import sys
import os
import re
import socket
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("roostos-timeguard-setup")

def discover_router_ip():
    """Discover RoostOS router IP using DNS SRV or resolving roostos.local."""
    logger.info("Attempting to discover RoostOS Router...")
    # 1. Resolve roostos.local
    try:
        ip = socket.gethostbyname("roostos.local")
        logger.info(f"Discovered RoostOS Router via host resolution: {ip}")
        return ip
    except socket.gaierror:
        pass

    # 2. Fallback to default gateway
    try:
        # Simple extraction from ip route
        out = subprocess.check_output("ip route show default", shell=True, text=True)
        parts = out.split()
        if "via" in parts:
            ip = parts[parts.index("via") + 1]
            logger.info(f"Discovered default gateway as fallback: {ip}")
            return ip
    except Exception as e:
        logger.error(f"Failed to find default gateway: {e}")

    return None

def configure_nslcd(router_ip):
    """Configure /etc/nslcd.conf to point to the discovered LDAP server."""
    nslcd_conf_path = "/etc/nslcd.conf"
    if not os.path.exists(nslcd_conf_path):
        logger.warning(f"{nslcd_conf_path} does not exist. Skipping nslcd configuration.")
        return

    logger.info(f"Configuring nslcd to point to LDAP server at ldap://{router_ip}...")
    try:
        with open(nslcd_conf_path, "r") as f:
            content = f.read()

        # Replace or append settings
        content = re.sub(r"^uri\s+.*", f"uri ldap://{router_ip}", content, flags=re.MULTILINE)
        content = re.sub(r"^base\s+.*", "base dc=roostos,dc=local", content, flags=re.MULTILINE)

        if "uri ldap://" not in content:
            content += f"\nuri ldap://{router_ip}\n"
        if "base dc=" not in content:
            content += "\nbase dc=roostos,dc=local\n"

        with open(nslcd_conf_path, "w") as f:
            f.write(content)
        
        # Restart nslcd service
        subprocess.run(["systemctl", "restart", "nslcd"], check=False)
        logger.info("nslcd configured and restarted successfully.")
    except Exception as e:
        logger.error(f"Failed to configure nslcd: {e}")

def configure_nsswitch():
    """Ensure ldap is in /etc/nsswitch.conf for passwd and group."""
    nsswitch_path = "/etc/nsswitch.conf"
    if not os.path.exists(nsswitch_path):
        return

    logger.info("Configuring /etc/nsswitch.conf for LDAP name resolution...")
    try:
        with open(nsswitch_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.startswith("passwd:") and "ldap" not in line:
                line = line.rstrip() + " ldap\n"
            elif line.startswith("group:") and "ldap" not in line:
                line = line.rstrip() + " ldap\n"
            new_lines.append(line)

        with open(nsswitch_path, "w") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.error(f"Failed to configure nsswitch.conf: {e}")

def configure_pam():
    """Integrate pam_exec for roostos-timeguardd pam-check in common-auth."""
    pam_auth_path = "/etc/pam.d/common-auth"
    if not os.path.exists(pam_auth_path):
        return

    logger.info("Configuring PAM authentication for screen time limits...")
    # Add pam_exec before pam_unix/ldap
    exec_rule = "auth    required    pam_exec.so stdout /usr/local/bin/roostos-timeguardd pam-check"
    try:
        with open(pam_auth_path, "r") as f:
            content = f.read()

        if "roostos-timeguardd pam-check" not in content:
            # Insert at the beginning or before standard rules
            content = exec_rule + "\n" + content
            with open(pam_auth_path, "w") as f:
                f.write(content)
            logger.info("PAM authentication updated.")
    except Exception as e:
        logger.error(f"Failed to update PAM: {e}")

def main():
    if os.getuid() != 0:
        print("This script must be run as root.", file=sys.stderr)
        sys.exit(1)

    router_ip = discover_router_ip()
    if not router_ip:
        logger.error("Could not discover RoostOS router. Using fallback configuration.")
        router_ip = "127.0.0.1"

    # Configure LDAP client stack
    configure_nslcd(router_ip)
    configure_nsswitch()
    configure_pam()

    # Save to daemon configuration
    config_path = "/etc/roostos-timeguardd/config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    try:
        import json
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
        config["mqtt_host"] = router_ip
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update daemon config: {e}")

if __name__ == "__main__":
    main()
