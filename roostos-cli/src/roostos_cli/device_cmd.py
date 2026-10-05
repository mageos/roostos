"""Device and family management commands for RoostOS."""

import os
import sys
from typing import List, Optional, Dict, Any
import click
import yaml
from pydantic import BaseModel, Field


class DeviceEntry(BaseModel):
    id: str
    name: str
    mac: str
    static_ip: Optional[str] = None
    owner: Optional[str] = None
    quarantined: bool = False
    paused: bool = False


class PersonEntry(BaseModel):
    id: str
    name: str
    role: str = "child"
    devices: List[str] = Field(default_factory=list)


@click.group(name="devices")
def devices_group() -> None:
    """Manage registered client devices and pause internet access."""
    pass


@click.group(name="people")
def people_group() -> None:
    """Manage family member profiles, screen time, and assigned devices."""
    pass


@devices_group.command(name="list")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def list_devices_cmd(config_dir: str) -> None:
    """Displays all known and registered network devices."""
    dev_path = os.path.join(config_dir, "devices.yaml")
    devices: List[DeviceEntry] = []
    if os.path.exists(dev_path):
        try:
            with open(dev_path, "r") as f:
                data = yaml.safe_load(f)
            for d in data.get("devices", []):
                devices.append(DeviceEntry(**d))
        except Exception as e:
            click.secho(f"Warning: Could not read devices.yaml: {e}", fg="yellow")

    if not devices:
        click.echo("No devices registered in devices.yaml yet.")
        return

    click.secho(f"{'DEVICE ID':<14} {'NAME':<20} {'MAC ADDRESS':<20} {'STATIC IP':<16} {'STATUS'}", bold=True)
    click.echo("-" * 80)
    for d in devices:
        status_str = "PAUSED" if d.paused else ("QUARANTINED" if d.quarantined else "ACTIVE")
        status_color = "red" if d.paused else ("yellow" if d.quarantined else "green")
        click.echo(f"{d.id:<14} {d.name:<20} {d.mac:<20} {d.static_ip or 'dynamic':<16} ", nl=False)
        click.secho(status_str, fg=status_color, bold=d.paused)


@devices_group.command(name="pause")
@click.argument("target")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def pause_device_cmd(target: str, config_dir: str) -> None:
    """Pauses internet access for a device by ID or MAC address."""
    _toggle_device_pause(target, True, config_dir)


@devices_group.command(name="resume")
@click.argument("target")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def resume_device_cmd(target: str, config_dir: str) -> None:
    """Resumes internet access for a paused device by ID or MAC address."""
    _toggle_device_pause(target, False, config_dir)


def _toggle_device_pause(target: str, pause: bool, config_dir: str) -> None:
    dev_path = os.path.join(config_dir, "devices.yaml")
    if not os.path.exists(dev_path):
        click.secho("Error: devices.yaml does not exist.", fg="red", err=True)
        sys.exit(1)

    try:
        with open(dev_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        click.secho(f"Error reading devices.yaml: {e}", fg="red", err=True)
        sys.exit(1)

    target_clean = target.lower().strip()
    found = False
    for d in data.get("devices", []):
        if d.get("id", "").lower() == target_clean or d.get("mac", "").lower() == target_clean:
            d["paused"] = pause
            found = True
            dev_name = d.get("name", target)
            break

    if not found:
        click.secho(f"Device '{target}' not found in devices.yaml.", fg="red", err=True)
        sys.exit(1)

    try:
        with open(dev_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        action = "paused" if pause else "resumed"
        color = "yellow" if pause else "green"
        click.secho(f"✓ Device '{dev_name}' ({target}) internet access {action}.", fg=color, bold=True)
    except Exception as e:
        click.secho(f"Error updating devices.yaml: {e}", fg="red", err=True)
        sys.exit(1)


@people_group.command(name="list")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def list_people_cmd(config_dir: str) -> None:
    """Displays registered family members and managed people."""
    dev_path = os.path.join(config_dir, "devices.yaml")
    people: List[PersonEntry] = []
    if os.path.exists(dev_path):
        try:
            with open(dev_path, "r") as f:
                data = yaml.safe_load(f)
            for p in data.get("people", []):
                people.append(PersonEntry(**p))
        except Exception as e:
            click.secho(f"Warning: Could not read people in devices.yaml: {e}", fg="yellow")

    if not people:
        click.echo("No people configured in devices.yaml yet.")
        return

    click.secho(f"{'PERSON ID':<16} {'NAME':<24} {'ROLE':<12} {'DEVICES'}", bold=True)
    click.echo("-" * 70)
    for p in people:
        devs = ", ".join(p.devices) if p.devices else "none"
        click.echo(f"{p.id:<16} {p.name:<24} {p.role:<12} {devs}")
