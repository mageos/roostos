"""CLI commands for managing RoostOS apps, source builds, and local catalogs."""

import os
import sys
from typing import Optional
import click

from roostos_engine.repository import YAMLConfigRepository
from roostos_engine.catalog_manager import CatalogManager
from roostos_engine.models.catalog import (
    SourceBuildSpec,
    ImportFromSourceRequest,
    InstallFromSourceRequest,
    InstallAppRequest,
)
from roostos_engine.models.plugins import PluginsConfig
from roostos_engine.source_builder import SourceBuilder
from roostos_engine.ingress_helper import provision_ingress_route


@click.group(name="app")
def app_group() -> None:
    """Manage RoostOS applications, package manifests, and source builds."""
    pass


@app_group.command(name="inspect")
@click.argument("source", required=True)
@click.option("--ref", default="main", help="Git branch, tag, or commit ref")
def inspect_app_cmd(source: str, ref: str) -> None:
    """Inspects a roost-app.yaml manifest from a git repository or local directory."""
    click.secho(f"Inspecting package manifest from: {source} (ref: {ref})...", fg="cyan")
    builder = SourceBuilder()
    try:
        repo_dir = builder.clone_or_resolve_source(source, git_ref=ref)
        manifest = builder.load_manifest(repo_dir)
        if not manifest:
            click.secho("Error: No roost-app.yaml manifest or Dockerfile found.", fg="red", err=True)
            sys.exit(1)

        click.secho("==================================================", fg="green", bold=True)
        click.secho(f"  Package: {manifest.name} ({manifest.id})", fg="green", bold=True)
        click.secho("==================================================", fg="green")
        click.echo(f"Version:      {manifest.version}")
        click.echo(f"Category:     {manifest.category}")
        click.echo(f"Author:       {manifest.author or 'Unknown'}")
        click.echo(f"Description:  {manifest.description or 'None'}")
        if manifest.build:
            click.echo(f"Dockerfile:   {manifest.build.dockerfile}")
            click.echo(f"Context:      {manifest.build.context_path}")
            sb = manifest.build.sandbox
            click.secho("Build Sandbox:", fg="yellow")
            click.echo(f"  Network Req: {'YES (requires approval)' if sb.network_required else 'No (offline)'}")
            if sb.network_required:
                click.echo(f"  Endpoints:   {', '.join(sb.allowed_endpoints) or 'None'}")
                if sb.network_justification:
                    click.echo(f"  Justification: {sb.network_justification}")
            click.echo(f"  Memory Limit: {sb.max_memory_mb} MB")
            click.echo(f"  CPU Quota:   {sb.max_cpu_cores} cores")
            click.echo(f"  Timeout:     {sb.timeout_seconds}s")
            click.echo(f"  Hardened:    {'Yes (no-new-privileges, ulimits)' if sb.no_new_privileges else 'Standard'}")
        if manifest.container:
            ports = [f"{p.host_port}➔{p.container_port}" for p in manifest.container.ports]
            click.echo(f"Ports:        {', '.join(ports) or 'None'}")
            vols = [f"{v.host_path}➔{v.container_path}" for v in manifest.container.volumes]
            click.echo(f"Volumes:      {', '.join(vols) or 'None'}")
    except Exception as e:
        click.secho(f"Error inspecting source: {e}", fg="red", err=True)
        sys.exit(1)


@app_group.command(name="import")
@click.argument("source", required=True)
@click.option("--ref", default="main", help="Git branch, tag, or commit ref")
@click.option("--app-id", default=None, help="Override application identifier")
@click.option("--config-dir", default="/etc/roostos", help="Configuration files directory")
@click.option("--approve-network/--deny-network", default=None, help="Approve or deny build network access")
def import_app_cmd(
    source: str, ref: str, app_id: Optional[str], config_dir: str, approve_network: Optional[bool]
) -> None:
    """Imports and builds an application from source into the local catalog."""
    click.secho(f"Importing application from: {source} (ref: {ref})...", fg="cyan")
    builder = SourceBuilder()
    mgr = CatalogManager(config_dir=config_dir)

    if approve_network is None:
        try:
            repo_dir = builder.clone_or_resolve_source(source, git_ref=ref, dir_name_override=app_id)
            manifest = builder.load_manifest(repo_dir)
            if manifest and manifest.build and manifest.build.sandbox.network_required:
                click.secho("⚠️  Build requires external network access to:", fg="yellow", bold=True)
                for ep in manifest.build.sandbox.allowed_endpoints:
                    click.echo(f"    - {ep}")
                if manifest.build.sandbox.network_justification:
                    click.echo(f"  Justification: {manifest.build.sandbox.network_justification}")
                approve_network = click.confirm("Do you approve network access for this build?", default=False)
        except Exception:
            pass

    req = ImportFromSourceRequest(
        source_url_or_path=source, git_ref=ref, app_id_override=app_id, approve_network=bool(approve_network)
    )
    try:
        app_entry, logs = builder.import_to_catalog(req, mgr)
        click.secho(f"Successfully imported '{app_entry.name}' into local catalog!", fg="green", bold=True)
        click.echo(f"  ID:     {app_entry.id}")
        click.echo(f"  Image:  {app_entry.container.image}")
        click.echo(f"  Commit: {app_entry.last_commit_built or 'local'}")
        click.echo(f"\nRun 'roostos app install --app-id {app_entry.id}' to deploy.")
    except Exception as e:
        click.secho(f"Import failed: {e}", fg="red", err=True)
        sys.exit(1)


