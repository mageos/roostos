"""Cluster synchronization and multi-node orchestration commands for RoostOS."""

import os
import sys
from typing import List, Optional, Dict, Any
import click
import yaml
from pydantic import BaseModel, Field


class ClusterNode(BaseModel):
    id: str
    name: str
    roles: List[str] = Field(default_factory=list)
    management_ip: str
    status: str = "active"


@click.group(name="cluster")
def cluster_group() -> None:
    """Manage multi-node cluster topologies and node adoption."""
    pass


@cluster_group.command(name="list")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def list_cluster_cmd(config_dir: str) -> None:
    """Displays all nodes registered in the local RoostOS cluster."""
    nodes_path = os.path.join(config_dir, "nodes.yaml")
    nodes: List[ClusterNode] = []
    if os.path.exists(nodes_path):
        try:
            with open(nodes_path, "r") as f:
                data = yaml.safe_load(f)
            for n in data.get("nodes", []):
                nodes.append(ClusterNode(**n))
        except Exception as e:
            click.secho(f"Warning: Could not read nodes.yaml: {e}", fg="yellow")

    if not nodes:
        click.echo("This system is not yet configured as part of a cluster.")
        click.echo("Run 'roostos setup' or 'roostos cluster adopt <ip>' to register nodes.")
        return

    click.secho(f"{'NODE ID':<16} {'NAME':<24} {'MANAGEMENT IP':<18} {'ROLES'}", bold=True)
    click.echo("-" * 75)
    for n in nodes:
        roles_str = ", ".join(n.roles) if n.roles else "none"
        click.echo(f"{n.id:<16} {n.name:<24} {n.management_ip:<18} {roles_str}")


@cluster_group.command(name="adopt")
@click.argument("ip")
@click.option("--name", default=None, help="Friendly name for the adopted node")
@click.option("--role", default="gateway_router", help="Primary role for the node")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def adopt_node_cmd(ip: str, name: Optional[str], role: str, config_dir: str) -> None:
    """Registers and adopts a remote node into the cluster configuration."""
    nodes_path = os.path.join(config_dir, "nodes.yaml")
    os.makedirs(config_dir, exist_ok=True)
    data: Dict[str, Any] = {"nodes": []}
    if os.path.exists(nodes_path):
        try:
            with open(nodes_path, "r") as f:
                loaded = yaml.safe_load(f)
                if loaded and "nodes" in loaded:
                    data = loaded
        except Exception:
            pass

    nodes = data.get("nodes", [])
    node_id = f"node-{ip.replace('.', '-')}"
    node_name = name or f"Node {ip}"

    # Check if already registered
    for n in nodes:
        if n.get("management_ip") == ip or n.get("id") == node_id:
            n["name"] = node_name
            if role not in n.get("roles", []):
                n.setdefault("roles", []).append(role)
            break
    else:
        nodes.append({
            "id": node_id,
            "name": node_name,
            "roles": [role],
            "management_ip": ip,
            "status": "active",
        })

    data["nodes"] = nodes
    try:
        with open(nodes_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        click.secho(f"✓ Node {ip} adopted into cluster as '{node_name}' ({role})", fg="green", bold=True)
    except Exception as e:
        click.secho(f"Error saving nodes.yaml: {e}", fg="red", err=True)
        sys.exit(1)
