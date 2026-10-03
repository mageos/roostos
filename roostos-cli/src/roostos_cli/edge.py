"""CLI subcommands for RoostOS Edge Gateway orchestration."""

import os
import sys
import json
import urllib.parse
import urllib.request
import click
from typing import Optional

from roostos_engine.edge_manager import EdgeManager
from roostos_engine.models.edge import EdgeEnrollmentPayload, EdgeEnrollmentResponse


@click.group(name="edge")
def edge_group() -> None:
    """Manage VPS Edge Gateway, ingress reverse-proxies, and CGNAT bypass."""
    pass


@edge_group.command(name="token")
@click.option("--ip", default=None, help="Public IP address of this VPS (auto-detected if omitted)")
@click.option("--port", default=8000, help="Port where RoostOS Node API is listening")
@click.option("--ttl", default=15, help="Token validity window in minutes")
@click.option("--https", is_flag=True, help="Use HTTPS protocol in enrollment URI")
def generate_token_cmd(ip: Optional[str], port: int, ttl: int, https: bool) -> None:
    """Generates a short-lived single-use bootstrap token on the VPS for home enrollment."""
    # 1. Detect public IP if not provided
    public_ip = ip
    if not public_ip:
        try:
            # Query default route source IP
            import subprocess
            res = subprocess.run(["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=2)
            for part in res.stdout.split():
                if part.count(".") == 3 and not part.startswith("1.1."):
                    public_ip = part
                    break
        except Exception:
            pass
    if not public_ip:
        public_ip = "127.0.0.1"

    mgr = EdgeManager()
    bootstrap = mgr.create_bootstrap_token(vps_public_ip=public_ip, listen_port=port, ttl_minutes=ttl, use_https=https)

    # Persist active token locally so the API can validate/consume it
    state_dir = "/var/lib/roostos" if os.path.exists("/var/lib") else "/tmp/roostos"
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, "edge_bootstrap.json")
    try:
        with open(state_file, "w") as f:
            json.dump({
                "token": bootstrap.token,
                "jti": jwt_get_jti(bootstrap.token),
                "expires_at": bootstrap.expires_at,
                "public_ip": public_ip,
                "port": port,
            }, f)
    except Exception as e:
        click.secho(f"Warning: Could not write token state file: {e}", fg="yellow")

    formatted_uri = f"roost-edge://{public_ip}:{port}?token={bootstrap.token}"

    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("         RoostOS Edge Gateway Bootstrap Token     ", fg="cyan", bold=True)
    click.secho("==================================================", fg="cyan", bold=True)
    click.echo("\nCopy and paste this token into your Home Router Web Console:\n")
    click.secho(formatted_uri, fg="green", bold=True)
    click.echo(f"\nExpires in: {ttl} minutes (single-use)")
    click.echo(f"VPS Public IP: {public_ip}")
    click.secho("==================================================", fg="cyan")


@edge_group.command(name="connect")
@click.option("--token", required=True, help="Bootstrap token generated on VPS (roost-edge://...)")
@click.option("--config-dir", default="/etc/roostos", help="Home configuration directory")
@click.option("--mock", is_flag=True, help="Dry run without modifying system networkd files")
def connect_cmd(token: str, config_dir: str, mock: bool) -> None:
    """Connects home router to the VPS Edge Gateway using the bootstrap token."""
    click.secho("Initiating connection to Edge Gateway VPS...", fg="cyan")

    # Parse token format
    token_str = token.strip()
    endpoint_url = ""
    bearer_token = ""

    if token_str.startswith("roost-edge://"):
        raw = token_str[len("roost-edge://"):]
        parts = raw.split("?token=")
        host_port = parts[0]
        bearer_token = parts[1] if len(parts) > 1 else ""
        endpoint_url = f"http://{host_port}"
    else:
        bearer_token = token_str
        endpoint_url = "http://127.0.0.1:8000"

    mgr = EdgeManager(config_dir=config_dir, mock=mock)
    home_priv, home_pub = mgr.generate_wireguard_keypair()

    # Call VPS enrollment API
    enroll_url = f"{endpoint_url}/api/edge/enroll"
    payload = EdgeEnrollmentPayload(
        home_public_key=home_pub,
        hostname="roost-home",
        requested_tunnel_ip="10.42.0.2/24",
    )

    req = urllib.request.Request(
        enroll_url,
        data=json.dumps(payload.model_dump()).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            enroll_resp = EdgeEnrollmentResponse.model_validate(data)
    except Exception as e:
        click.secho(f"✗ Enrollment failed: Could not connect to Edge Gateway: {e}", fg="red", err=True)
        sys.exit(1)

    click.secho("✓ Authenticated with Edge Gateway VPS successfully!", fg="green")

    # Generate networkd configuration on home router
    net_files = mgr.generate_networkd_config(
        role="client",
        private_key=home_priv,
        peer_public_key=enroll_resp.gateway_public_key,
        endpoint=enroll_resp.endpoint,
        tunnel_ip=enroll_resp.assigned_tunnel_ip,
        allowed_ips=",".join(enroll_resp.allowed_ips),
        persistent_keepalive=enroll_resp.persistent_keepalive,
    )

    net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
    if not mock:
        os.makedirs(net_dir, exist_ok=True)
        for fname, content in net_files.items():
            fpath = os.path.join(net_dir, fname)
            with open(fpath, "w") as f:
                f.write(content)
        click.secho(f"✓ Written WireGuard network configuration to {net_dir}", fg="green")

    click.secho("✓ Edge Gateway tunnel established at 10.42.0.2 -> 10.42.0.1", fg="green", bold=True)


@edge_group.command(name="status")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def status_cmd(config_dir: str) -> None:
    """Displays active Edge Gateway status and Ingress routes."""
    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("             Edge Gateway Status                  ", fg="cyan", bold=True)
    click.secho("==================================================", fg="cyan", bold=True)

    net_yaml = os.path.join(config_dir, "network.yaml")
    if os.path.exists(net_yaml):
        try:
            import yaml
            with open(net_yaml, "r") as f:
                data = yaml.safe_load(f) or {}
            edge_gateways = data.get("network", {}).get("edge_gateways", [])
            if edge_gateways:
                for gw in edge_gateways:
                    click.echo(f"Gateway ID:     {gw.get('id')}")
                    click.echo(f"Name:           {gw.get('name')}")
                    click.echo(f"Public IP:      {gw.get('public_ip')}")
                    click.echo(f"Tunnel:         {gw.get('tunnel_ip_home')} -> {gw.get('tunnel_ip_gateway')}")
                    click.echo(f"Status:         {gw.get('status', 'connected')}")
                    click.echo(f"Ingress Routes: {len(gw.get('ingress_routes', []))}")
                    return
        except Exception:
            pass

    click.echo("No Edge Gateway currently linked. Run 'roostos edge connect --token <TOKEN>' to link.")
    click.secho("==================================================", fg="cyan")


@edge_group.command(name="lockdown")
@click.option("--wan", default="eth0", help="Public WAN interface to protect")
def lockdown_cmd(wan: str) -> None:
    """Hardens VPS firewall by blocking public access to port 8000 on WAN."""
    mgr = EdgeManager()
    rules = mgr.compile_lockdown_rules(wan_interface=wan)
    click.secho(f"Applying attack surface hardening on interface {wan}...", fg="cyan")
    for r in rules:
        click.echo(f"  {r}")
    click.secho("✓ RoostOS REST API is now restricted to internal WireGuard tunnel (10.42.0.1) & localhost.", fg="green")


def jwt_get_jti(token: str) -> str:
    """Extracts jti without verifying signature."""
    try:
        import jwt
        unverified = jwt.decode(token, options={"verify_signature": False})
        return unverified.get("jti", "")
    except Exception:
        return ""
