"""CLI command definitions for RoostOS Cluster Fleet Management."""

import sys
import json
import click
from typing import Optional

from roostos_engine.repository import YAMLConfigRepository
from roostos_engine.node_decommission import decommission_cluster_node, leave_cluster_locally


def register_cluster_commands(main_group: click.Group, call_dbus_method_fn, run_async_fn):
    @main_group.group(name="cluster")
    def cluster_group():
        """Manage RoostOS cluster fleet, node membership, and topology."""
        pass

    @cluster_group.command(name="status")
    @click.option("--config-dir", default="/etc/roostos", help="Path to config files directory")
    @click.option("--session", is_flag=True, help="Query session bus instead of system bus")
    def cluster_status(config_dir, session):
        """Displays cluster status, role, controller connectivity, and nodes."""
        async def run():
            try:
                status_json = await call_dbus_method_fn("GetClusterStatus", session=session)
                cs = json.loads(status_json)
            except Exception:
                repo = YAMLConfigRepository(config_dir)
                config = repo.get_config()
                node_id = (config.system.cluster.node_id if config.system and config.system.cluster else None) or "node-01"
                current_node = next((n for n in config.nodes if n.id == node_id), None)
                roles = [r.value if hasattr(r, "value") else str(r) for r in (current_node.roles if current_node else [])]
                is_ctl = "controller" in roles
                cs = {
                    "role": "controller" if is_ctl and len(config.nodes) > 1 else ("standalone" if is_ctl else "node"),
                    "node_id": node_id,
                    "node_name": current_node.name if current_node else config.system.hostname,
                    "roles": roles,
                    "controller_url": config.system.cluster.controller_url if config.system and config.system.cluster else None,
                    "registered_nodes_count": len(config.nodes),
                    "nodes": [n.model_dump() for n in config.nodes]
                }

            click.echo("=== RoostOS Cluster Status ===")
            click.echo(f"Topology Role:     {cs.get('role', 'standalone').upper()}")
            click.echo(f"Current Node:      {cs.get('node_name')} (ID: {cs.get('node_id')})")
            click.echo(f"Node Roles:        {', '.join(cs.get('roles', []))}")
            click.echo(f"Controller URL:    {cs.get('controller_url') or 'None (Local Master/Standalone)'}")
            click.echo(f"Fleet Nodes:       {cs.get('registered_nodes_count', 0)}")

            nodes = cs.get("nodes", [])
            if nodes:
                click.echo("\nRegistered Nodes:")
                for n in nodes:
                    nid = n.get("id") or n.get("node_id")
                    name = n.get("name") or nid
                    roles_str = ", ".join(n.get("roles", []))
                    ip = n.get("management_ip") or "-"
                    click.echo(f"  • {name:<20} | ID: {nid:<10} | IP: {ip:<15} | Roles: {roles_str}")

        run_async_fn(run())

    @cluster_group.command(name="leave")
    @click.option("--config-dir", default="/etc/roostos", help="Path to config files directory")
    @click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
    @click.option("--no-notify", is_flag=True, help="Do not attempt to notify controller")
    def cluster_leave(config_dir, yes, no_notify):
        """Instructs this local node to leave the cluster and return to standalone."""
        if not yes:
            if not click.confirm("Are you sure you want this node to leave the cluster? This will invalidate cluster credentials and reset to standalone."):
                click.echo("Aborted.")
                return

        click.echo("Leaving cluster and invalidating local credentials...")
        try:
            repo = YAMLConfigRepository(config_dir)
            result = leave_cluster_locally(repo, notify_controller=not no_notify)
            click.echo(f"✓ {result.message}")
            if result.certs_removed:
                click.echo(f"  Invalidated credentials: {', '.join(result.certs_removed)}")
        except Exception as e:
            click.echo(f"✗ Failed to leave cluster: {e}", err=True)
            sys.exit(1)

    @cluster_group.command(name="remove-node")
    @click.argument("node_id")
    @click.option("--config-dir", default="/etc/roostos", help="Path to config files directory")
    @click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
    def cluster_remove_node(node_id, config_dir, yes):
        """Evicts a node from the cluster and invalidates its credentials."""
        if not yes:
            if not click.confirm(f"Are you sure you want to remove node '{node_id}' from the cluster and revoke its credentials?"):
                click.echo("Aborted.")
                return

        click.echo(f"Evicting node '{node_id}' and invalidating credentials...")
        try:
            repo = YAMLConfigRepository(config_dir)
            result = decommission_cluster_node(repo, node_id)
            click.echo(f"✓ {result.message}")
            if result.certs_removed:
                click.echo(f"  Revoked certificates: {', '.join(result.certs_removed)}")
            if result.tunnels_cleaned:
                click.echo(f"  Tunnels cleared:      {', '.join(result.tunnels_cleaned)}")
            if result.dhcp_rebalanced:
                click.echo(f"  DHCP rebalanced:      {', '.join(result.dhcp_rebalanced)}")
        except Exception as e:
            click.echo(f"✗ Failed to remove node: {e}", err=True)
            sys.exit(1)

    @cluster_group.command(name="token")
    @click.option("--session", is_flag=True, help="Use session bus instead of system bus")
    def cluster_token(session):
        """Generates a temporary pairing join token for enrolling new nodes."""
        async def run():
            token = await call_dbus_method_fn("GenerateJoinToken", session=session)
            click.echo(f"Cluster Join Token: {token}")
            click.echo(f"Run on joining node: sudo roostos cluster join --token {token}")
        run_async_fn(run())
