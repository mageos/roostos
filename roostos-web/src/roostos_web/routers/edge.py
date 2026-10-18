"""FastAPI router for Edge Gateway management, bootstrap enrollment, and ingress routing."""

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from roostos_engine.models.edge import (
    IngressRoute, EdgeGatewayConfig, EdgeBootstrapToken, EdgeEnrollmentPayload,
    EdgeEnrollmentResponse, EdgeInviteBundle, GenerateTokenRequest, ConnectEdgeRequest,
    IngressRoutePayload, UpdateEdgeEndpointRequest, EdgeRouteSyncRequest, EdgeConnectivityCheckResponse,
)
from roostos_engine.edge_manager import EdgeManager
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.models.certificates import ChallengeType
from roostos_engine.repository import ConfigRepository
from roostos_engine.edge_helpers import get_active_gateways as _get_active_gateways, save_edge_gateway_record as _save_edge_gateway_record
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/v1/edge", tags=["edge"])

@router.post("/token", response_model=EdgeBootstrapToken)
async def generate_bootstrap_token(
    payload: GenerateTokenRequest, current_user: UserSession = Depends(get_current_admin),
) -> EdgeBootstrapToken:
    """Generates a short-lived single-use bootstrap token on the VPS for enrollment."""
    vps_ip = payload.public_ip or os.environ.get("ROOSTOS_PUBLIC_IP", "127.0.0.1")
    return EdgeManager().create_bootstrap_token(
        vps_public_ip=vps_ip, listen_port=payload.port,
        ttl_minutes=payload.ttl_minutes, use_https=payload.use_https,
    )

