import os
import sys
import time
import socket
import ipaddress
import subprocess
import click
from typing import List, Dict, Any, Tuple

from prompt_toolkit.shortcuts import (
    yes_no_dialog,
    input_dialog,
    radiolist_dialog,
    checkboxlist_dialog,
    message_dialog,
    button_dialog,
)

from roostos_engine.config import (
    load_config_directory,
    SystemConfig,
    NetworkConfig,
    NetworkInterface,
    NetworkBridge,
    SystemDNSConfig,
    SchedulesConfig,
    FirewallSettings,
    InputRuleConfig,
    save_config_file,
)

def has_existing_config(config_dir: str) -> bool:
    """Check if main configuration files already exist in the target directory."""
    expected_files = ["system.yaml", "network.yaml", "schedules.yaml"]
    return any(os.path.exists(os.path.join(config_dir, f)) for f in expected_files)

def handle_cancel(val: Any) -> None:
    if val is None:
        click.echo("Setup cancelled. Configuration files were NOT written.")
        sys.exit(0)


def list_interfaces() -> List[str]:
    """Scan /sys/class/net to find available physical network interfaces."""
    interfaces = []
    if os.path.exists("/sys/class/net"):
        try:
            for name in os.listdir("/sys/class/net"):
                # Filter out loopback and typical virtual interfaces
                if name == "lo" or name.startswith(("br", "docker", "veth", "wg", "tap", "tun", "virbr")):
                    continue
                interfaces.append(name)
        except Exception:
            pass
    
    if not interfaces:
        # Fallback/mock interfaces for non-Linux or development environments
        interfaces = ["eth0", "eth1", "eth2", "eth3"]
    return sorted(interfaces)

def is_valid_ip(ip_str: str) -> bool:
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False

def is_valid_cidr(cidr_str: str) -> bool:
    try:
        ipaddress.ip_network(cidr_str, strict=False)
        return "/" in cidr_str
    except ValueError:
        return False

def get_interface_mac(name: str) -> str:
    """Read the MAC address of a network interface from sysfs."""
    try:
        path = f"/sys/class/net/{name}/address"
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def prompt_choice(question: str, choices: List[str], default: str) -> str:
    """Prompt user to choose from a list of options."""
    choice_str = "/".join([f"[{c}]" if c == default else c for c in choices])
    while True:
        val = input(f"{question} ({choice_str}): ").strip()
        if not val:
            return default
        # Match case-insensitive
        for c in choices:
            if c.lower() == val.lower():
                return c
        print(f"Invalid option. Please choose from: {', '.join(choices)}")

def prompt_bool(question: str, default: bool) -> bool:
    """Prompt user for a yes/no question."""
    default_str = "y" if default else "n"
    choices = "Y/n" if default else "y/N"
    while True:
        val = input(f"{question} ({choices}): ").strip().lower()
        if not val:
            return default
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")

