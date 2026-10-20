"""CLI command definitions for RoostOS Firewall Input Rules."""

import sys
import json
import click

from roostos_engine.config import load_config_directory


def resolve_zone_to_interface(zone: str, config_dir: str = "/etc/roostos") -> str:
    """Resolves 'wan' or 'lan' zone names to actual interface/bridge names from config."""
    if zone in ("*", ""):
        return "*"
    if zone.lower() not in ("wan", "lan"):
        return zone
    try:
        config = load_config_directory(config_dir)
        for iface in config.network.interfaces:
            if iface.role == zone.lower():
                if zone.lower() == "lan" and iface.bridge:
                    return iface.bridge
                return iface.name
    except Exception:
        pass
    return zone


def resolve_interface_to_zone(iface_name: str, config_dir: str = "/etc/roostos") -> str:
    """Resolves an interface name back to its zone label for display, or returns the name as-is."""
    if iface_name == "*":
        return "*"
    try:
        config = load_config_directory(config_dir)
        for iface in config.network.interfaces:
            if iface.name == iface_name:
                return f"{iface_name} ({iface.role})"
        for bridge in config.network.bridges:
            if bridge.name == iface_name:
                return f"{iface_name} (lan)"
    except Exception:
        pass
    return iface_name


def parse_ports(port_str: str) -> list:
    """Parses a comma-separated port string into a list of integers."""
    ports = []
    for part in port_str.split(","):
        part = part.strip()
        if part:
            try:
                p = int(part)
                if not (1 <= p <= 65535):
                    raise click.BadParameter(f"Port {p} is out of range (1-65535).")
                ports.append(p)
            except ValueError:
                raise click.BadParameter(f"Invalid port value: '{part}'. Ports must be integers.")
    if not ports:
        raise click.BadParameter("At least one port must be specified.")
    return ports


def register_firewall_commands(main_group: click.Group, call_dbus_method_fn, run_async_fn):
    @main_group.group(name="firewall")
    def firewall_group():
        """Manage firewall input rules."""
        pass

    @firewall_group.command(name="list")
    @click.option("--session", is_flag=True, help="Query session bus instead of system bus")
    @click.option("--config-dir", default="/etc/roostos", help="Path to config directory for zone resolution")
    def firewall_list(session, config_dir):
        """Lists all configured firewall input rules."""
        async def run():
            rules_json = await call_dbus_method_fn("GetFirewallRules", session=session)
            rules = json.loads(rules_json)
            if not rules:
                click.echo("No firewall input rules configured.")
                return

            click.echo(f"{'NAME':<25} | {'INTERFACE':<18} | {'PROTO':<8} | {'PORT':<6} | {'SOURCE':<18} | {'ACTION':<8} | {'ENABLED'}")
            click.echo("-" * 110)
            for r in rules:
                name = r.get("name", "")
                iface = r.get("interface", "*")
                iface_display = resolve_interface_to_zone(iface, config_dir)
                proto = r.get("protocol", "tcp").upper()
                port = r.get("port", "")
                source = r.get("source") or "any"
                action = r.get("action", "accept").upper()
                enabled = "Yes" if r.get("enabled", True) else "No"
                click.echo(f"{name:<25} | {iface_display:<18} | {proto:<8} | {str(port):<6} | {source:<18} | {action:<8} | {enabled}")

        run_async_fn(run())

    @firewall_group.command(name="allow")
    @click.option("--name", default=None, help="Descriptive name for the rule (auto-generated if omitted)")
    @click.option("--interface", default="*", help="Interface or zone to match (e.g. eth0, wan, lan). Use '*' for all.")
    @click.option("--protocol", default="tcp", type=click.Choice(["tcp", "udp", "tcp/udp"], case_sensitive=False), help="Protocol to match")
    @click.option("--port", required=True, type=str, help="Destination port number(s), comma-separated (e.g. 22,80,443)")
    @click.option("--source", default="", help="Source IP/CIDR filter (e.g. 10.0.0.0/8). Omit for any source.")
    @click.option("--config-dir", default="/etc/roostos", help="Path to config directory for zone resolution")
    @click.option("--session", is_flag=True, help="Use session bus instead of system bus")
    def firewall_allow(name, interface, protocol, port, source, config_dir, session):
        """Adds or updates firewall input rules to allow traffic. Accepts multiple ports."""
        ports = parse_ports(port)
        resolved_iface = resolve_zone_to_interface(interface, config_dir)

        async def run():
            failed = []
            for p in ports:
                rule_name = name if (name and len(ports) == 1) else (f"{name}-{p}" if name else f"allow-{protocol.lower()}-{p}-{interface if interface != resolved_iface else resolved_iface}")
                success = await call_dbus_method_fn(
                    "UpdateFirewallRule", rule_name, resolved_iface, protocol, p, source, "accept", True, session=session
                )
                if success:
                    click.echo(f"✓ Rule '{rule_name}': ALLOW {protocol.upper()} port {p} on {interface}")
                else:
                    failed.append(p)
                    click.echo(f"✗ Failed to add rule for port {p}.", err=True)

            if failed:
                sys.exit(1)

        run_async_fn(run())

    @firewall_group.command(name="delete")
    @click.argument("name")
    @click.option("--session", is_flag=True, help="Use session bus instead of system bus")
    def firewall_delete(name, session):
        """Deletes a firewall input rule by name."""
        async def run():
            success = await call_dbus_method_fn("DeleteFirewallRule", name, session=session)
            if success:
                click.echo(f"Firewall rule '{name}' deleted successfully.")
            else:
                click.echo(f"Failed to delete firewall rule '{name}'.", err=True)
                sys.exit(1)

        run_async_fn(run())
