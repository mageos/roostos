"""RoostOS Root Command-Line Interface (CLI)."""

import os
import sys
import click
from typing import Optional

from roostos_cli import __version__
from roostos_cli.models import (
    NodeRole,
    GatewayConfigParams,
    ControllerConfigParams,
    WorkstationConfigParams,
    EdgeGatewayConfigParams,
)
from roostos_cli.inspector import EnvironmentInspector
from roostos_cli.discovery import NetworkDiscoverer
from roostos_cli.wizard import SetupWizard
from roostos_cli.edge import edge_group
from roostos_cli.app_cmd import app_group
from roostos_cli.update_cmd import update_group
from roostos_cli.doctor import doctor_cmd
from roostos_cli.service_cmd import service_group, logs_cmd
from roostos_cli.network_cmd import net_group, dhcp_group
from roostos_cli.firewall_cmd import fw_group
from roostos_cli.cluster_cmd import cluster_group
from roostos_cli.device_cmd import devices_group, people_group


@click.group()
@click.version_option(version=__version__, prog_name="roostos")
def cli() -> None:
    """RoostOS: Universal Network Operating System CLI."""
    pass


cli.add_command(edge_group)
cli.add_command(app_group)
cli.add_command(update_group)
cli.add_command(doctor_cmd)
cli.add_command(doctor_cmd, name="diag")
cli.add_command(service_group)
cli.add_command(logs_cmd)
cli.add_command(net_group)
cli.add_command(dhcp_group)
cli.add_command(fw_group)
cli.add_command(cluster_group)
cli.add_command(devices_group)
cli.add_command(people_group)


@cli.command(name="status")
@click.option("--config-dir", default="/etc/roostos", help="Configuration files directory")
def status_cmd(config_dir: str) -> None:
    """Displays local hardware, assigned roles, and network status."""
    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("              RoostOS Node Status                 ", fg="cyan", bold=True)
    click.secho("==================================================", fg="cyan", bold=True)

    env = EnvironmentInspector.inspect()
    click.echo(f"Architecture:      {env.arch} ({env.cpu_cores} cores)")
    click.echo(f"Memory:            {env.memory_total_mb} MB (Free: {env.memory_free_mb} MB)")
    click.echo(f"Form Factor:       {'Laptop' if env.is_laptop else 'Desktop/Server/SBC'}")
    click.echo(f"Network Adapters:  {', '.join([f'{i.name} ({i.operstate})' for i in env.interfaces])}")

    # Check configured role in system.yaml
    role_str = "Unconfigured"
    sys_path = os.path.join(config_dir, "system.yaml")
    if os.path.exists(sys_path):
        try:
            import yaml
            with open(sys_path, "r") as f:
                data = yaml.safe_load(f)
            roles = data.get("system", {}).get("cluster", {}).get("roles", [])
            if roles:
                role_str = ", ".join(roles)
        except Exception:
            pass

    click.echo(f"Assigned Role(s):  {role_str}")
    click.secho("==================================================", fg="cyan")


@cli.command(name="discover")
def discover_cmd() -> None:
    """Scans local network for active RoostOS Gateways and Controllers."""
    click.secho("Scanning local network for RoostOS services...", fg="cyan")
    services = NetworkDiscoverer.discover_services(timeout_seconds=1.5)
    if not services:
        click.echo("No RoostOS gateways or controllers discovered on this subnet.")
        return

    click.secho(f"Discovered {len(services)} RoostOS service(s):", fg="green")
    for s in services:
        click.echo(f"  • [{s.service_type.upper()}] {s.name} at {s.ip}:{s.port}")


