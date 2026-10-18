import io
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import PlainTextResponse

from roostos_engine.models.edge import (
    CreatePeerRequest,
    EdgePeer,
    UpdateVpnServerRequest,
    VpnServerInfo,
)
from roostos_engine.repository import ConfigRepository
from roostos_engine.vpn_peer_manager import (
    create_vpn_peer,
    delete_vpn_peer,
    get_vpn_servers,
    list_all_peers,
    update_vpn_server as _update_vpn_server,
)
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/v1/edge/peers", tags=["Edge Peers"])


@router.get("/servers", response_model=List[VpnServerInfo])
async def list_vpn_servers(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> List[VpnServerInfo]:
    """Lists all cluster nodes and Edge Gateways available as VPN servers with public hostnames."""
    return get_vpn_servers(repo)


@router.put("/servers/{server_id}", response_model=VpnServerInfo)
async def update_vpn_server(
    server_id: str,
    payload: UpdateVpnServerRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> VpnServerInfo:
    """Updates VPN server status, public hostname, or WireGuard port for an Edge Gateway or Node."""
    try:
        return _update_vpn_server(repo, server_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=List[EdgePeer])
async def list_edge_peers(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> List[EdgePeer]:
    """Lists all active mobile devices and site-to-site peers connected to any VPN server node."""
    return list_all_peers(repo)


@router.post("", response_model=EdgePeer)
async def create_edge_peer(
    payload: CreatePeerRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgePeer:
    """Enrolls a new mobile device or site router onto the selected VPN server node."""
    try:
        return create_vpn_peer(repo, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{peer_id}/qr")
async def download_peer_qr(
    peer_id: str,
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Response:
    """Returns SVG QR code for mobile WireGuard scanning."""
    peers = list_all_peers(repo)
    peer = next((p for p in peers if p.id == peer_id), None)
    if not peer or not peer.client_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Peer not found.")

    svg_content = peer.qr_svg
    if not svg_content:
        try:
            import qrcode
            import qrcode.image.svg
            img = qrcode.make(peer.client_config, image_factory=qrcode.image.svg.SvgPathImage)
            stream = io.BytesIO()
            img.save(stream)
            svg_content = stream.getvalue().decode("utf-8")
        except Exception:
            svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><text x="10" y="100" fill="gray">QR Code Library Unavailable</text></svg>'

    return Response(content=svg_content, media_type="image/svg+xml")


@router.get("/{peer_id}/config", response_class=PlainTextResponse)
async def download_peer_config(
    peer_id: str,
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Response:
    """Downloads the WireGuard client configuration file (.conf)."""
    peers = list_all_peers(repo)
    peer = next((p for p in peers if p.id == peer_id), None)
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
    success = delete_vpn_peer(repo, peer_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Peer '{peer_id}' not found.")
    return {"status": "success", "message": f"Peer '{peer_id}' revoked."}
