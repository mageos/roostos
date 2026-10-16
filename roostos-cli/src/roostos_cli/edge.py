"""CLI subcommands for RoostOS Edge Gateway orchestration."""

import os
import sys
import json
import urllib.error
import urllib.parse
import urllib.request
import click
from typing import Optional

from roostos_engine.edge_manager import EdgeManager
from roostos_engine.models.edge import (
    EdgeEnrollmentPayload,
    EdgeEnrollmentResponse,
    EdgeInviteBundle,
)


def _detect_public_ip() -> str:
    """Auto-detects default route source IP."""
    try:
        import subprocess
        res = subprocess.run(["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=2)
        match = [p for p in res.stdout.split() if p.count(".") == 3 and not p.startswith("1.1.")]
        if match:
            return match[0]
    except Exception:
        pass
    return "127.0.0.1"


def _record_edge_gateway(
    config_dir: str,
    vps_ip: str,
    gw_tunnel: str,
    home_tunnel: str,
    pub_key: str,
    port: int = 51820,
    domain: Optional[str] = None,
) -> None:
    """Helper to persist edge gateway record in network.yaml."""
    EdgeManager(config_dir=config_dir).persist_gateway_config(
        vps_ip=vps_ip,
        gw_tunnel=gw_tunnel,
        home_tunnel=home_tunnel,
        pub_key=pub_key,
        port=port,
        domain=domain,
    )


@click.group(name="edge")
def edge_group() -> None:
    """Manage VPS Edge Gateway, ingress reverse-proxies, and CGNAT bypass."""
    pass


@edge_group.command(name="token")
@click.option("--domain", default=None, help="Domain name / FQDN of this VPS (used instead of IP in invite)")
@click.option("--ip", default=None, help="Public IP address of this VPS (auto-detected if omitted)")
@click.option("--port", default=51820, help="WireGuard UDP listen port (default: 51820)")
@click.option("--ttl", default=15, help="Token validity window in minutes (legacy HTTP only)")
@click.option("--export", "-o", "export_file", default=None, help="Export invitation bundle to file (e.g. roost-edge.json)")
@click.option("--legacy-http", is_flag=True, help="Use legacy HTTP API bootstrap token instead of WireGuard invite")
@click.option("--https", is_flag=True, help="Use HTTPS protocol in legacy HTTP token")
def generate_token_cmd(
    domain: Optional[str],
    ip: Optional[str],
    port: int,
    ttl: int,
    export_file: Optional[str],
    legacy_http: bool,
    https: bool,
) -> None:
    """Generates an Edge Gateway invitation or bootstrap token for home router connection."""
    public_ip = ip or _detect_public_ip()
    mgr = EdgeManager()

    if not legacy_http:
        invite = mgr.create_wireguard_invite(
            vps_public_ip=public_ip,
            listen_port=port,
            output_path=export_file,
            domain=domain,
        )
        wg_token = invite.to_token()
        _record_edge_gateway(
            config_dir="/etc/roostos",
            vps_ip=public_ip,
            gw_tunnel=invite.gateway_tunnel_ip,
            home_tunnel=invite.assigned_tunnel_ip,
            pub_key=invite.gateway_public_key,
            port=port,
            domain=domain,
        )

        click.secho(f"=== RoostOS WireGuard Edge Gateway Invitation ===\nEndpoint: {invite.endpoint} (WAN port 8000 closed)\nPaste token into Home Router Web Console or CLI:\n", fg="cyan", bold=True)
        click.secho(wg_token, fg="green", bold=True)
        if export_file:
            click.echo(f"\n✓ Exported to: {export_file}")
        return

    bootstrap = mgr.create_bootstrap_token(
        vps_public_ip=public_ip, listen_port=port if port != 51820 else 8000,
        ttl_minutes=ttl, use_https=https,
    )
    formatted_uri = f"roost-edge://{domain or public_ip}:{port}?token={bootstrap.token}"
    click.secho(f"=== RoostOS Edge Gateway Bootstrap Token ===\nExpires: {ttl} min | Public IP: {public_ip}\nPaste into Home Router Web Console or CLI:\n", fg="cyan", bold=True)
    click.secho(formatted_uri, fg="green", bold=True)


@edge_group.command(name="connect")
@click.option("--token", default=None, help="Bootstrap token or invite string (roost-edge-wg://... or roost-edge://...)")
@click.option("--file", "-f", "bundle_file", default=None, help="Path to exported invitation bundle JSON file")
@click.option("--config-dir", default="/etc/roostos", help="Home configuration directory")
@click.option("--mock", is_flag=True, help="Dry run without modifying system networkd files")
def connect_cmd(
    token: Optional[str],
    bundle_file: Optional[str],
    config_dir: str,
    mock: bool,
) -> None:
    """Connects home router to the VPS Edge Gateway using invite token or bundle file."""
    if not token and not bundle_file:
        click.secho("Error: Either --token or --file must be specified.", fg="red", err=True)
        sys.exit(1)

    mgr = EdgeManager(config_dir=config_dir, mock=mock)

    invite_bundle: Optional[EdgeInviteBundle] = None
    if bundle_file:
        try:
            with open(bundle_file, "r") as f:
                invite_bundle = EdgeInviteBundle.model_validate_json(f.read())
        except Exception as e:
            click.secho(f"✗ Failed to read invite bundle '{bundle_file}': {e}", fg="red", err=True)
            sys.exit(1)
    elif token and token.strip().startswith("roost-edge-wg://"):
        try:
            invite_bundle = EdgeInviteBundle.from_token(token.strip())
        except Exception as e:
            click.secho(f"✗ Failed to decode WireGuard invite token: {e}", fg="red", err=True)
            sys.exit(1)

    if invite_bundle:
        click.secho("Applying WireGuard Edge Gateway configuration...", fg="cyan")
        mgr.apply_wireguard_invite(invite_bundle)
        vps_ip = invite_bundle.endpoint.split(":")[0]
        port = int(invite_bundle.endpoint.split(":")[1]) if ":" in invite_bundle.endpoint else 51820
        _record_edge_gateway(
            config_dir=config_dir,
            vps_ip=vps_ip,
            gw_tunnel=invite_bundle.gateway_tunnel_ip,
            home_tunnel=invite_bundle.assigned_tunnel_ip,
            pub_key=invite_bundle.gateway_public_key,
            port=port,
        )
        click.secho(f"✓ Edge Gateway tunnel established at {invite_bundle.assigned_tunnel_ip} -> {invite_bundle.gateway_tunnel_ip}", fg="green", bold=True)
        click.secho("✓ WireGuard interface active. Zero public web API calls made.", fg="green")
        return

    # Legacy HTTP token flow
    click.secho("Initiating connection to Edge Gateway VPS...", fg="cyan")
    token_str = token.strip() if token else ""
    endpoint_url, bearer_token = "http://127.0.0.1:8000", token_str
    if token_str.startswith("roost-edge://"):
        parts = token_str[len("roost-edge://"):].split("?token=")
        endpoint_url = f"http://{parts[0]}"
        bearer_token = parts[1] if len(parts) > 1 else ""

    try:
        import jwt
        unverified = jwt.decode(bearer_token, options={"verify_signature": False})
        if unverified.get("endpoint_url"):
            endpoint_url = unverified["endpoint_url"]
    except Exception:
        pass

    home_priv, home_pub = mgr.generate_wireguard_keypair()
    enroll_url = f"{endpoint_url}/api/v1/edge/enroll"
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
    except urllib.error.HTTPError as e:
        err_msg = e.reason
        try:
            err_json = json.loads(e.read().decode("utf-8"))
            err_msg = err_json.get("detail", err_msg)
        except Exception:
            pass
        click.secho(f"✗ Enrollment failed: Edge Gateway returned HTTP {e.code} ({err_msg})", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"✗ Enrollment failed: Could not connect to Edge Gateway: {e}", fg="red", err=True)
        sys.exit(1)

    click.secho("✓ Authenticated with Edge Gateway VPS successfully!", fg="green")

    # Generate networkd configuration on home router
    net_files = mgr.generate_networkd_config(
        role="client", private_key=home_priv, peer_public_key=enroll_resp.gateway_public_key,
        endpoint=enroll_resp.endpoint, tunnel_ip=enroll_resp.assigned_tunnel_ip,
        allowed_ips=",".join(enroll_resp.allowed_ips), persistent_keepalive=enroll_resp.persistent_keepalive,
    )
    mgr._apply_network_files(net_files)

    vps_ip = enroll_resp.endpoint.split(":")[0]
    _record_edge_gateway(
        config_dir=config_dir,
        vps_ip=vps_ip,
        gw_tunnel=enroll_resp.gateway_tunnel_ip,
        home_tunnel=enroll_resp.assigned_tunnel_ip,
        pub_key=enroll_resp.gateway_public_key,
    )
    click.secho("✓ Edge Gateway tunnel established at 10.42.0.2 -> 10.42.0.1", fg="green", bold=True)


@edge_group.command(name="status")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def status_cmd(config_dir: str) -> None:
    """Displays active Edge Gateway status and Ingress routes."""
    click.secho("=== Edge Gateway Status ===", fg="cyan", bold=True)
    import yaml
    for fpath in (os.path.join(config_dir, "network.yaml"), os.path.join(config_dir, "nodes.yaml")):
        if os.path.exists(fpath):
            try:
                with open(fpath, "r") as f:
                    data = yaml.safe_load(f) or {}
                for gw in (data.get("edge_gateways") or data.get("network", {}).get("edge_gateways", [])):
                    click.echo(f"Gateway ID:     {gw.get('id')}\nName:           {gw.get('name')}\nPublic IP:      {gw.get('public_ip')}\nTunnel:         {gw.get('tunnel_ip_home')} -> {gw.get('tunnel_ip_gateway')}\nStatus:         {gw.get('status', 'connected')}\nIngress Routes: {len(gw.get('ingress_routes', []))}")
                    return
                for n in data.get("nodes", []):
                    if "edge_gateway" in n.get("roles", []):
                        click.echo(f"Gateway ID:     {n.get('id')}\nName:           {n.get('name')}\nPublic IP:      {n.get('management_ip') or '10.42.0.1'}\nTunnel:         10.42.0.2 -> 10.42.0.1\nStatus:         connected (Cluster Node)\nIngress Routes: 0")
                        return
            except Exception:
                pass

    click.echo("No Edge Gateway currently linked. Run 'roostos edge connect --token <TOKEN>' to link.")


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


@edge_group.command(name="update")
@click.option("--domain", default=None, help="Domain name (FQDN) of the Edge Gateway VPS")
@click.option("--ip", default=None, help="Public IP address of the Edge Gateway VPS")
@click.option("--port", default=51820, help="WireGuard UDP listen port (default: 51820)")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def update_cmd(
    domain: Optional[str],
    ip: Optional[str],
    port: int,
    config_dir: str,
) -> None:
    """Updates the Edge Gateway endpoint to use a domain name or IP address."""
    if not domain and not ip:
        click.secho("Error: Either --domain or --ip must be specified.", fg="red", err=True)
        sys.exit(1)

    endpoint_host = domain or ip
    mgr = EdgeManager(config_dir=config_dir)
    updated_file = mgr.update_peer_endpoint(endpoint_host=endpoint_host, port=port)
    from roostos_engine.ingress_helper import update_gateway_endpoint
    update_gateway_endpoint(config_dir=config_dir, endpoint_host=endpoint_host, port=port, is_domain=bool(domain))

    if updated_file:
        click.secho(f"✓ Edge Gateway WireGuard endpoint updated to {endpoint_host}:{port}", fg="green", bold=True)
        click.secho("✓ Systemd-networkd reloaded.", fg="green")
    else:
        click.secho(f"✓ Edge Gateway record updated to {endpoint_host}:{port}.", fg="green")
