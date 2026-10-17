"""System diagnostics checks and kernel firewall log parser for RoostOS."""

import datetime
import os
import re
import subprocess
from typing import Any, Dict, List


def run_system_diagnostics() -> Dict[str, Any]:
    """Executes kernel, nftables, D-Bus, AppArmor, systemd, and reachability diagnostics."""
    checks: List[Dict[str, str]] = []

    # 1. IPv4 Forwarding
    ip_forward_ok = False
    ip_forward_msg = ""
    try:
        with open("/proc/sys/net/ipv4/ip_forward", "r") as f:
            val = f.read().strip()
            if val == "1":
                ip_forward_ok = True
                ip_forward_msg = "IPv4 forwarding is enabled in the kernel."
            else:
                ip_forward_msg = "IPv4 forwarding is disabled. LAN clients will not have internet access."
    except Exception as e:
        ip_forward_msg = f"Failed to check IPv4 forwarding: {e}"
    checks.append({"name": "IPv4 Packet Forwarding", "status": "PASS" if ip_forward_ok else "FAIL", "message": ip_forward_msg})

    # 2. nftables / NAT Masquerading
    nft_ok = False
    nft_msg = ""
    try:
        ruleset = subprocess.check_output(["nft", "list", "ruleset"], text=True)
        if "masquerade" in ruleset:
            nft_ok = True
            nft_msg = "NAT masquerading is active in nftables ruleset."
        else:
            nft_msg = "NAT masquerading is not active in nftables ruleset."
    except Exception as e:
        nft_msg = f"Failed to query nftables ruleset: {e}"
    checks.append({"name": "NAT Masquerading (nftables)", "status": "PASS" if nft_ok else "FAIL", "message": nft_msg})

    # 3. D-Bus Security Policy for DNSResolver
    dbus_ok = False
    dbus_msg = ""
    policy_path = "/etc/dbus-1/system.d/org.roostos.conf"
    if os.path.exists(policy_path):
        try:
            with open(policy_path, "r") as f:
                content = f.read()
                if "org.roostos.DNSResolver" in content and "allow own" in content:
                    dbus_ok = True
                    dbus_msg = "D-Bus security policy permits org.roostos.DNSResolver ownership."
                else:
                    dbus_msg = "D-Bus policy configuration is missing the DNSResolver ownership allowance."
        except Exception as e:
            dbus_msg = f"Failed to read D-Bus policy file: {e}"
    else:
        dbus_msg = f"D-Bus policy file {policy_path} does not exist."
    checks.append({"name": "D-Bus DNSResolver Policy", "status": "PASS" if dbus_ok else "FAIL", "message": dbus_msg})

    # 4. AppArmor Exception for Kea DHCP Hook
    apparmor_ok = True
    apparmor_msg = "AppArmor is inactive or no policy exceptions are required."
    aa_path = "/etc/apparmor.d/local/usr.sbin.kea-dhcp4"
    if os.path.exists(aa_path):
        try:
            res = subprocess.run(["systemctl", "is-active", "--quiet", "apparmor"])
            if res.returncode == 0:
                with open(aa_path, "r") as f:
                    content = f.read()
                    if "roost-dhcp-hook ux" in content:
                        apparmor_ok = True
                        apparmor_msg = "AppArmor Kea policy override hook exception is active."
                    else:
                        apparmor_ok = False
                        apparmor_msg = "AppArmor override file usr.sbin.kea-dhcp4 is missing the hook exception."
        except Exception as e:
            apparmor_msg = f"Failed to verify AppArmor status: {e}"
    checks.append({"name": "AppArmor DHCP Hook Exception", "status": "PASS" if apparmor_ok else "FAIL", "message": apparmor_msg})

    # 5. Kea DHCP Service Status
    kea_ok = False
    kea_msg = ""
    try:
        res = subprocess.run(["systemctl", "is-active", "--quiet", "kea-dhcp4-server"])
        if res.returncode == 0:
            kea_ok = True
            kea_msg = "Kea DHCP4 Server service is running."
        else:
            kea_msg = "Kea DHCP4 Server service is stopped or failed."
    except Exception as e:
        kea_msg = f"Failed to check Kea DHCP service status: {e}"
    checks.append({"name": "Kea DHCPv4 Daemon", "status": "PASS" if kea_ok else "FAIL", "message": kea_msg})

    # 6. Docker Daemon Status
    docker_ok = False
    docker_msg = ""
    try:
        res = subprocess.run(["systemctl", "is-active", "--quiet", "docker"])
        if res.returncode == 0:
            docker_ok = True
            docker_msg = "Docker Daemon service is running."
        else:
            docker_msg = "Docker Daemon service is stopped or failed."
    except Exception as e:
        docker_msg = f"Failed to check Docker service status: {e}"
    checks.append({"name": "Docker Daemon", "status": "PASS" if docker_ok else "FAIL", "message": docker_msg})

    # 7. WAN Gateway Connection Ping
    wan_ping_ok = False
    wan_ping_msg = ""
    try:
        res = subprocess.run(["ping", "-c", "1", "-W", "2", "1.1.1.1"], capture_output=True, text=True)
        if res.returncode == 0:
            wan_ping_ok = True
            wan_ping_msg = "Successfully pinged public target (1.1.1.1) over WAN."
        else:
            wan_ping_msg = "Failed to ping public target over WAN (connectivity issue)."
    except Exception as e:
        wan_ping_msg = f"Ping command execution failed: {e}"
    checks.append({"name": "WAN Internet Reachability", "status": "PASS" if wan_ping_ok else "FAIL", "message": wan_ping_msg})

    # 8. Kea run-script hook library existence
    hook_lib_ok = False
    hook_lib_msg = ""
    hook_lib_path = "/usr/lib/x86_64-linux-gnu/kea/hooks/libdhcp_run_script.so"
    hook_lib_path_arm = "/usr/lib/aarch64-linux-gnu/kea/hooks/libdhcp_run_script.so"
    if os.path.exists(hook_lib_path) or os.path.exists(hook_lib_path_arm):
        hook_lib_ok = True
        hook_lib_msg = "Kea run-script hook library (libdhcp_run_script.so) is installed."
    else:
        hook_lib_msg = "Kea run-script hook library is missing. Active leases list will not update. Install 'kea-hook-run-script' package."
    checks.append({"name": "Kea Run-Script Hook Library", "status": "PASS" if hook_lib_ok else "FAIL", "message": hook_lib_msg})

    overall_status = "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS"
    return {"status": overall_status, "checks": checks}


