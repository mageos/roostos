import sys
import json
import asyncio
import click
from typing import List, Dict, Any

from dbus_next.aio import MessageBus
from dbus_next import BusType

from roostos_engine.config import load_config_directory

BUS_NAME = "org.roostos.Daemon"
OBJECT_PATH = "/org/roostos/Daemon"

# Maps CamelCase D-Bus definitions to dbus-next's runtime normalized snake_case PEP8 lookups.
METHOD_MAP = {
    "GetConfig": "get_config",
    "GetUsers": "get_users",
    "GetPeople": "get_people",
    "GetBuildings": "get_buildings",
    "GetRooms": "get_rooms",
    "GetDevices": "get_devices",
    "GetActiveLeases": "get_active_leases",
    "RegisterLease": "register_lease",
    "ReleaseLease": "release_lease",
    "GetSchedules": "get_schedules",
    "UpdateDevice": "update_device",
    "DeleteDevice": "delete_device",
    "GrantTimeExtension": "grant_time_extension",
    "RemoveTimeExtension": "remove_time_extension",
    "CreateBackup": "create_backup",
    "RestoreBackup": "restore_backup",
    "RebootHost": "reboot_host",
    "GetPendingUPnPRequests": "get_pending_u_pn_p_requests",
    "RegisterUPnPRequest": "register_u_pn_p_request",
    "ApproveUPnPRequest": "approve_u_pn_p_request",
    "RejectUPnPRequest": "reject_u_pn_p_request",
    "GetFirewallRules": "get_firewall_rules",
    "UpdateFirewallRule": "update_firewall_rule",
    "DeleteFirewallRule": "delete_firewall_rule"
}

PROPERTY_MAP = {
    "RebootRequired": "reboot_required"
}

# Helper function to run async D-Bus commands from click sync wrapper
def run_async(coro):
    try:
        return asyncio.run(coro)
    except Exception as e:
        click.echo(f"Error communicating with RoostOS Daemon over D-Bus: {e}", err=True)
        sys.exit(1)

async def call_dbus_method(method_name: str, *args, session: bool = False):
    bus_type = BusType.SESSION if session else BusType.SYSTEM
    bus = await MessageBus(bus_type=bus_type).connect()
    
    # Introspect service and fetch proxy interface
    introspection = await bus.introspect(BUS_NAME, OBJECT_PATH)
    proxy_object = bus.get_proxy_object(BUS_NAME, OBJECT_PATH, introspection)
    interface = proxy_object.get_interface(BUS_NAME)
    
    # Resolve normalized method name and execute
    normalized_name = METHOD_MAP.get(method_name, method_name.lower())
    func = getattr(interface, f"call_{normalized_name}")
    res = await func(*args)
    
    bus.disconnect()
    return res

async def get_dbus_property(property_name: str, session: bool = False):
    bus_type = BusType.SESSION if session else BusType.SYSTEM
    bus = await MessageBus(bus_type=bus_type).connect()
    introspection = await bus.introspect(BUS_NAME, OBJECT_PATH)
    proxy_object = bus.get_proxy_object(BUS_NAME, OBJECT_PATH, introspection)
    interface = proxy_object.get_interface(BUS_NAME)
    
    # Resolve normalized property name
    normalized_name = PROPERTY_MAP.get(property_name, property_name.lower())
    func = getattr(interface, f"get_{normalized_name}")
    res = await func()
    
    bus.disconnect()
    return res

# ==========================================
# Click CLI Definitions
# ==========================================

@click.group()
def main():
    """RoostOS Core CLI management utility."""
    pass

@main.group(name="config")
def config_group():
    """Manage local split configuration files."""
    pass