@click.command()
@click.option("--dir", "config_dir", default="/etc/roostos", help="Path to config files directory")
@click.option("--non-interactive", is_flag=True, help="Run without user interaction (uses defaults/env variables)")
def main(config_dir: str, non_interactive: bool) -> None:
    """RoostOS Guided Setup Wizard."""
    if not non_interactive and has_existing_config(config_dir):
        choice = button_dialog(
            title="Existing Configuration Found",
            text=f"Existing RoostOS configuration files were found in '{config_dir}'.\n\nDo you want to use the existing configuration and exit, or re-run the setup wizard?",
            buttons=[
                ("Use Existing & Exit", "use_existing"),
                ("Re-run Wizard", "rerun"),
            ]
        ).run()
        if choice == "use_existing" or choice is None:
            click.echo("Using existing configuration. Exiting.")
            sys.exit(0)

    click.clear()
    click.secho("===================================================", fg="cyan", bold=True)
    click.secho("         RoostOS Initial Guided Setup Wizard        ", fg="cyan", bold=True)
    click.secho("===================================================", fg="cyan", bold=True)
    
    if os.getuid() != 0 and config_dir == "/etc/roostos":
        if not non_interactive:
            cont = yes_no_dialog(
                title="Warning: Not Running as Root",
                text="You are not running as root. Writing configurations to /etc/roostos will likely fail.\n\nDo you want to continue anyway?"
            ).run()
            if not cont:
                click.echo("Setup cancelled.")
                sys.exit(0)

    # 1. Discover interfaces
    ifaces = list_interfaces()
    if not ifaces:
        click.secho("Error: No network interfaces discovered on the system.", fg="red", err=True)
        sys.exit(1)

    click.secho("\n--- Network Interface Discovery ---", fg="cyan")
    click.echo(f"Discovered interfaces: {', '.join(ifaces)}")

    # 2. WAN Interface Selection
    click.secho("\n--- WAN Interface Configuration ---", fg="cyan")
    default_wan = ifaces[0] if ifaces else "eth0"
    if "eth0" in ifaces:
        default_wan = "eth0"
    elif "enp0s3" in ifaces:
        default_wan = "enp0s3"

    if non_interactive:
        wan_iface = os.environ.get("ROOSTOS_WAN_INTERFACE", default_wan)
    else:
        choices = []
        for name in ifaces:
            mac = get_interface_mac(name)
            mac_str = f" ({mac})" if mac else ""
            choices.append((name, f"{name}{mac_str}"))
        
        wan_iface = radiolist_dialog(
            title="WAN Interface Selection",
            text="Please select the WAN (Internet) interface:",
            values=choices,
            default=default_wan
        ).run()
        handle_cancel(wan_iface)

    click.echo(f"Selected WAN interface: {wan_iface}")

    # 3. WAN Protocol Configuration
    if non_interactive:
        wan_proto = os.environ.get("ROOSTOS_WAN_PROTO", "dhcp").lower()
        ipv6_enabled = os.environ.get("ROOSTOS_WAN_IPV6", "true").lower() in ("true", "1", "yes")
        wan_ip = os.environ.get("ROOSTOS_WAN_IP", "")
        wan_gw = os.environ.get("ROOSTOS_WAN_GATEWAY", "")
    else:
        wan_proto = radiolist_dialog(
            title="WAN Protocol",
            text="How should the WAN interface be configured?",
            values=[("dhcp", "DHCP (Dynamic IP)"), ("static", "Static IP")],
            default="dhcp"
        ).run()
        handle_cancel(wan_proto)

        ipv6_enabled = yes_no_dialog(
            title="WAN IPv6",
            text="Should IPv6 be enabled?"
        ).run()
        if ipv6_enabled is None:
            handle_cancel(None)

        wan_ip = ""
        wan_gw = ""
        if wan_proto == "static":
            while True:
                wan_ip = input_dialog(
                    title="Static WAN IP",
                    text="Enter static WAN IP address and netmask (e.g. 192.168.0.100/24):"
                ).run()
                handle_cancel(wan_ip)
                wan_ip = wan_ip.strip()
                if is_valid_cidr(wan_ip):
                    break
                message_dialog(
                    title="Error",
                    text="Invalid format. Please enter an IP with subnet mask in CIDR notation (e.g., 192.168.0.100/24)."
                ).run()

            while True:
                wan_gw = input_dialog(
                    title="Static WAN Gateway",
                    text="Enter static WAN Gateway IP address (e.g. 192.168.0.1):"
                ).run()
                handle_cancel(wan_gw)
                wan_gw = wan_gw.strip()
                if is_valid_ip(wan_gw):
                    break
                message_dialog(
                    title="Error",
                    text="Invalid format. Please enter a valid gateway IP address."
                ).run()

    # 4. LAN Interface Selection
    click.secho("\n--- LAN Interface Configuration ---", fg="cyan")
    remaining_ifaces = [i for i in ifaces if i != wan_iface]
    default_lan = [remaining_ifaces[0]] if remaining_ifaces else ["eth1"]
    if "eth1" in remaining_ifaces:
        default_lan = ["eth1"]

    if non_interactive:
        lan_env = os.environ.get("ROOSTOS_LAN_INTERFACES", ",".join(default_lan))
        lan_ifaces = [x.strip() for x in lan_env.split(",") if x.strip()]
    else:
        choices = []
        for name in remaining_ifaces:
            mac = get_interface_mac(name)
            mac_str = f" ({mac})" if mac else ""
            choices.append((name, f"{name}{mac_str}"))

        while True:
            lan_ifaces = checkboxlist_dialog(
                title="LAN Interface(s) Selection",
                text="Please select one or more LAN interfaces:",
                values=choices,
                default_values=default_lan
            ).run()
            handle_cancel(lan_ifaces)
            if lan_ifaces:
                break
            message_dialog(
                title="Error",
                text="You must select at least one LAN interface."
            ).run()

    click.echo(f"Selected LAN interface(s): {', '.join(lan_ifaces)}")

    # 5. LAN Network / IP Address
    if non_interactive:
        lan_net_str = os.environ.get("ROOSTOS_LAN_NETWORK", "192.168.1.0/24")
        lan_ip_str = os.environ.get("ROOSTOS_LAN_IP", "192.168.1.1")
    else:
        while True:
            lan_net_str = input_dialog(
                title="LAN Network Subnet",
                text="What is the default network for the LAN?",
                default="192.168.1.0/24"
            ).run()
            handle_cancel(lan_net_str)
            lan_net_str = lan_net_str.strip()
            if is_valid_cidr(lan_net_str):
                break
            message_dialog(
                title="Error",
                text="Invalid subnet. Please use CIDR notation (e.g. 192.168.1.0/24)."
            ).run()

        while True:
            lan_ip_str = input_dialog(
                title="LAN Router IP Address",
                text="What is the IP address of the LAN side of the router?",
                default="192.168.1.1"
            ).run()
            handle_cancel(lan_ip_str)
            lan_ip_str = lan_ip_str.strip()
            if is_valid_ip(lan_ip_str):
                # Verify LAN IP is in the default network
                net = ipaddress.ip_network(lan_net_str, strict=False)
                ip = ipaddress.ip_address(lan_ip_str)
                if ip in net:
                    break
                else:
                    message_dialog(
                        title="Error",
                        text=f"Error: LAN IP {lan_ip_str} does not belong to the LAN network {lan_net_str}."
                    ).run()
            else:
                message_dialog(
                    title="Error",
                    text="Invalid IP address format."
                ).run()

    # Calculate default DHCP Pool ranges
    net = ipaddress.ip_network(lan_net_str, strict=False)
    ip = ipaddress.ip_address(lan_ip_str)
    prefix_len = net.prefixlen
    
    # Suggest DHCP pool starting at host 100, ending at min(250, last host)
    hosts_count = net.num_addresses - 2
    if hosts_count > 100:
        default_dhcp_start = str(net[100])
        default_dhcp_end = str(net[min(250, net.num_addresses - 2)])
    elif hosts_count > 2:
        default_dhcp_start = str(net[2]) if ip == net[1] else str(net[1])
        default_dhcp_end = str(net[-2])
    else:
        # Extremely small subnet, no space for dhcp pool
        default_dhcp_start = ""
        default_dhcp_end = ""

    dhcp_enabled = True
    dhcp_start = default_dhcp_start
    dhcp_end = default_dhcp_end

    if default_dhcp_start and default_dhcp_end:
        if non_interactive:
            dhcp_enabled = os.environ.get("ROOSTOS_LAN_DHCP_ENABLED", "true").lower() in ("true", "1", "yes")
            dhcp_start = os.environ.get("ROOSTOS_LAN_DHCP_START", default_dhcp_start)
            dhcp_end = os.environ.get("ROOSTOS_LAN_DHCP_END", default_dhcp_end)
        else:
            dhcp_enabled = yes_no_dialog(
                title="LAN DHCP Server",
                text="Should DHCP Server be enabled on LAN?"
            ).run()
            if dhcp_enabled is None:
                handle_cancel(None)

            if dhcp_enabled:
                confirm_dhcp = yes_no_dialog(
                    title="LAN DHCP Pool",
                    text=f"Use default DHCP pool {default_dhcp_start} - {default_dhcp_end}?"
                ).run()
                if confirm_dhcp is None:
                    handle_cancel(None)

                if not confirm_dhcp:
                    while True:
                        dhcp_start = input_dialog(
                            title="DHCP Pool Start IP",
                            text="Enter DHCP pool start IP:",
                            default=default_dhcp_start
                        ).run()
                        handle_cancel(dhcp_start)
                        dhcp_start = dhcp_start.strip()
                        if is_valid_ip(dhcp_start) and ipaddress.ip_address(dhcp_start) in net:
                            break
                        message_dialog(
                            title="Error",
                            text=f"IP must be valid and belong to the network {lan_net_str}."
                        ).run()

                    while True:
                        dhcp_end = input_dialog(
                            title="DHCP Pool End IP",
                            text="Enter DHCP pool end IP:",
                            default=default_dhcp_end
                        ).run()
                        handle_cancel(dhcp_end)
                        dhcp_end = dhcp_end.strip()
                        if is_valid_ip(dhcp_end) and ipaddress.ip_address(dhcp_end) in net:
                            if ipaddress.ip_address(dhcp_start) <= ipaddress.ip_address(dhcp_end):
                                break
                            else:
                                message_dialog(
                                    title="Error",
                                    text="DHCP pool end IP must be greater than or equal to start IP."
                                ).run()
                        else:
                            message_dialog(
                                title="Error",
                                text=f"IP must be valid and belong to the network {lan_net_str}."
                            ).run()
    else:
        dhcp_enabled = False

    # 6. DNS Setup
    click.secho("\n--- Upstream DNS Configuration ---", fg="cyan")
    default_dns = "1.1.1.1, 8.8.8.8"
    if non_interactive:
        dns_input = os.environ.get("ROOSTOS_DNS_SERVERS", default_dns)
    else:
        dns_input = input_dialog(
            title="Upstream DNS Configuration",
            text="What are the upstream DNS servers (comma-separated)?",
            default=default_dns
        ).run()
        handle_cancel(dns_input)
    
    if not dns_input:
        dns_input = default_dns
    dns_servers = [x.strip() for x in dns_input.replace(" ", ",").split(",") if x.strip()]
    
    # Validate DNS IPs
    valid_dns = []
    for dns in dns_servers:
        if is_valid_ip(dns):
            valid_dns.append(dns)
        else:
            click.secho(f"Warning: Ignored invalid DNS server IP '{dns}'", fg="yellow")
    if not valid_dns:
        valid_dns = ["1.1.1.1", "8.8.8.8"]

    # 7. WAN Access Configuration
    click.secho("\n--- WAN Access Configuration ---", fg="cyan")
    click.echo("By default, no services are accessible from the WAN side for security.")

    if non_interactive:
        wan_web_access = os.environ.get("ROOSTOS_WAN_WEB_ACCESS", "false").lower() in ("true", "1", "yes")
        wan_ssh_access = os.environ.get("ROOSTOS_WAN_SSH_ACCESS", "false").lower() in ("true", "1", "yes")
    else:
        wan_web_access = yes_no_dialog(
            title="WAN Web UI Access",
            text="Allow RoostOS Web UI (port 8000) from WAN?"
        ).run()
        if wan_web_access is None:
            handle_cancel(None)

        wan_ssh_access = yes_no_dialog(
            title="WAN SSH Access",
            text="Allow SSH (port 22) from WAN?"
        ).run()
        if wan_ssh_access is None:
            handle_cancel(None)

    # 8. Review and Apply Settings
    bridge_ip_full = f"{lan_ip_str}/{prefix_len}"

    if non_interactive:
        apply_config = True
    else:
        review_text = (
            f"WAN Interface:      {wan_iface}\n"
            f"WAN Configuration:  {wan_proto.upper()}" + (f" ({wan_ip}, Gateway: {wan_gw})" if wan_proto == "static" else "") + "\n"
            f"WAN IPv6 Enabled:   {ipv6_enabled}\n"
            f"LAN Interface(s):   {', '.join(lan_ifaces)}\n"
            f"LAN Network:        {lan_net_str}\n"
            f"LAN IP (Router):    {bridge_ip_full}\n"
            f"LAN DHCP Server:    {'ENABLED (' + dhcp_start + ' to ' + dhcp_end + ')' if dhcp_enabled else 'DISABLED'}\n"
            f"Upstream DNS:       {', '.join(valid_dns)}\n"
            f"WAN SSH Access:     {'ENABLED' if wan_ssh_access else 'DISABLED'}\n"
            f"WAN Web UI Access:  {'ENABLED' if wan_web_access else 'DISABLED'}\n"
            f"Config Directory:   {config_dir}\n\n"
            "Do you want to write and apply these settings now?"
        )
        apply_config = yes_no_dialog(
            title="Review and Apply Settings",
            text=review_text
        ).run()
        if apply_config is None:
            handle_cancel(None)

    if not apply_config:
        click.echo("Setup cancelled. Configuration files were NOT written.")
        sys.exit(0)

    # Load existing configs to merge fields gracefully
    try:
        config = load_config_directory(config_dir)
    except Exception:
        # Create fresh models if config directory is empty/broken
        from roostos_engine.config import RoostConfig, SystemSettings, WifiSettings
        config = RoostConfig(
            system=SystemSettings(),
            users=[],
            network=None,  # Will be populated
            wifi=WifiSettings(),
            vpns=[],
            people=[],
            buildings=[],
            rooms=[],
            devices=[],
            firewall=None,  # Will be populated
            plugins=[]
        )

    # Update system.yaml settings
    if not config.system.dns:
        config.system.dns = SystemDNSConfig()
    config.system.dns.forwarders = valid_dns

    # Update network.yaml settings
    from roostos_engine.config import NetworkSettings
    if not config.network:
        config.network = NetworkSettings()

    # Rebuild interface list
    new_interfaces = []
    # WAN
    new_interfaces.append(NetworkInterface(
        name=wan_iface,
        role="wan",
        dhcp=True if wan_proto == "dhcp" else False,
        ip=wan_ip if wan_proto == "static" else None,
        gateway=wan_gw if wan_proto == "static" else None,
        ipv6=ipv6_enabled
    ))
    # LAN
    for lan_if in lan_ifaces:
        new_interfaces.append(NetworkInterface(
            name=lan_if,
            role="lan",
            bridge="br0"
        ))
    config.network.interfaces = new_interfaces

    # Rebuild bridges list
    config.network.bridges = [
        NetworkBridge(
            name="br0",
            ip=bridge_ip_full,
            dhcp_enabled=dhcp_enabled,
            dhcp_pool_start=dhcp_start if dhcp_enabled else None,
            dhcp_pool_end=dhcp_end if dhcp_enabled else None
        )
    ]

    # Save to disk
    os.makedirs(config_dir, exist_ok=True)
    system_config_obj = SystemConfig(system=config.system, users=config.users)
    network_config_obj = NetworkConfig(network=config.network, wifi=config.wifi, vpns=config.vpns)

    # Build firewall rules for WAN access
    wan_rules = []
    if wan_ssh_access:
        wan_rules.append(InputRuleConfig(
            name="WAN SSH Access",
            interface=wan_iface,
            protocol="tcp",
            port=22,
            action="accept",
            enabled=True
        ))
    if wan_web_access:
        wan_rules.append(InputRuleConfig(
            name="WAN Web UI Access",
            interface=wan_iface,
            protocol="tcp",
            port=8000,
            action="accept",
            enabled=True
        ))

    # Load existing schedules config to preserve port_forwards and schedules
    existing_firewall = getattr(config, 'firewall', None) or FirewallSettings()
    # Merge: keep existing rules that don't conflict with WAN access rule names
    wan_rule_names = {r.name for r in wan_rules}
    preserved_rules = [r.model_dump() for r in existing_firewall.rules if r.name not in wan_rule_names]
    new_rules = [r.model_dump() for r in wan_rules]
    merged_rules = preserved_rules + new_rules

    schedules_config_obj = SchedulesConfig(
        firewall=FirewallSettings(
            port_forwards=[pf.model_dump() for pf in existing_firewall.port_forwards],
            rules=merged_rules,
            schedules=[s.model_dump() for s in existing_firewall.schedules]
        )
    )

    try:
        save_config_file(config_dir, "system.yaml", system_config_obj)
        save_config_file(config_dir, "network.yaml", network_config_obj)
        save_config_file(config_dir, "schedules.yaml", schedules_config_obj)
        click.secho("\n✓ Configuration files written successfully.", fg="green")
    except Exception as e:
        click.secho(f"\n✗ Error saving configuration files: {e}", fg="red", err=True)
        sys.exit(1)

    # 8. Apply settings live if running as root
    if os.getuid() == 0:
        click.secho("\nApplying network configuration live...", fg="cyan")
        # Trigger systemd-networkd restart
        try:
            subprocess.run(["systemctl", "restart", "systemd-networkd"], check=True, capture_output=True)
            click.echo("✓ systemd-networkd restarted successfully.")
        except Exception as e:
            click.secho(f"Warning: Failed to restart systemd-networkd: {e}", fg="yellow")

        # Restart roostd daemon to re-compile firewall/DHCP rules
        try:
            # Check if roostd is currently running/enabled
            res = subprocess.run(["systemctl", "is-active", "roostd"], capture_output=True, text=True)
            if res.returncode == 0 or "inactive" in res.stdout:
                subprocess.run(["systemctl", "restart", "roostd"], check=True, capture_output=True)
                click.echo("✓ roostd daemon service restarted successfully.")
            else:
                # If service unit is not found or not active, try starting it
                subprocess.run(["systemctl", "start", "roostd"], capture_output=True)
        except Exception as e:
            click.secho(f"Warning: Failed to restart roostd service: {e}", fg="yellow")

        # Give systemd-networkd a few seconds to initialize/fetch IP
        click.echo("Waiting 5 seconds for network interfaces to initialize...")
        time.sleep(5)

        # 9. Settings Validation
        click.secho("\n--- Quick Validation ---", fg="cyan")
        # Check WAN interface status
        wan_status = "DOWN"
        wan_addr = "None"
        try:
            res = subprocess.run(["ip", "addr", "show", "dev", wan_iface], capture_output=True, text=True)
            if res.returncode == 0:
                if "state UP" in res.stdout or "state UNKNOWN" in res.stdout:
                    wan_status = "UP"
                import re
                match = re.search(r"inet\s+([0-9.]+)", res.stdout)
                if match:
                    wan_addr = match.group(1)
        except Exception:
            pass

        if wan_status == "UP" and wan_addr != "None":
            click.secho(f"WAN Interface ({wan_iface}): [OK] Operstate is {wan_status}, IP: {wan_addr}", fg="green")
        else:
            click.secho(f"WAN Interface ({wan_iface}): [WARNING] Operstate is {wan_status}, IP: {wan_addr}", fg="yellow")

        # Ping verification (Internet reachability)
        ping_ok = False
        click.echo("Verifying WAN internet connection (pinging 8.8.8.8)...")
        try:
            res = subprocess.run(["ping", "-c", "2", "-W", "3", "8.8.8.8"], capture_output=True)
            if res.returncode == 0:
                ping_ok = True
        except Exception:
            pass

        if ping_ok:
            click.secho("Internet Reachability: [OK] Successfully pinged 8.8.8.8", fg="green")
        else:
            click.secho("Internet Reachability: [FAILED] Could not ping 8.8.8.8", fg="red")

        # DNS resolution verification
        dns_ok = False
        click.echo("Verifying DNS resolution (resolving google.com)...")
        try:
            socket.gethostbyname("google.com")
            dns_ok = True
        except Exception:
            pass

        if dns_ok:
            click.secho("DNS Name Resolution: [OK] Successfully resolved google.com", fg="green")
        else:
            click.secho("DNS Name Resolution: [FAILED] Could not resolve google.com", fg="red")

        click.secho("\nInitial guided setup complete!", fg="green", bold=True)
    else:
        click.echo("\nNon-root mode. Live configuration changes were not applied to system services.")
        click.secho("\nInitial guided setup files created (Dry-run)!", fg="green", bold=True)

if __name__ == "__main__":
    main()