@cli.command(name="setup")
@click.option("--role", type=click.Choice([r.value for r in NodeRole]), help="Force deployment role")
@click.option("--wan", help="WAN interface for Gateway role")
@click.option("--lan", help="LAN interfaces (comma-separated) for Gateway role")
@click.option("--subnet", default="192.168.1.0/24", help="LAN subnet for Gateway role")
@click.option("--dns-subsystem", type=click.Choice(["local", "technitium"], case_sensitive=False), default="local", help="DNS subsystem to use (local or technitium)")
@click.option("--allow-wan-ssh", is_flag=True, help="Allow SSH on WAN interface")
@click.option("--allow-wan-web", is_flag=True, help="Allow RoostOS Web on WAN interface")
@click.option("--controller", help="Controller host/IP for Workstation role")
@click.option("--token", help="Join token for Workstation role")
@click.option("--non-interactive", is_flag=True, help="Run without interactive prompts")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
@click.option("--mock", is_flag=True, help="Mock package installation (dry-run)")
def setup_cmd(
    role: Optional[str],
    wan: Optional[str],
    lan: Optional[str],
    subnet: str,
    dns_subsystem: str,
    allow_wan_ssh: bool,
    allow_wan_web: bool,
    controller: Optional[str],
    token: Optional[str],
    non_interactive: bool,
    config_dir: str,
    mock: bool,
) -> None:
    """Launches the RoostOS Setup Wizard."""
    if not mock and os.environ.get("ROOSTOS_MOCK_INSTALL") != "1" and os.getuid() != 0:
        click.secho("✗ Root privileges are required to run the RoostOS setup wizard.", fg="red", bold=True, err=True)
        click.secho("Please run with sudo or as root: sudo roostos setup", fg="yellow", err=True)
        sys.exit(1)

    click.clear()
    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("          RoostOS Universal Setup Wizard          ", fg="cyan", bold=True)
    click.secho("==================================================", fg="cyan", bold=True)

    env = EnvironmentInspector.inspect()
    env.discovered_gateways = NetworkDiscoverer.discover_gateways()
    env.discovered_controllers = NetworkDiscoverer.discover_controllers()

    click.echo(f"System:       {env.arch} | {env.cpu_cores} Cores | {env.memory_total_mb} MB RAM")
    click.echo(f"Form Factor:  {'Laptop' if env.is_laptop else 'Desktop/Server/SBC'}")
    click.echo(f"Adapters:     {', '.join([i.name for i in env.interfaces])}")
    click.secho(f"Auto-Detect:  {env.recommendation_reason}", fg="yellow")

    target_role: Optional[NodeRole] = NodeRole(role) if role else None

    # Interactive role selection if not supplied
    if not target_role and not non_interactive:
        click.echo("\nPlease select the role for this system:")
        click.echo("  [1] Gateway Router (Firewall, DHCP, WAN/LAN routing)")
        click.echo("  [2] Central Controller & App Server (Cluster coordinator)")
        click.echo("  [3] Standalone All-in-One (Router + Controller on one machine)")
        click.echo("  [4] Client Workstation (Family PC/laptop: screen-time & domain)")
        click.echo("  [5] Edge Gateway (VPS Ingress & CGNAT bypass)")
        choice = click.prompt("Selection", type=click.IntRange(1, 5), default=1)
        role_map = {
            1: NodeRole.GATEWAY,
            2: NodeRole.CONTROLLER,
            3: NodeRole.STANDALONE,
            4: NodeRole.WORKSTATION,
            5: NodeRole.EDGE_GATEWAY,
        }
        target_role = role_map[choice]

    target_role = target_role or env.recommended_role

    gw_params = None
    if target_role in (NodeRole.GATEWAY, NodeRole.STANDALONE):
        eth_ifaces = [i.name for i in env.interfaces if not i.is_wireless and i.name != "lo"]
        default_wan = eth_ifaces[0] if eth_ifaces else "eth0"
        default_lan = eth_ifaces[1:] if len(eth_ifaces) > 1 else [i for i in eth_ifaces if i != default_wan] or ["eth1"]

        if not non_interactive:
            click.echo("\n--- Network Interface Configuration ---")
            click.echo("Detected physical network adapters:")
            for iface in env.interfaces:
                if iface.name != "lo":
                    mac_str = iface.mac_address or "Unknown"
                    ip_str = iface.ip_address or "None"
                    click.echo(f"  • {iface.name} (MAC: {mac_str}, IP: {ip_str}, State: {iface.operstate.upper()})")
            wan_if = click.prompt("WAN interface (connects to upstream modem/Internet)", default=wan or default_wan)
            default_lan_str = ",".join([i for i in default_lan if i != wan_if]) or "eth1"
            lan_input = click.prompt("LAN interface(s) (comma-separated for bridge br0)", default=lan or default_lan_str)
            lan_ifs = [x.strip() for x in lan_input.split(",") if x.strip()]

            click.echo("\n--- LAN Subnet & DHCP Pool ---")
            prefix = subnet.split("/")[0].rsplit(".", 1)[0] if "/" in subnet else "192.168.1"
            lan_ip = click.prompt("Router LAN IP", default=f"{prefix}.1")
            base = lan_ip.rsplit(".", 1)[0]
            dhcp_start = click.prompt("DHCP pool start", default=f"{base}.100")
            dhcp_end = click.prompt("DHCP pool end", default=f"{base}.250")

            click.echo("\n--- DNS Subsystem ---")
            click.echo("  [1] Local Resolver (Lightweight native DNS forwarding)")
            click.echo("  [2] Technitium DNS (Advanced DNS server with built-in ad/malware blocking)")
            dns_choice = click.prompt("Selection", type=click.IntRange(1, 2), default=1 if dns_subsystem == "local" else 2)
            dns_sub = "local" if dns_choice == 1 else "technitium"

            click.echo("\n--- WAN Firewall Access ---")
            allow_ssh = click.confirm("Allow SSH remote management on WAN?", default=False)
            allow_web = click.confirm("Allow RoostOS Web Console on WAN?", default=False)
        else:
            wan_if = wan or default_wan
            lan_ifs = [x.strip() for x in lan.split(",")] if lan else default_lan
            prefix = subnet.split("/")[0].rsplit(".", 1)[0] if "/" in subnet else "192.168.1"
            lan_ip = f"{prefix}.1"
            dhcp_start = f"{prefix}.100"
            dhcp_end = f"{prefix}.250"
            dns_sub = dns_subsystem
            allow_ssh = allow_wan_ssh
            allow_web = allow_wan_web

        gw_params = GatewayConfigParams(
            wan_interface=wan_if,
            lan_interfaces=lan_ifs,
            lan_network=f"{lan_ip.rsplit('.', 1)[0]}.0/24",
            lan_ip=lan_ip,
            dhcp_start=dhcp_start,
            dhcp_end=dhcp_end,
            dns_subsystem=dns_sub,
            allow_wan_ssh=allow_ssh,
            allow_wan_web=allow_web,
        )

    ctrl_params = None
    if target_role in (NodeRole.CONTROLLER, NodeRole.STANDALONE):
        gw_ip = env.discovered_gateways[0].ip if env.discovered_gateways else None
        ctrl_params = ControllerConfigParams(adopted_gateway_ip=gw_ip)

    ws_params = None
    if target_role == NodeRole.WORKSTATION:
        ctrl_host = controller or (env.discovered_controllers[0].ip if env.discovered_controllers else "roostos.local")
        ws_params = WorkstationConfigParams(
            controller_host=ctrl_host,
            join_token=token,
        )

    edge_params = None
    if target_role == NodeRole.EDGE_GATEWAY:
        wan_if = wan or "eth0"
        edge_params = EdgeGatewayConfigParams(wan_interface=wan_if)

    wizard = SetupWizard(config_dir=config_dir, mock_install=mock)
    result = wizard.run_setup(
        role=target_role,
        gateway_params=gw_params,
        controller_params=ctrl_params,
        workstation_params=ws_params,
        edge_params=edge_params,
        env=env,
    )

    click.echo("\n--------------------------------------------------")
    if result.success:
        click.secho(f"✓ {result.message}", fg="green", bold=True)
        if result.dashboard_url:
            click.echo(f"Web Console available at: {result.dashboard_url}")
    else:
        click.secho(f"✗ Setup failed: {result.message}", fg="red", err=True)
        sys.exit(1)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
