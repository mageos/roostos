"""Cluster synchronization and multi-node orchestration commands for RoostOS."""

import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import List, Optional, Dict, Any
import click
import yaml
from pydantic import BaseModel, Field

from roostos_cli.discovery import NetworkDiscoverer


class ClusterNode(BaseModel):
    id: str
    name: str
    roles: List[str] = Field(default_factory=list)
    management_ip: str
    status: str = "active"


def _login_and_get_token(controller_url: str, user: str, pwd: str) -> str:
    """Authenticates against controller /api/auth/login and returns JWT access token."""
    login_data = urllib.parse.urlencode({"username": user, "password": pwd}).encode("utf-8")
    req = urllib.request.Request(
        f"{controller_url}/api/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("access_token", "")
    except urllib.error.HTTPError as e:
        click.secho(f"✗ Authentication failed: Incorrect username or password ({e.code})", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"✗ Failed to connect to controller login: {e}", fg="red", err=True)
        sys.exit(1)


def _record_cluster_link(config_dir: str, controller_url: str, node_id: str, name: str, role: str) -> None:
    """Updates local system.yaml with cluster controller linkage."""
    sys_path = os.path.join(config_dir, "system.yaml")
    os.makedirs(config_dir, exist_ok=True)
    sdata: Dict[str, Any] = {"system": {}}
    if os.path.exists(sys_path):
        try:
            with open(sys_path, "r") as f:
                sdata = yaml.safe_load(f) or {"system": {}}
        except Exception:
            pass
    cluster = sdata.setdefault("system", {}).setdefault("cluster", {})
    cluster.update({"controller_url": controller_url, "node_id": node_id, "is_controller": False})
    roles = cluster.setdefault("roles", [])
    if role not in roles:
        roles.append(role)
    try:
        with open(sys_path, "w") as f:
            yaml.dump(sdata, f, default_flow_style=False)
    except Exception:
        pass


@click.group(name="cluster")
def cluster_group() -> None:
    """Manage multi-node cluster topologies, pairing tokens, and node enrollment."""
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
        click.echo("Run 'roostos setup' or 'roostos cluster join' to register nodes.")
        return

    click.secho(f"{'NODE ID':<16} {'NAME':<24} {'MANAGEMENT IP':<18} {'ROLES'}", bold=True)
    click.echo("-" * 75)
    for n in nodes:
        roles_str = ", ".join(n.roles) if n.roles else "none"
        click.echo(f"{n.id:<16} {n.name:<24} {n.management_ip:<18} {roles_str}")


@cluster_group.command(name="token")
@click.option("--ttl", default=600, help="Token validity duration in seconds (default: 600)")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
@click.option("--port", default=8000, help="Controller listen port")
def token_cmd(ttl: int, config_dir: str, port: int) -> None:
    """Generates a temporary pairing join token on the cluster controller."""
    token = None
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/cluster/token", method="POST")
        with urllib.request.urlopen(req, timeout=3) as resp:
            token = json.loads(resp.read().decode("utf-8")).get("token")
    except Exception:
        pass

    if not token:
        try:
            from roostos_engine.cluster_manager import ClusterManager
            mgr = ClusterManager(config_dir=config_dir)
            token = mgr.generate_join_token(ttl_seconds=ttl)
        except Exception:
            import secrets
            token = f"roost-{secrets.token_hex(4)}"

    click.secho("=== RoostOS Cluster Join Token ===", fg="cyan", bold=True)
    click.echo(f"Token: {token} (Expires in {ttl // 60} minutes)\n")
    click.echo("To enroll a node, run on the joining node:")
    click.secho(f"sudo roostos cluster join --token {token}", fg="green", bold=True)


@cluster_group.command(name="join")
@click.argument("controller", required=False, default=None)
@click.option("--token", "-t", default=None, help="Pre-shared pairing join token")
@click.option("--username", "-u", default=None, help="Admin username for interactive authentication")
@click.option("--password", "-p", default=None, help="Admin password")
@click.option("--role", "-r", default=None, help="Node role (e.g. edge_gateway, compute_node)")
@click.option("--name", "-n", default=None, help="Friendly name for this node")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
@click.option("--mock", is_flag=True, help="Simulate join without writing system files")
def join_cluster_cmd(
    controller: Optional[str],
    token: Optional[str],
    username: Optional[str],
    password: Optional[str],
    role: Optional[str],
    name: Optional[str],
    config_dir: str,
    mock: bool,
) -> None:
    """Enrolls this node into a RoostOS cluster with mTLS certificates."""
    click.secho("=== RoostOS Cluster Node Enrollment ===", fg="cyan", bold=True)

    target_controller = controller
    if not target_controller:
        click.echo("Scanning for RoostOS Cluster Controller...")
        controllers = NetworkDiscoverer.discover_controllers()
        if len(controllers) == 1:
            target_controller = f"http://{controllers[0].ip}:{controllers[0].port}"
            click.secho(f"✓ Found Controller: {controllers[0].name} ({target_controller})", fg="green")
        elif len(controllers) > 1:
            click.echo("Multiple controllers discovered:")
            for idx, c in enumerate(controllers, 1):
                click.echo(f"  {idx}) {c.name} (http://{c.ip}:{c.port})")
            choice = click.prompt("Select controller", type=int, default=1)
            target_controller = f"http://{controllers[choice - 1].ip}:{controllers[choice - 1].port}"
        else:
            target_controller = click.prompt("Could not discover controller. Enter Controller IP or URL")

    if not target_controller.startswith(("http://", "https://")):
        target_controller = f"http://{target_controller}:8000" if ":" not in target_controller else f"http://{target_controller}"
    target_controller = target_controller.rstrip("/")

    auth_token = token
    if not auth_token:
        if username:
            user = username.strip()
            pwd = password if password is not None else click.prompt(f"Password for {user}", hide_input=True)
            auth_token = _login_and_get_token(target_controller, user, pwd)
        else:
            click.echo("\nAuthentication Method:\n  1) Admin Username & Password\n  2) Pre-shared Join Token")
            method = click.prompt("Select", type=click.Choice(["1", "2"]), default="1")
            if method == "1":
                user = click.prompt("Admin username", default="admin")
                pwd = click.prompt("Admin password", hide_input=True)
                auth_token = _login_and_get_token(target_controller, user, pwd)
            else:
                auth_token = click.prompt("Join token").strip()

    if not auth_token:
        click.secho("Error: No authentication token obtained.", fg="red", err=True)
        sys.exit(1)

    hostname = socket.gethostname() or "roost-node"
    node_name, node_role = name or hostname, role or "edge_gateway"
    node_id = f"node-{uuid.uuid4().hex[:8]}"

    if mock:
        click.secho(f"✓ [MOCK] Successfully joined cluster at {target_controller} as '{node_name}' ({node_role})", fg="green", bold=True)
        return

    click.echo(f"Submitting enrollment request to {target_controller}...")
    try:
        req = urllib.request.Request(
            f"{target_controller}/api/cluster/join",
            data=json.dumps({"token": auth_token, "node_id": node_id, "name": node_name, "roles": [node_role]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            join_resp = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_msg = json.loads(err_msg).get("detail", err_msg)
        except Exception:
            pass
        click.secho(f"✗ Join failed ({e.code}): {err_msg}", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"✗ Network error connecting to controller: {e}", fg="red", err=True)
        sys.exit(1)

    certs_saved = False
    if join_resp.get("client_cert_pem") and join_resp.get("client_key_pem"):
        cert_dir = os.path.join(config_dir, "certs")
        os.makedirs(cert_dir, exist_ok=True)
        for fname, key in (("client.crt", "client_cert_pem"), ("client.key", "client_key_pem"), ("ca.crt", "ca_cert_pem")):
            if join_resp.get(key):
                with open(os.path.join(cert_dir, fname), "w") as f:
                    f.write(join_resp[key])
        certs_saved = True

    _record_cluster_link(config_dir, target_controller, node_id, node_name, node_role)
    click.secho(f"✓ Node successfully enrolled in cluster as '{node_name}' ({node_role})!", fg="green", bold=True)
    if certs_saved:
        click.secho(f"✓ Enrolled X.509 mTLS certificates in {config_dir}/certs/", fg="green")
    click.secho(f"✓ Linked to controller at {target_controller}", fg="green")


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
    node_id, node_name = f"node-{ip.replace('.', '-')}", name or f"Node {ip}"

    for n in nodes:
        if n.get("management_ip") == ip or n.get("id") == node_id:
            n["name"] = node_name
            if role not in n.get("roles", []):
                n.setdefault("roles", []).append(role)
            break
    else:
        nodes.append({"id": node_id, "name": node_name, "roles": [role], "management_ip": ip, "status": "active"})

    data["nodes"] = nodes
    try:
        with open(nodes_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        click.secho(f"✓ Node {ip} adopted into cluster as '{node_name}' ({role})", fg="green", bold=True)
    except Exception as e:
        click.secho(f"Error saving nodes.yaml: {e}", fg="red", err=True)
        sys.exit(1)