def collect_firewall_blocks(is_mock: bool, limit: int = 50) -> List[Dict[str, Any]]:
    """Reads blocked packet events from kernel journal or returns mock entries in mock mode."""
    blocks: List[Dict[str, Any]] = []
    if not is_mock:
        try:
            res = subprocess.run(
                ["journalctl", "-k", "-n", "1000", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                pattern = re.compile(
                    r"(?P<ts>\w{3}\s+\d+\s+\d+:\d+:\d+).*FIREWALL:BLOCKED:(?P<rule>\S+).*IN=(?P<in>\S*).*OUT=(?P<out>\S*).*SRC=(?P<src>\S+).*DST=(?P<dst>\S+).*PROTO=(?P<proto>\S+)"
                )
                for line in res.stdout.splitlines():
                    if "FIREWALL:BLOCKED:" in line:
                        match = pattern.search(line)
                        if match:
                            spt_match = re.search(r"SPT=(\d+)", line)
                            dpt_match = re.search(r"DPT=(\d+)", line)
                            blocks.append({
                                "timestamp": match.group("ts"),
                                "rule": match.group("rule").replace("_", " "),
                                "in_face": match.group("in"),
                                "out_face": match.group("out"),
                                "src_ip": match.group("src"),
                                "dst_ip": match.group("dst"),
                                "proto": match.group("proto"),
                                "src_port": spt_match.group(1) if spt_match else "",
                                "dst_port": dpt_match.group(1) if dpt_match else "",
                            })
        except Exception:
            pass

    if not blocks and is_mock:
        now = datetime.datetime.now()
        mock_data = [
            ("Block_Tor_Traffic", "192.168.1.105", "185.220.101.5", "TCP", "49321", "9001", "br0"),
            ("Default_Input_Drop", "198.51.100.72", "192.168.100.45", "UDP", "38291", "5060", "eth0"),
            ("Blocked_Client", "192.168.1.50", "142.250.190.46", "TCP", "51023", "443", "br0"),
            ("Block_SSH_Access", "203.0.113.15", "192.168.100.45", "TCP", "55432", "22", "eth0"),
            ("Kids_Bedtime_Block", "192.168.1.50", "31.13.71.36", "TCP", "61240", "443", "br0"),
        ]
        for i, (rule, src, dst, proto, spt, dpt, iif) in enumerate(mock_data):
            ts = (now - datetime.timedelta(minutes=i * 7 + 3)).strftime("%b %d %H:%M:%S")
            blocks.append({
                "timestamp": ts,
                "rule": rule.replace("_", " "),
                "in_face": iif,
                "out_face": "eth0" if iif == "br0" else "",
                "src_ip": src,
                "dst_ip": dst,
                "proto": proto,
                "src_port": spt,
                "dst_port": dpt,
            })
    return blocks[:limit]