@app_group.command(name="check-updates")
@click.option("--config-dir", default="/etc/roostos", help="Configuration files directory")
def check_updates_cmd(config_dir: str) -> None:
    """Checks if git updates are available for imported catalog applications."""
    mgr = CatalogManager(config_dir=config_dir)
    builder = SourceBuilder()
    local_index = mgr.get_local_catalog()
    if not local_index.applications:
        click.echo("No imported applications in local catalog.")
        return

    click.secho("Checking for imported app updates...", fg="cyan")
    for app in local_index.applications:
        if not app.source_repo:
            continue
        has_update, remote_sha = builder.check_app_updates(app)
        if has_update:
            click.secho(f"  ⚡ {app.name} ({app.id}): Update available! ({app.last_commit_built} ➔ {remote_sha})", fg="yellow", bold=True)
        else:
            click.echo(f"  ✓ {app.name} ({app.id}): Up to date ({app.last_commit_built or 'local'})")


@app_group.command(name="install")
@click.option("--app-id", default=None, help="Application ID from catalog to install")
@click.option("--source", default=None, help="Git repo URL or local folder path")
@click.option("--ref", default="main", help="Git branch, tag, or commit ref")
@click.option("--expose-domain", default=None, help="Expose via Edge Gateway with public domain")
@click.option("--config-dir", default="/etc/roostos", help="Configuration files directory")
@click.option("--approve-network/--deny-network", default=None, help="Approve or deny build network access")
def install_app_cmd(
    app_id: Optional[str], source: Optional[str], ref: str, expose_domain: Optional[str],
    config_dir: str, approve_network: Optional[bool],
) -> None:
    """Installs an application from catalog (or builds directly from source)."""
    repo = YAMLConfigRepository(config_dir=config_dir)
    mgr = CatalogManager(config_dir=config_dir)

    # 1. Install from catalog if app_id provided and no source specified
    if app_id and not source:
        apps = mgr.get_available_apps()
        app = next((a for a in apps if a.id == app_id), None)
        if not app:
            click.secho(f"Error: Application '{app_id}' not found in any catalog.", fg="red", err=True)
            sys.exit(1)
        req = InstallAppRequest(app_id=app.id, catalog_id=app.catalog_id)
        plugin = mgr.create_plugin_from_app(app, req)
        config = repo.get_config()
        existing = [p for p in config.plugins if p.id != plugin.id]
        existing.append(plugin)
        repo.save_plugins_config(PluginsConfig(plugins=existing))
        click.secho(f"Successfully installed '{plugin.name}' ({plugin.id}) from catalog!", fg="green", bold=True)
        return

    # 2. Build and install from source
    if not source:
        click.secho("Error: Either --app-id or --source is required.", fg="red", err=True)
        sys.exit(1)

    builder = SourceBuilder()
    req_src = InstallFromSourceRequest(
        source_url_or_path=source, git_ref=ref, app_id_override=app_id,
        approve_network=bool(approve_network), expose_edge_ingress=bool(expose_domain),
        ingress_domain=expose_domain,
    )
    try:
        plugin, manifest, logs = builder.build_and_prepare_plugin(req_src)
        config = repo.get_config()
        existing = [p for p in config.plugins if p.id != plugin.id]
        existing.append(plugin)
        repo.save_plugins_config(PluginsConfig(plugins=existing))
        click.secho(f"Successfully installed '{plugin.name}' ({plugin.id})!", fg="green", bold=True)
    except Exception as e:
        click.secho(f"Installation failed: {e}", fg="red", err=True)
        sys.exit(1)