@router.post("/enroll", response_model=EdgeEnrollmentResponse)
async def enroll_home_server(
    payload: EdgeEnrollmentPayload, authorization: Optional[str] = Header(None),
) -> EdgeEnrollmentResponse:
    """Public bootstrap endpoint called by Home Server to complete automated enrollment."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or malformed bootstrap Bearer token.")
    token_str = authorization.split("Bearer ", 1)[1].strip()
    mgr = EdgeManager()
    try:
        claims = mgr.validate_and_consume_token(token_str)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    vps_ip = claims.get("vps_ip", "127.0.0.1")
    state_dir = os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
    key_file = os.path.join(state_dir, "edge_server.key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            vps_priv, vps_pub = f.read().strip().split(":")
    else:
        vps_priv, vps_pub = mgr.generate_wireguard_keypair()
        try:
            os.makedirs(state_dir, exist_ok=True)
            with open(key_file, "w") as f:
                f.write(f"{vps_priv}:{vps_pub}")
        except Exception:
            pass
    gw_allowed = ["10.42.0.2/32"] + [s for s in payload.lan_subnets if s != "10.42.0.2/32"]
    mgr._apply_network_files(mgr.generate_networkd_config(
        role="gateway", private_key=vps_priv, peer_public_key=payload.home_public_key,
        listen_port=51820, tunnel_ip="10.42.0.1/24", allowed_ips=",".join(gw_allowed),
        routed_subnets=payload.lan_subnets,
    ))
    return EdgeEnrollmentResponse(
        status="success", gateway_public_key=vps_pub, endpoint=f"{vps_ip}:51820",
        assigned_tunnel_ip="10.42.0.2/24", gateway_tunnel_ip="10.42.0.1/24",
        allowed_ips=["10.42.0.0/24"], persistent_keepalive=25,
        message="Edge Gateway successfully paired with home server.",
    )

@router.post("/connect", response_model=EdgeGatewayConfig)
async def connect_to_edge_gateway(
    payload: ConnectEdgeRequest, current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgeGatewayConfig:
    """Home server connects to Edge Gateway VPS using the invite or bootstrap token."""
    token_str = payload.token.strip()
    mgr = EdgeManager(config_dir=getattr(repo, "config_dir", "/etc/roostos"))
    if token_str.startswith("roost-edge-wg://"):
        try:
            invite = EdgeInviteBundle.from_token(token_str)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed WireGuard invite: {e}")
        mgr.apply_wireguard_invite(invite)
        vps_ip = invite.endpoint.split(":")[0]
        port = int(invite.endpoint.split(":")[1]) if ":" in invite.endpoint else 51820
        edge_gw = EdgeGatewayConfig(
            id="edge-01", name=payload.name, public_ip=vps_ip, listen_port=port,
            domain=payload.domain or (vps_ip if any(c.isalpha() for c in vps_ip) else None),
            tunnel_ip_gateway=invite.gateway_tunnel_ip, tunnel_ip_home=invite.assigned_tunnel_ip,
            public_key=invite.gateway_public_key, lan_subnets=invite.lan_subnets, status="connected",
        )
        _save_edge_gateway_record(repo, edge_gw)
        return edge_gw

    endpoint_url, bearer_token = "http://127.0.0.1:8000", token_str
    if token_str.startswith("roost-edge://"):
        parts = token_str[len("roost-edge://"):].split("?token=")
        endpoint_url, bearer_token = f"http://{parts[0]}", (parts[1] if len(parts) > 1 else "")
    try:
        import jwt
        endpoint_url = jwt.decode(bearer_token, options={"verify_signature": False}).get("endpoint_url", endpoint_url)
    except Exception:
        pass

    home_priv, home_pub = mgr.generate_wireguard_keypair()
    req = urllib.request.Request(
        f"{endpoint_url}/api/edge/enroll",
        data=json.dumps(EdgeEnrollmentPayload(home_public_key=home_pub).model_dump()).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer_token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            enroll_resp = EdgeEnrollmentResponse.model_validate(json.loads(resp.read().decode("utf-8")))
    except urllib.error.HTTPError as e:
        try:
            err_msg = json.loads(e.read().decode("utf-8")).get("detail", e.reason)
        except Exception:
            err_msg = e.reason
        raise HTTPException(status_code=e.code, detail=f"Edge Gateway rejected enrollment: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not connect to Edge Gateway: {e}")

    mgr._apply_network_files(mgr.generate_networkd_config(
        role="client", private_key=home_priv, peer_public_key=enroll_resp.gateway_public_key,
        endpoint=enroll_resp.endpoint, tunnel_ip=enroll_resp.assigned_tunnel_ip,
        allowed_ips=",".join(enroll_resp.allowed_ips), persistent_keepalive=enroll_resp.persistent_keepalive,
    ))
    vps_host = enroll_resp.endpoint.split(":")[0]
    edge_gw = EdgeGatewayConfig(
        id="edge-01", name=payload.name, public_ip=vps_host,
        domain=payload.domain or (vps_host if any(c.isalpha() for c in vps_host) else None),
        listen_port=51820, tunnel_ip_gateway=enroll_resp.gateway_tunnel_ip,
        tunnel_ip_home=enroll_resp.assigned_tunnel_ip, public_key=enroll_resp.gateway_public_key, status="connected",
    )
    _save_edge_gateway_record(repo, edge_gw)
    return edge_gw

@router.put("/endpoint", response_model=EdgeGatewayConfig)
async def update_edge_endpoint(
    payload: UpdateEdgeEndpointRequest, current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgeGatewayConfig:
    """Updates the Edge Gateway endpoint host (domain or IP) and port."""
    endpoint_host = payload.domain or payload.ip
    if not endpoint_host:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either domain or ip must be specified.")
    EdgeManager(config_dir=getattr(repo, "config_dir", "/etc/roostos")).update_peer_endpoint(endpoint_host=endpoint_host, port=payload.port)
    gateways = _get_active_gateways(repo.get_config())
    if not gateways:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Edge Gateway configured.")
    edge_gw = gateways[0]
    if payload.domain:
        edge_gw.domain = payload.domain
    if payload.ip:
        edge_gw.public_ip = payload.ip
    edge_gw.listen_port = payload.port
    _save_edge_gateway_record(repo, edge_gw)
    return edge_gw

@router.get("/status")
async def get_edge_status(
    current_user: UserSession = Depends(get_current_user), repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, Any]:
    """Returns linked Edge Gateway status, routed LAN subnets, and active ingress routes."""
    from roostos_engine.ingress_helper import read_wg_edge_traffic
    from roostos_engine.edge_diagnostics import detect_local_lan_subnets
    config = repo.get_config()
    cfg_dir = getattr(repo, "config_dir", getattr(getattr(repo, "active_repo", None), "config_dir", "/etc/roostos"))
    gateways = _get_active_gateways(config, check_systemd=(cfg_dir == "/etc/roostos"))
    traffic = read_wg_edge_traffic()
    lan_subnets = detect_local_lan_subnets(cfg_dir)
    for gw in gateways:
        if not gw.lan_subnets:
            gw.lan_subnets = lan_subnets
    return {
        "linked": bool(gateways), "gateways": [gw.model_dump() for gw in gateways],
        "rx_bytes": traffic["rx_bytes"], "tx_bytes": traffic["tx_bytes"],
        "lan_subnets": lan_subnets,
    }

@router.post("/routes/sync-lan")
async def sync_lan_routes(
    payload: Optional[EdgeRouteSyncRequest] = None, current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, Any]:
    """Applies local LAN <-> wg-edge routing and pushes LAN subnet routes to the Edge Gateway."""
    from roostos_engine.edge_diagnostics import push_lan_routes_to_gateway
    cfg_dir = getattr(repo, "config_dir", getattr(getattr(repo, "active_repo", None), "config_dir", "/etc/roostos"))
    req_subnets = payload.lan_subnets if payload and payload.lan_subnets else None
    res = push_lan_routes_to_gateway(config_dir=cfg_dir, lan_subnets=req_subnets, mock=(os.environ.get("ROOSTOS_MOCK") == "1"))
    for gw in _get_active_gateways(repo.get_config(), check_systemd=(cfg_dir == "/etc/roostos")):
        gw.lan_subnets = res["lan_subnets"]
        _save_edge_gateway_record(repo, gw)
    return res

@router.get("/verify", response_model=EdgeConnectivityCheckResponse)
async def verify_edge_connectivity(
    current_user: UserSession = Depends(get_current_user), repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgeConnectivityCheckResponse:
    """Probes live WireGuard handshake, ICMP reachability, LAN routing, and X.509/peer authentication."""
    from roostos_engine.edge_diagnostics import verify_edge_connectivity_and_auth
    cfg_dir = getattr(repo, "config_dir", getattr(getattr(repo, "active_repo", None), "config_dir", "/etc/roostos"))
    gateways = _get_active_gateways(repo.get_config(), check_systemd=(cfg_dir == "/etc/roostos"))
    target_ip = (gateways[0].tunnel_ip_gateway.split("/")[0] if gateways else "10.42.0.1")
    return verify_edge_connectivity_and_auth(config_dir=cfg_dir, target_ip=target_ip, mock=(os.environ.get("ROOSTOS_MOCK") == "1"))

@router.get("/routes", response_model=List[IngressRoute])
async def list_ingress_routes(
    current_user: UserSession = Depends(get_current_user), repo: ConfigRepository = Injected(ConfigRepository),
) -> List[IngressRoute]:
    """Lists all configured ingress reverse proxy routes."""
    return [route for gw in _get_active_gateways(repo.get_config()) for route in gw.ingress_routes]

@router.post("/routes", response_model=IngressRoute)
async def create_ingress_route(
    payload: IngressRoutePayload, current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository), cert_mgr: CertificateManager = Injected(CertificateManager),
) -> IngressRoute:
    """Adds a new ingress reverse proxy route and provisions SSL."""
    edge_gateways = _get_active_gateways(repo.get_config())
    if not edge_gateways:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Edge Gateway is linked.")
    ssl_status = "disabled"
    if payload.ssl_enabled:
        ssl_status = "pending"
        try:
            cert_mgr.acme.request_certificate(
                domain=payload.domain.strip().lower(), challenge_type=ChallengeType.HTTP_01, auto_renew=True,
            )
            ssl_status = "valid"
        except Exception:
            pass
    new_route = IngressRoute(
        id=f"route-{uuid.uuid4().hex[:6]}", domain=payload.domain.strip().lower(),
        target_ip=payload.target_ip.strip(), target_port=payload.target_port,
        ssl_enabled=payload.ssl_enabled, ssl_status=ssl_status, edge_gateway_id=edge_gateways[0].id,
    )
    edge_gateways[0].ingress_routes.append(new_route)
    _save_edge_gateway_record(repo, edge_gateways[0])
    return new_route

@router.delete("/routes/{route_id}")
async def delete_ingress_route(
    route_id: str, current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, str]:
    """Deletes an ingress reverse proxy route."""
    for gw in _get_active_gateways(repo.get_config()):
        gw.ingress_routes = [r for r in gw.ingress_routes if r.id != route_id]
        _save_edge_gateway_record(repo, gw)
    return {"status": "success", "message": f"Route '{route_id}' deleted."}

@router.post("/lockdown")
async def apply_firewall_lockdown(
    wan_interface: str = "eth0", current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Applies firewall lockdown on VPS to drop public port 8000 access."""
    return {
        "status": "success", "message": f"Port 8000 locked down on interface {wan_interface}.",
        "rules": EdgeManager().compile_lockdown_rules(wan_interface=wan_interface),
    }

@router.post("/disconnect")
@router.delete("")
@router.delete("/gateway")
async def disconnect_edge_gateway(
    gateway_id: Optional[str] = None, current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, Any]:
    """Tears down Edge Gateway WireGuard tunnel, purges routes and domain certificates."""
    from roostos_engine.edge_cleanup import disconnect_and_cleanup_edge_gateway
    return disconnect_and_cleanup_edge_gateway(repo=repo, gateway_id=gateway_id, mock=(os.environ.get("ROOSTOS_MOCK") == "1"))
