"""Service management and log viewer commands for RoostOS."""

import subprocess
import click
from typing import List, Optional
from pydantic import BaseModel


class ServiceStatus(BaseModel):
    name: str
    active: str
    sub: str
    enabled: str


ROOSTOS_SERVICES = [
    "roostos-node.service",
    "roostos-engine.service",
    "roostos-timeguardd.service",
    "kea-dhcp4-server.service",
    "mosquitto.service",
    "nftables.service",
]


def query_service_status(service_name: str) -> ServiceStatus:
    try:
        res = subprocess.run(
            ["systemctl", "show", service_name, "--property=ActiveState,SubState,UnitFileState"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        props = {}
        for line in res.stdout.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
        return ServiceStatus(
            name=service_name,
            active=props.get("ActiveState", "unknown"),
            sub=props.get("SubState", "unknown"),
            enabled=props.get("UnitFileState", "unknown"),
        )
    except Exception:
        return ServiceStatus(name=service_name, active="unknown", sub="unknown", enabled="unknown")


@click.group(name="service")
def service_group() -> None:
    """Manage local RoostOS systemd background services."""
    pass


@service_group.command(name="list")
def list_services_cmd() -> None:
    """Displays status of all RoostOS daemons and system services."""
    click.secho(f"{'SERVICE':<28} {'STATE':<12} {'SUBSTATE':<12} {'STARTUP'}", bold=True)
    click.echo("-" * 64)
    for srv in ROOSTOS_SERVICES:
        st = query_service_status(srv)
        color = "green" if st.active == "active" else ("yellow" if st.active == "inactive" else "red")
        click.echo(f"{st.name:<28} ", nl=False)
        click.secho(f"{st.active:<12} ", fg=color, bold=(st.active == "active"), nl=False)
        click.echo(f"{st.sub:<12} {st.enabled}")


@service_group.command(name="start")
@click.argument("service_name")
def start_service_cmd(service_name: str) -> None:
    """Starts a RoostOS daemon or service."""
    srv = service_name if service_name.endswith(".service") else f"{service_name}.service"
    click.echo(f"Starting {srv}...")
    try:
        subprocess.run(["systemctl", "start", srv], check=True)
        click.secho(f"✓ {srv} started.", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho(f"✗ Failed to start {srv}: {e}", fg="red", err=True)


@service_group.command(name="stop")
@click.argument("service_name")
def stop_service_cmd(service_name: str) -> None:
    """Stops a RoostOS daemon or service."""
    srv = service_name if service_name.endswith(".service") else f"{service_name}.service"
    click.echo(f"Stopping {srv}...")
    try:
        subprocess.run(["systemctl", "stop", srv], check=True)
        click.secho(f"✓ {srv} stopped.", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho(f"✗ Failed to stop {srv}: {e}", fg="red", err=True)


@service_group.command(name="restart")
@click.argument("service_name")
def restart_service_cmd(service_name: str) -> None:
    """Restarts a RoostOS daemon or service."""
    srv = service_name if service_name.endswith(".service") else f"{service_name}.service"
    click.echo(f"Restarting {srv}...")
    try:
        subprocess.run(["systemctl", "restart", srv], check=True)
        click.secho(f"✓ {srv} restarted.", fg="green")
    except subprocess.CalledProcessError as e:
        click.secho(f"✗ Failed to restart {srv}: {e}", fg="red", err=True)


@click.command(name="logs")
@click.argument("service_name", default="roostos-node")
@click.option("-n", "--lines", default=50, help="Number of journal log lines to display")
@click.option("-f", "--follow", is_flag=True, help="Follow log stream continuously")
def logs_cmd(service_name: str, lines: int, follow: bool) -> None:
    """Views systemd journal logs for a RoostOS service."""
    srv = service_name if service_name.endswith(".service") else f"{service_name}.service"
    args = ["journalctl", "-u", srv, "-n", str(lines), "--no-pager"]
    if follow:
        args.append("-f")
    try:
        subprocess.run(args)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        click.secho(f"Error reading journal logs: {e}", fg="red", err=True)
