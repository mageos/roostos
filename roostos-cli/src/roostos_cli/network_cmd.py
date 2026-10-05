"""Network interface and DHCP lease management commands for RoostOS."""

import os
import sys
import json
import sqlite3
import subprocess
from typing import List, Optional, Dict, Any
import click
import yaml
from pydantic import BaseModel, Field


class InterfaceDetails(BaseModel):
    name: str
    role: str = "unassigned"
    operstate: str = "unknown"
    ip: Optional[str] = None
    mac: Optional[str] = None
    mtu: Optional[int] = None


class LeaseRecord(BaseModel):
    mac: str
    ip: str
    hostname: Optional[str] = "Unknown"
    quarantined: bool = False
    last_seen: Optional[str] = None


@click.group(name="net")
def net_group() -> None:
    """Inspect and manage physical and virtual network interfaces."""
    pass


@click.group(name="dhcp")
def dhcp_group() -> None:
    """Manage DHCP server leases, pools, and static IP reservations."""
    pass


@net_group.command(name="list")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def list_interfaces_cmd(config_dir: str) -> None:
    """Lists host network adapters, configured roles, and active IP addresses."""
    # 1. Read configured roles from network.yaml
    role_map: Dict[str, str] = {}
    net_path = os.path.join(config_dir, "network.yaml")
    if os.path.exists(net_path):
        try:
            with open(net_path, "r") as f:
                data = yaml.safe_load(f)
            for iface in data.get("network", {}).get("interfaces", []):
                role_map[iface.get("name", "")] = iface.get("role", "lan")
            for br in data.get("network", {}).get("bridges", []):
                role_map[br.get("name", "")] = "bridge"
        except Exception:
            pass

    # 2. Query system interfaces via `ip -j addr show`
    ifaces: List[InterfaceDetails] = []
    try:
        res = subprocess.run(["ip", "-j", "addr", "show"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            for item in json.loads(res.stdout):
                name = item.get("ifname", "")
                if name == "lo":
                    continue
                operstate = item.get("operstate", "UNKNOWN")
                mac = item.get("address", "")
                mtu = item.get("mtu")
                ipv4 = None
                for addr in item.get("addr_info", []):
                    if addr.get("family") == "inet":
                        ipv4 = f"{addr.get('local')}/{addr.get('prefixlen')}"
                        break
                ifaces.append(
                    InterfaceDetails(
                        name=name,
                        role=role_map.get(name, "unassigned"),
                        operstate=operstate,
                        ip=ipv4,
                        mac=mac,
                        mtu=mtu,
                    )
                )
    except Exception as e:
        click.secho(f"Warning: Could not query network interfaces: {e}", fg="yellow", err=True)

    click.secho(f"{'INTERFACE':<16} {'ROLE':<12} {'STATE':<10} {'IP ADDRESS':<20} {'MAC ADDRESS'}", bold=True)
    click.echo("-" * 75)
    for iface in ifaces:
        state_color = "green" if iface.operstate.upper() == "UP" else "yellow"
        click.echo(f"{iface.name:<16} {iface.role:<12} ", nl=False)
        click.secho(f"{iface.operstate.upper():<10} ", fg=state_color, nl=False)
        click.echo(f"{iface.ip or 'None':<20} {iface.mac or 'None'}")


@dhcp_group.command(name="leases")
@click.option("--db-path", default="/var/lib/roostos/state.db", help="Path to state SQLite database")
def list_leases_cmd(db_path: str) -> None:
    """Displays active and historic DHCP leases and quarantined devices."""
    leases: List[LeaseRecord] = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT mac, ip, hostname, quarantined, last_seen FROM active_leases ORDER BY last_seen DESC")
            for row in cursor.fetchall():
                leases.append(
                    LeaseRecord(
                        mac=row["mac"],
                        ip=row["ip"],
                        hostname=row["hostname"] or "Unknown",
                        quarantined=bool(row["quarantined"]),
                        last_seen=row["last_seen"],
                    )
                )
            conn.close()
        except Exception as e:
            click.secho(f"Warning: Could not read state database: {e}", fg="yellow")

    if not leases:
        click.echo("No active DHCP leases recorded in state database.")
        return

    click.secho(f"{'IP ADDRESS':<16} {'MAC ADDRESS':<20} {'STATUS':<12} {'LAST SEEN':<22} {'HOSTNAME'}", bold=True)
    click.echo("-" * 85)
    for l in leases:
        status_label = "QUARANTINED" if l.quarantined else "ACTIVE"
        status_color = "red" if l.quarantined else "green"
        click.echo(f"{l.ip:<16} {l.mac:<20} ", nl=False)
        click.secho(f"{status_label:<12} ", fg=status_color, bold=l.quarantined, nl=False)
        click.echo(f"{l.last_seen or 'Unknown':<22} {l.hostname}")


@dhcp_group.command(name="reserve")
@click.argument("mac")
@click.argument("ip")
@click.option("--name", default=None, help="Friendly name / hostname for the device")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def reserve_ip_cmd(mac: str, ip: str, name: Optional[str], config_dir: str) -> None:
    """Creates a static DHCP IP reservation for a given MAC address."""
    dev_path = os.path.join(config_dir, "devices.yaml")
    os.makedirs(config_dir, exist_ok=True)
    data: Dict[str, Any] = {"devices": []}
    if os.path.exists(dev_path):
        try:
            with open(dev_path, "r") as f:
                loaded = yaml.safe_load(f)
                if loaded and "devices" in loaded:
                    data = loaded
        except Exception as e:
            click.secho(f"Error reading devices.yaml: {e}", fg="red", err=True)
            sys.exit(1)

    devices = data.get("devices", [])
    found = False
    clean_mac = mac.lower().strip()
    for d in devices:
        if d.get("mac", "").lower() == clean_mac:
            d["static_ip"] = ip
            if name:
                d["name"] = name
            found = True
            break

    if not found:
        dev_id = f"dev-{clean_mac.replace(':', '')[-6:]}"
        devices.append({
            "id": dev_id,
            "name": name or f"Device {clean_mac[-5:]}",
            "mac": clean_mac,
            "static_ip": ip,
            "quarantined": False,
        })

    data["devices"] = devices
    try:
        with open(dev_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        click.secho(f"✓ Static reservation saved: {clean_mac} -> {ip}", fg="green", bold=True)
        click.echo("Restarting DHCP daemon to apply changes...")
        subprocess.run(["systemctl", "restart", "kea-dhcp4-server"], check=False, capture_output=True)
    except Exception as e:
        click.secho(f"Error saving reservation: {e}", fg="red", err=True)
        sys.exit(1)
