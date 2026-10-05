"""Firewall status and packet filtering commands for RoostOS."""

import os
import sys
import subprocess
from typing import List, Optional, Dict, Any
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


@click.group(name="fw")
def fw_group() -> None:
    """Inspect and manage firewall rules, port forwarding, and device blocking."""
    pass


@fw_group.command(name="status")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def fw_status_cmd(config_dir: str) -> None:
    """Displays firewall service status, active sets, and port forward rules."""
    # 1. Query nftables service
    active_str = "inactive"
    try:
        res = subprocess.run(["systemctl", "is-active", "nftables"], capture_output=True, text=True, timeout=2)
        active_str = res.stdout.strip()
    except Exception:
        pass

    color = "green" if active_str == "active" else "red"
    click.echo("nftables Service:  ", nl=False)
    click.secho(active_str.upper(), fg=color, bold=True)

    # 2. Check blocked clients set
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

    # 3. Read port forwards from firewall.yaml (fallback to schedules.yaml)
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
        # Attempt to add to active nftables blocked set
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
    fw_path = os.path.join(config_dir, "firewall.yaml")
    os.makedirs(config_dir, exist_ok=True)
    data: Dict[str, Any] = {"firewall": {"port_forwards": [], "rules": []}}
    if os.path.exists(fw_path):
        try:
            with open(fw_path, "r") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    data = loaded
        except Exception as e:
            click.secho(f"Error reading firewall.yaml: {e}", fg="red", err=True)
            sys.exit(1)

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

    try:
        with open(fw_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        click.secho(f"✓ Port forward rule saved: WAN:{wan_port} -> {lan_ip}:{lan_port} ({proto})", fg="green", bold=True)
    except Exception as e:
        click.secho(f"Error saving rule: {e}", fg="red", err=True)
        sys.exit(1)