@config_group.command(name="validate")
@click.option("--dir", default="/etc/roostos", help="Path to config files directory")
def config_validate(dir):
    """Loads and validates all configuration files inside the directory."""
    click.echo(f"Validating configuration directory: {dir}...")
    try:
        config = load_config_directory(dir)
        click.echo("✓ Validation Success! All split configuration files are valid and coherent.")
        click.echo(f"  Hostname: {config.system.hostname}")
        click.echo(f"  Registered users: {len(config.users)}")
        click.echo(f"  Registered devices: {len(config.devices)}")
        click.echo(f"  Port forwards: {len(config.firewall.port_forwards)}")
        click.echo(f"  Schedules: {len(config.firewall.schedules)}")
        click.echo(f"  Active plugins: {len([p for p in config.plugins if p.enabled])}")
        
    except Exception as e:
        click.echo("✗ Validation Failed! Found schema or linkage errors:", err=True)
        click.echo(f"  Error: {e}", err=True)
        sys.exit(1)

@main.command(name="status")
@click.option("--session", is_flag=True, help="Query session bus instead of system bus")
def daemon_status(session):
    """Checks the status of the local running roostd daemon."""
    async def run():
        cfg_json = await call_dbus_method("GetConfig", session=session)
        reboot_req = await get_dbus_property("RebootRequired", session=session)
        leases_json = await call_dbus_method("GetActiveLeases", session=session)
        
        cfg = json.loads(cfg_json)
        leases = json.loads(leases_json)
        
        click.echo("RoostOS Engine Daemon: RUNNING")
        click.echo(f"  Hostname: {cfg['system']['hostname']}")
        click.echo(f"  Timezone: {cfg['system']['timezone']}")
        click.echo(f"  Pending Reboot: {'Yes' if reboot_req else 'No'}")
        click.echo(f"  Active DHCP leases: {len(leases)}")
    
    run_async(run())

@device_group := main.group(name="device")
def device_group():
    """Manage registered network devices."""
    pass

@device_group.command(name="list")
@click.option("--session", is_flag=True, help="Query session bus instead of system bus")
def device_list(session):
    """Lists all registered devices from the running daemon."""
    async def run():
        devices_json = await call_dbus_method("GetDevices", session=session)
        devices = json.loads(devices_json)
        
        if not devices:
            click.echo("No devices registered.")
            return

        click.echo(f"{'MAC ADDRESS':<20} | {'NAME':<20} | {'OWNER':<15} | {'STATIC IP':<15} | {'UPnP TRUSTED'}")
        click.echo("-" * 85)
        for d in devices:
            mac = d.get("mac", "")
            name = d.get("name", "")
            owner = d.get("owner") or "-"
            static_ip = d.get("static_ip") or "-"
            upnp = "Yes" if d.get("upnp_trusted") else "No"
            click.echo(f"{mac:<20} | {name:<20} | {owner:<15} | {static_ip:<15} | {upnp}")

    run_async(run())

@device_group.command(name="register")
@click.argument("mac")
@click.argument("name")
@click.option("--owner", default="", help="Person ID linking to this device")
@click.option("--location", default="", help="Room or Building ID location")
@click.option("--tags", default="", help="Comma-separated list of tags")
@click.option("--static-ip", default="", help="Static DHCP IP reservation")
@click.option("--upnp-trusted", is_flag=True, help="Trust all UPnP mapping requests")
@click.option("--session", is_flag=True, help="Use session bus instead of system bus")
def device_register(mac, name, owner, location, tags, static_ip, upnp_trusted, session):
    """Registers or updates a device profile in devices.yaml."""
    async def run():
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        success = await call_dbus_method(
            "UpdateDevice", 
            mac, name, owner, location, tag_list, static_ip, upnp_trusted, "",
            session=session
        )
        if success:
            click.echo(f"Successfully registered device {mac} ({name}).")
        else:
            click.echo(f"Failed to register device {mac}.", err=True)
            sys.exit(1)

    run_async(run())

@device_group.command(name="deregister")
@click.argument("mac")
@click.option("--session", is_flag=True, help="Use session bus instead of system bus")
def device_deregister(mac, session):
    """Removes a registered device MAC from devices.yaml."""
    async def run():
        success = await call_dbus_method("DeleteDevice", mac, session=session)
        if success:
            click.echo(f"Successfully deregistered device {mac}.")
        else:
            click.echo(f"Failed to deregistered device {mac}.", err=True)
            sys.exit(1)

    run_async(run())

