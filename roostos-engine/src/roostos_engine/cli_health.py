"""CLI command definitions for RoostOS Health Diagnostics and Orphaned Records Scan."""

import sys
import json
import click
from typing import Optional

from roostos_engine.health import HealthChecker
from roostos_engine.orphan_detector import scan_orphaned_records, cleanup_orphaned_records
from roostos_engine.repository import YAMLConfigRepository


def run_healthcheck(config_dir: str = "/etc/roostos", fix: bool = False, mqtt: bool = False) -> None:
    click.echo("=== RoostOS System & Cluster Health Check ===")
    repo = YAMLConfigRepository(config_dir)
    checker = HealthChecker(config_dir=config_dir, mock=False)

    config = repo.get_config()
    node_id = (config.system.cluster.node_id if config.system and config.system.cluster else None) or "node-01"
    current_node = next((n for n in config.nodes if n.id == node_id), None)
    roles = [r.value if hasattr(r, "value") else str(r) for r in (current_node.roles if current_node else [])]

    report = checker.collect_health_report(
        node_id=node_id,
        node_name=current_node.name if current_node else config.system.hostname,
        roles=roles,
        dbus_connected=True,
        check_mqtt=mqtt,
    )

    status_color = "green" if report.status == "healthy" else ("yellow" if report.status == "degraded" else "red")
    click.secho(f"Overall Status:    {report.status.upper()}", fg=status_color, bold=True)
    click.echo(f"Node Name:         {report.name} ({report.node_id})")
    click.echo(f"Active Roles:      {', '.join(report.roles)}")
    click.echo(f"Telemetry:         CPU: {report.telemetry.cpu_load}% | RAM: {report.telemetry.ram_usage}% | Disk: {report.telemetry.disk_usage}% | Uptime: {report.telemetry.uptime_str}")

    click.echo("\n--- Subsystems ---")
    for sub_name, sub in report.subsystems.items():
        icon = "✓" if sub.status == "PASS" else ("⚠" if sub.status == "WARN" else "✗")
        color = "green" if sub.status == "PASS" else ("yellow" if sub.status == "WARN" else "red")
        click.secho(f"  {icon} {sub.name:<25}: {sub.status:<6} ({sub.message})", fg=color)

    if report.mqtt_bus:
        icon = "✓" if report.mqtt_bus.status == "PASS" else "✗"
        color = "green" if report.mqtt_bus.status == "PASS" else "red"
        click.secho(f"  {icon} {'MQTT Message Bus':<25}: {report.mqtt_bus.status:<6} ({report.mqtt_bus.message})", fg=color)

    # Orphaned Records Scan
    click.echo("\n--- Orphaned Records Scan ---")
    scan_res = scan_orphaned_records(config_dir=config_dir, config=config)
    if scan_res.total_orphans == 0:
        click.secho("✓ No orphaned records detected. All certificates, DHCP standby nodes, VPN peers, and device linkages are coherent.", fg="green")
    else:
        click.secho(f"⚠ {scan_res.total_orphans} Orphaned Record(s) Found:", fg="yellow", bold=True)
        for o in scan_res.orphans:
            loc_str = f" [{o.location}]" if o.location else ""
            click.echo(f"  • [{o.category}] {o.identifier}: {o.description}{loc_str}")

        if fix:
            click.echo("\nExecuting automatic cleanup of orphaned records...")
            clean_res = cleanup_orphaned_records(repo)
            for item in clean_res.get("cleaned_records", []):
                click.secho(f"  ✓ Purged: {item}", fg="green")
            for err in clean_res.get("errors", []):
                click.secho(f"  ✗ Failed: {err}", fg="red")
            click.echo("✓ Orphaned records cleanup completed.")
        else:
            click.echo("\nTip: Run with '--fix' to automatically purge orphaned credentials and clean linkages.")


def register_health_commands(main_group: click.Group, call_dbus_method_fn, run_async_fn):
    @main_group.command(name="healthcheck")
    @click.option("--config-dir", default="/etc/roostos", help="Path to config files directory")
    @click.option("--fix", is_flag=True, help="Automatically clean up detected orphaned records")
    @click.option("--mqtt", is_flag=True, help="Include active MQTT broker ping health check")
    def healthcheck_cmd(config_dir, fix, mqtt):
        """Executes diagnostic healthcheck, subsystem tests, and scans for orphaned records."""
        run_healthcheck(config_dir=config_dir, fix=fix, mqtt=mqtt)
