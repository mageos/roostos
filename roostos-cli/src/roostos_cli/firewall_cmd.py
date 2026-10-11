"""Firewall status and packet filtering commands for RoostOS."""

import os
import sys
import subprocess
from typing import List, Optional, Dict, Any, Tuple
import click
import yaml
from pydantic import BaseModel, Field


class PortForward(BaseModel):
    name: str
    wan_port: int
    lan_ip: str
    lan_port: int
    protocol: str = "tcp"
    enabled: bool = True


class InputRule(BaseModel):
    name: str
    interface: str = "*"
    protocol: str = "tcp"
    port: int
    source: Optional[str] = None
    action: str = "accept"
    enabled: bool = True


def _load_firewall_dict(config_dir: str) -> Tuple[str, Dict[str, Any]]:
    fw_path = os.path.join(config_dir, "firewall.yaml")
    os.makedirs(config_dir, exist_ok=True)
    data: Dict[str, Any] = {"firewall": {"port_forwards": [], "rules": []}}
    if os.path.exists(fw_path):
        try:
            with open(fw_path, "r") as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    data = loaded
        except Exception as e:
            click.secho(f"Error reading firewall.yaml: {e}", fg="red", err=True)
            sys.exit(1)
    if "firewall" not in data or not isinstance(data["firewall"], dict):
        data["firewall"] = {}
    return fw_path, data