@bypass_group := main.group(name="bypass")
def bypass_group():
    """Manage dynamic schedule bypasses/time-allowances."""
    pass

@bypass_group.command(name="grant")
@click.argument("mac")
@click.argument("duration", type=int)
@click.option("--session", is_flag=True, help="Use session bus instead of system bus")
def bypass_grant(mac, duration, session):
    """Grants a temporary schedule override (in minutes) to a MAC address."""
    async def run():
        success = await call_dbus_method("GrantTimeExtension", mac, duration * 60, session=session)
        if success:
            click.echo(f"Granted {duration} minute bypass extension for {mac}.")
        else:
            click.echo(f"Failed to grant bypass for {mac}.", err=True)
            sys.exit(1)

    run_async(run())

@bypass_group.command(name="revoke")
@click.argument("mac")
@click.option("--session", is_flag=True, help="Use session bus instead of system bus")
def bypass_revoke(mac, session):
    """Revokes any active schedule bypass extension for a MAC address."""
    async def run():
        success = await call_dbus_method("RemoveTimeExtension", mac, session=session)
        if success:
            click.echo(f"Revoked bypass extension for {mac}.")
        else:
            click.echo(f"Failed to revoke bypass for {mac}.", err=True)
            sys.exit(1)

    run_async(run())

@firewall_group := main.group(name="firewall")
def firewall_group():
    """Manage firewall input rules."""
    pass

def resolve_zone_to_interface(zone: str, config_dir: str = "/etc/roostos") -> str:
    """Resolves 'wan' or 'lan' zone names to actual interface/bridge names from config."""
    if zone in ("*", ""):
        return "*"
    if zone.lower() not in ("wan", "lan"):
        return zone  # Treat as literal interface name
    try:
        config = load_config_directory(config_dir)
        for iface in config.network.interfaces:
            if iface.role == zone.lower():
                if zone.lower() == "lan" and iface.bridge:
                    return iface.bridge  # Use bridge name for LAN firewall rules
                return iface.name
    except Exception:
        pass
    return zone  # Fallback: treat as literal

def resolve_interface_to_zone(iface_name: str, config_dir: str = "/etc/roostos") -> str:
    """Resolves an interface name back to its zone label for display, or returns the name as-is."""
    if iface_name == "*":
        return "*"
    try:
        config = load_config_directory(config_dir)
        # Check direct interface match
        for iface in config.network.interfaces:
            if iface.name == iface_name:
                return f"{iface_name} ({iface.role})"
        # Check bridge match
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

@firewall_group.command(name="list")
@click.option("--session", is_flag=True, help="Query session bus instead of system bus")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory for zone resolution")
def firewall_list(session, config_dir):
    """Lists all configured firewall input rules."""
    async def run():
        rules_json = await call_dbus_method("GetFirewallRules", session=session)
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

    run_async(run())

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
            # Generate rule name
            if name:
                rule_name = name if len(ports) == 1 else f"{name}-{p}"
            else:
                iface_label = interface if interface != resolved_iface else resolved_iface
                rule_name = f"allow-{protocol.lower()}-{p}-{iface_label}"

            success = await call_dbus_method(
                "UpdateFirewallRule",
                rule_name, resolved_iface, protocol, p, source, "accept", True,
                session=session
            )
            if success:
                click.echo(f"✓ Rule '{rule_name}': ALLOW {protocol.upper()} port {p} on {interface}")
            else:
                failed.append(p)
                click.echo(f"✗ Failed to add rule for port {p}.", err=True)

        if failed:
            sys.exit(1)

    run_async(run())

@firewall_group.command(name="delete")
@click.argument("name")
@click.option("--session", is_flag=True, help="Use session bus instead of system bus")
def firewall_delete(name, session):
    """Deletes a firewall input rule by name."""
    async def run():
        success = await call_dbus_method("DeleteFirewallRule", name, session=session)
        if success:
            click.echo(f"Firewall rule '{name}' deleted successfully.")
        else:
            click.echo(f"Failed to delete firewall rule '{name}'.", err=True)
            sys.exit(1)

    run_async(run())

if __name__ == "__main__":
    main()
