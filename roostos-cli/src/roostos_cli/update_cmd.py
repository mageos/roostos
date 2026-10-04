"""CLI commands for checking, scheduling, and installing RoostOS system updates."""

import click
from roostos_engine.update_manager import UpdateManager


@click.group(name="update")
def update_group() -> None:
    """Manage OS package updates, security patches, and reboot schedules."""
    pass


@update_group.command(name="status")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def status_cmd(config_dir: str) -> None:
    """Displays update availability and reboot requirements."""
    mgr = UpdateManager(config_dir=config_dir)
    res = mgr.check_updates(refresh_cache=False)

    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("              RoostOS System Updates              ", fg="cyan", bold=True)
    click.secho("==================================================", fg="cyan", bold=True)
    click.echo(f"Package Manager:   {mgr.detect_package_manager().upper()}")
    click.echo(f"Updates Available: {res.updates_available}")
    click.echo(f"Security Updates:  {res.security_updates}")
    click.echo(f"Reboot Required:   {'YES (System reboot pending)' if res.reboot_required else 'No'}")
    click.echo(f"Reboot Window:     {mgr.get_next_reboot_window_time()}")
    if res.last_check_time:
        click.echo(f"Last Check Time:   {res.last_check_time}")

    if res.packages:
        click.echo("\nAvailable Packages:")
        for p in res.packages[:10]:
            sec_tag = " [SECURITY]" if p.is_security else ""
            click.echo(f"  • {p.package_name}: {p.current_version} -> {p.new_version}{sec_tag}")
        if len(res.packages) > 10:
            click.echo(f"  ... and {len(res.packages) - 10} more.")


@update_group.command(name="check")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def check_cmd(config_dir: str) -> None:
    """Refreshes package repositories and checks for new updates."""
    click.secho("Refreshing repositories and checking for updates...", fg="cyan")
    mgr = UpdateManager(config_dir=config_dir)
    res = mgr.check_updates(refresh_cache=True)

    if res.updates_available > 0:
        click.secho(f"Found {res.updates_available} update(s) ({res.security_updates} security).", fg="yellow")
    else:
        click.secho("System is up to date. No updates available.", fg="green")


@update_group.command(name="install")
@click.option("--security-only", is_flag=True, help="Only apply security updates")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def install_cmd(security_only: bool, config_dir: str) -> None:
    """Backs up system configuration and installs package updates."""
    click.secho("Creating pre-update backup and applying updates...", fg="cyan")
    mgr = UpdateManager(config_dir=config_dir)
    res = mgr.install_updates(security_only=security_only)

    if res.success:
        click.secho(f"✓ Successfully installed updates ({res.packages_updated} packages updated).", fg="green", bold=True)
        if res.backup_path:
            click.echo(f"Pre-update backup saved to: {res.backup_path}")
        if res.reboot_scheduled_for:
            click.secho(f"Reboot scheduled for: {res.reboot_scheduled_for}", fg="yellow")
        elif res.reboot_required:
            click.secho("Notice: System reboot is required to apply changes.", fg="yellow")
    else:
        click.secho(f"✗ Update installation failed: {res.error or 'Unknown error'}", fg="red", err=True)