def _save_firewall_dict(fw_path: str, data: Dict[str, Any]) -> None:
    try:
        with open(fw_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
    except Exception as e:
        click.secho(f"Error saving firewall configuration: {e}", fg="red", err=True)
        sys.exit(1)


@click.group(name="fw")
def fw_group() -> None:
    """Inspect and manage firewall rules, port forwarding, and device blocking."""
    pass


@fw_group.command(name="status")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def fw_status_cmd(config_dir: str) -> None:
    """Displays firewall service status, active sets, and port forward rules."""
    active_str = "inactive"
    try:
        res = subprocess.run(["systemctl", "is-active", "nftables"], capture_output=True, text=True, timeout=2)
        active_str = res.stdout.strip()
    except Exception:
        pass

    color = "green" if active_str == "active" else "red"
    click.echo("nftables Service:  ", nl=False)
    click.secho(active_str.upper(), fg=color, bold=True)

    blocked_items: List[str] = []
    try:
        res = subprocess.run(["nft", "list", "set", "inet", "filter", "blocked_clients"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                line = line.strip()
                if "elements =" in line:
                    elems = line.split("elements =")[1].strip(" {};")
                    blocked_items = [e.strip() for e in elems.split(",") if e.strip()]
    except Exception:
        pass

    click.echo(f"Blocked Clients:   {len(blocked_items)} ({', '.join(blocked_items) if blocked_items else 'None'})")

    fw_path = os.path.join(config_dir, "firewall.yaml")
    sch_path = os.path.join(config_dir, "schedules.yaml")
    target_path = fw_path if os.path.exists(fw_path) else sch_path
    forwards: List[PortForward] = []
    if os.path.exists(target_path):
        try:
            with open(target_path, "r") as f:
                data = yaml.safe_load(f) or {}
            raw_pfs = data.get("firewall", {}).get("port_forwards", []) if "firewall" in data else data.get("port_forwards", [])
            for pf in raw_pfs:
                wan = pf.get("wan_port") or pf.get("external_port", 0)
                lan_ip = pf.get("lan_ip") or pf.get("internal_ip", "")
                lan_p = pf.get("lan_port") or pf.get("internal_port", 0)
                forwards.append(PortForward(
                    name=pf.get("name", "Forward"),
                    wan_port=wan,
                    lan_ip=lan_ip,
                    lan_port=lan_p,
                    protocol=pf.get("protocol", "tcp"),
                    enabled=pf.get("enabled", True),
                ))
        except Exception:
            pass

    click.echo(f"\nPort Forwards ({len(forwards)}):")
    if forwards:
        click.secho(f"  {'NAME':<20} {'WAN PORT':<10} {'LAN TARGET':<22} {'PROTO':<8} {'ENABLED'}", bold=True)
        click.echo("  " + "-" * 70)
        for f in forwards:
            status_color = "green" if f.enabled else "yellow"
            target = f"{f.lan_ip}:{f.lan_port}"
            click.echo(f"  {f.name:<20} {f.wan_port:<10} {target:<22} {f.protocol.upper():<8} ", nl=False)
            click.secho(str(f.enabled), fg=status_color)
    else:
        click.echo("  No port forwards configured.")


@fw_group.command(name="block")
@click.argument("target")
def block_cmd(target: str) -> None:
    """Blocks an IP or MAC address from accessing WAN internet."""
    target_clean = target.lower().strip()
    click.echo(f"Blocking {target_clean}...")
    try:
        cmd = ["nft", "add", "element", "inet", "filter", "blocked_clients", f"{{ {target_clean} }}"]
        subprocess.run(cmd, check=True, capture_output=True)
        click.secho(f"✓ Blocked {target_clean} in active firewall set.", fg="green")
    except Exception as e:
        click.secho(f"Warning: Could not update nftables set directly: {e}", fg="yellow")


@fw_group.command(name="unblock")
@click.argument("target")
def unblock_cmd(target: str) -> None:
    """Unblocks an IP or MAC address from the active firewall drop set."""
    target_clean = target.lower().strip()
    click.echo(f"Unblocking {target_clean}...")
    try:
        cmd = ["nft", "delete", "element", "inet", "filter", "blocked_clients", f"{{ {target_clean} }}"]
        subprocess.run(cmd, check=True, capture_output=True)
        click.secho(f"✓ Unblocked {target_clean} from active firewall set.", fg="green")
    except Exception as e:
        click.secho(f"Warning: Could not update nftables set directly: {e}", fg="yellow")


@fw_group.command(name="forward")
@click.argument("wan_port", type=int)
@click.argument("lan_ip")
@click.argument("lan_port", type=int)
@click.option("--proto", type=click.Choice(["tcp", "udp", "both"]), default="tcp", help="Protocol")
@click.option("--name", default=None, help="Descriptive name for the forward rule")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def forward_cmd(wan_port: int, lan_ip: str, lan_port: int, proto: str, name: Optional[str], config_dir: str) -> None:
    """Configures a port forward from WAN to a local LAN device."""
    fw_path, data = _load_firewall_dict(config_dir)
    fw = data.setdefault("firewall", {})
    pfs = fw.setdefault("port_forwards", [])
    rule_name = name or f"Forward-{wan_port}-{lan_port}"
    pfs.append({
        "name": rule_name,
        "protocol": proto,
        "external_port": wan_port,
        "internal_ip": lan_ip,
        "internal_port": lan_port,
        "wan_port": wan_port,
        "lan_ip": lan_ip,
        "lan_port": lan_port,
        "enabled": True,
    })
    _save_firewall_dict(fw_path, data)
    click.secho(f"✓ Port forward rule saved: WAN:{wan_port} -> {lan_ip}:{lan_port} ({proto})", fg="green", bold=True)


@fw_group.group(name="rules")
def rules_group() -> None:
    """Inspect and manage firewall input rules."""
    pass


@rules_group.command(name="list")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def rules_list_cmd(config_dir: str) -> None:
    """Lists configured firewall input rules."""
    _, data = _load_firewall_dict(config_dir)
    raw_rules = data.get("firewall", {}).get("rules", []) or data.get("rules", [])
    rules: List[InputRule] = []
    for r in raw_rules:
        try:
            rules.append(InputRule(**r))
        except Exception:
            pass

    if not rules:
        click.echo("No firewall input rules configured.")
        return

    click.secho(f"{'NAME':<20} {'PORT':<8} {'PROTO':<10} {'IFACE':<10} {'SOURCE':<18} {'ACTION':<8} {'ENABLED'}", bold=True)
    click.echo("-" * 85)
    for r in rules:
        action_color = "green" if r.action == "accept" else "red"
        status_color = "green" if r.enabled else "yellow"
        click.echo(f"{r.name:<20} {r.port:<8} {r.protocol.upper():<10} {r.interface:<10} {r.source or '*':<18} ", nl=False)
        click.secho(f"{r.action.upper():<8} ", fg=action_color, nl=False)
        click.secho(str(r.enabled), fg=status_color)


@rules_group.command(name="add")
@click.argument("name")
@click.argument("port", type=int)
@click.option("--proto", type=click.Choice(["tcp", "udp", "tcp/udp"]), default="tcp", help="Protocol")
@click.option("--iface", default="*", help="Network interface (e.g. eth0, *, lan)")
@click.option("--source", default=None, help="Source IP or CIDR filter (e.g. 192.168.1.0/24)")
@click.option("--action", type=click.Choice(["accept", "drop"]), default="accept", help="Rule action")
@click.option("--disabled", is_flag=True, default=False, help="Add rule in disabled state")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def rules_add_cmd(
    name: str,
    port: int,
    proto: str,
    iface: str,
    source: Optional[str],
    action: str,
    disabled: bool,
    config_dir: str,
) -> None:
    """Adds or updates a firewall input rule."""
    fw_path, data = _load_firewall_dict(config_dir)
    fw = data.setdefault("firewall", {})
    rules = fw.setdefault("rules", [])

    new_rule = {
        "name": name,
        "interface": iface,
        "protocol": proto,
        "port": port,
        "source": source,
        "action": action,
        "enabled": not disabled,
    }

    replaced = False
    for i, r in enumerate(rules):
        if r.get("name") == name:
            rules[i] = new_rule
            replaced = True
            break
    if not replaced:
        rules.append(new_rule)

    _save_firewall_dict(fw_path, data)
    action_verb = "Updated" if replaced else "Added"
    click.secho(f"✓ {action_verb} firewall rule '{name}' on port {port}/{proto} ({action}).", fg="green", bold=True)


@rules_group.command(name="remove")
@click.argument("name")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def rules_remove_cmd(name: str, config_dir: str) -> None:
    """Removes a firewall input rule by name."""
    fw_path, data = _load_firewall_dict(config_dir)
    fw = data.setdefault("firewall", {})
    rules = fw.setdefault("rules", [])

    orig_len = len(rules)
    fw["rules"] = [r for r in rules if r.get("name") != name]

    if len(fw["rules"]) == orig_len:
        click.secho(f"Firewall rule '{name}' not found.", fg="yellow", err=True)
        sys.exit(1)

    _save_firewall_dict(fw_path, data)
    click.secho(f"✓ Removed firewall rule '{name}'.", fg="green")
