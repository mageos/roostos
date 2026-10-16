"""FastAPI router for Edge Gateway Multi-Peer VPN and Mobile Device enrollment."""

import datetime
import os
import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import PlainTextResponse

from roostos_engine.edge_manager import EdgeManager
from roostos_engine.edge_peer_helper import (
    compile_hub_network_file,
    compile_server_multi_peer_netdev,
    generate_client_wireguard_config,
)
from roostos_engine.models.edge import (
    CreatePeerRequest,
    EdgeGatewayConfig,
    EdgePeer,
    EdgePeerType,
)
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/v1/edge/peers", tags=["Edge Peers"])


def _get_active_gateway(repo: ConfigRepository) -> Optional[EdgeGatewayConfig]:
    config = repo.get_config()
    gateways = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
    if gateways:
        return gateways[0]
    return None


def _save_gateway(repo: ConfigRepository, gw: EdgeGatewayConfig) -> None:
    config = repo.get_config()
    existing = [g for g in (getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", [])) if g.id != gw.id]
    config.network.edge_gateways = [*existing, gw]
    config.edge_gateways = [*existing, gw]
    try:
        repo.save_network_config(config.network)
    except Exception as e:
        print(f"Warning: Failed to persist gateway config: {e}")


@router.get("", response_model=List[EdgePeer])
async def list_edge_peers(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> List[EdgePeer]:
    """Lists all active mobile devices and site-to-site peers connected to the Edge Gateway."""
    gw = _get_active_gateway(repo)
    return gw.peers if gw else []


@router.post("", response_model=EdgePeer)
async def create_edge_peer(
    payload: CreatePeerRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgePeer:
    """Enrolls a new mobile device or site router onto the Edge Gateway VPN hub."""
    gw = _get_active_gateway(repo)
    if not gw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Edge Gateway configured. Link an Edge Gateway before registering peers.",
        )

    mgr = EdgeManager()
    client_priv, client_pub = mgr.generate_wireguard_keypair()

    # Determine unique assigned tunnel IP in 10.42.0.0/24
    used_ips = {p.assigned_ip.split("/")[0] for p in gw.peers}
    used_ips.add(gw.tunnel_ip_gateway.split("/")[0])
    used_ips.add(gw.tunnel_ip_home.split("/")[0])

    assigned_host = None
    # For mobile/client: start at 10.42.0.10; For site: start at 10.42.0.3
    start_octet = 3 if payload.peer_type == EdgePeerType.SITE else 10
    for octet in range(start_octet, 250):
        candidate = f"10.42.0.{octet}"
        if candidate not in used_ips:
            assigned_host = candidate
            break

    if not assigned_host:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="VPN subnet address pool exhausted.")

    assigned_ip = f"{assigned_host}/32"

    # Compile AllowedIPs for the client:
    # If route_internet is enabled, route full tunnel 0.0.0.0/0
    # Otherwise, route the VPN subnet (10.42.0.0/24) plus all site LAN subnets
    if payload.route_internet:
        client_allowed_ips = ["0.0.0.0/0", "::/0"]
    else:
        client_allowed_ips = ["10.42.0.0/24"]
        # Include all remote site subnets for inter-LAN routing
        for p in gw.peers:
            if p.subnets:
                client_allowed_ips.extend(p.subnets)
        if payload.subnets:
            client_allowed_ips.extend(payload.subnets)

    endpoint_host = gw.domain or gw.public_ip
    client_conf = generate_client_wireguard_config(
        client_private_key=client_priv,
        gateway_public_key=gw.public_key or "",
        endpoint=f"{endpoint_host}:{gw.listen_port}",
        assigned_ip=f"{assigned_host}/24",
        allowed_ips=list(dict.fromkeys(client_allowed_ips)),
        dns_server="10.42.0.1",
        persistent_keepalive=25,
    )

    qr_svg = None
    try:
        import io
        import qrcode
        import qrcode.image.svg

        img = qrcode.make(client_conf, image_factory=qrcode.image.svg.SvgPathImage)
        stream = io.BytesIO()
        img.save(stream)
        qr_svg = stream.getvalue().decode("utf-8")
    except Exception:
        pass

    peer = EdgePeer(
        id=f"peer-{uuid.uuid4().hex[:6]}",
        name=payload.name.strip(),
        peer_type=payload.peer_type,
        public_key=client_pub,
        assigned_ip=assigned_ip,
        subnets=payload.subnets,
        route_internet=payload.route_internet,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        client_config=client_conf,
        qr_svg=qr_svg,
    )

    gw.peers.append(peer)

    # Re-apply multi-peer configuration if we have VPS private key
    state_dir = getattr(repo, "config_dir", "/etc/roostos")
    key_file = os.path.join(state_dir, "edge_server.key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r") as f:
                vps_priv, _ = f.read().strip().split(":")
            netdev_content = compile_server_multi_peer_netdev(
                gateway_private_key=vps_priv,
                peers=gw.peers,
                listen_port=gw.listen_port,
            )
            network_content = compile_hub_network_file(
                tunnel_ip=gw.tunnel_ip_gateway,
            )
            mgr._apply_network_files({
                "50-wg-edge.netdev": netdev_content,
                "50-wg-edge.network": network_content,
            })
        except Exception as e:
            print(f"Warning: Failed to reload WireGuard hub network files: {e}")

    _save_gateway(repo, gw)
    return peer


@router.get("/{peer_id}/qr")
async def download_peer_qr(
    peer_id: str,
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Response:
    """Returns SVG QR code for mobile WireGuard scanning."""
    gw = _get_active_gateway(repo)
    if not gw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Edge Gateway.")
    peer = next((p for p in gw.peers if p.id == peer_id), None)
    if not peer or not peer.client_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Peer not found.")

    svg_content = peer.qr_svg
    if not svg_content:
        import io
        import qrcode
        import qrcode.image.svg

        img = qrcode.make(peer.client_config, image_factory=qrcode.image.svg.SvgPathImage)
        stream = io.BytesIO()
        img.save(stream)
        svg_content = stream.getvalue().decode("utf-8")

    return Response(content=svg_content, media_type="image/svg+xml")


@router.get("/{peer_id}/config", response_class=PlainTextResponse)
async def download_peer_config(
    peer_id: str,
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Response:
    """Downloads the WireGuard client configuration file (.conf)."""
    gw = _get_active_gateway(repo)
    if not gw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Edge Gateway.")
    peer = next((p for p in gw.peers if p.id == peer_id), None)
    if not peer or not peer.client_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Peer configuration not found.")

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in peer.name)
    return Response(
        content=peer.client_config,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.conf"'},
    )


@router.delete("/{peer_id}", response_model=Dict[str, str])
async def delete_edge_peer(
    peer_id: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, str]:
    """Revokes a WireGuard peer and detaches it from the VPN hub."""
    gw = _get_active_gateway(repo)
    if not gw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Edge Gateway.")

    initial_count = len(gw.peers)
    gw.peers = [p for p in gw.peers if p.id != peer_id]
    if len(gw.peers) == initial_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Peer '{peer_id}' not found.")

    _save_gateway(repo, gw)
    return {"status": "success", "message": f"Peer '{peer_id}' revoked."}
