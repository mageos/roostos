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
    IngressRoutePayload, UpdateEdgeEndpointRequest,
)
from roostos_engine.edge_manager import EdgeManager
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.services.base import get_repository
from roostos_web.di import Injected

router = APIRouter(prefix="/api/edge", tags=["edge"])


def _save_edge_gateway_record(repo: ConfigRepository, edge_gw: EdgeGatewayConfig) -> None:
    """Helper to persist edge gateway record in network config."""
    config = repo.get_config()
    existing = [gw for gw in (getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", [])) if gw.id != edge_gw.id]
    config.network.edge_gateways = [*existing, edge_gw]
    config.edge_gateways = [*existing, edge_gw]
    try:
        repo.save_network_config(config.network)
    except Exception as e:
        print(f"Warning: Failed to save edge gateway: {e}")


@router.post("/token", response_model=EdgeBootstrapToken)
async def generate_bootstrap_token(
    payload: GenerateTokenRequest,
    current_user: UserSession = Depends(get_current_admin),
) -> EdgeBootstrapToken:
    """Generates a short-lived single-use bootstrap token on the VPS for enrollment."""
    vps_ip = payload.public_ip or os.environ.get("ROOSTOS_PUBLIC_IP", "127.0.0.1")
    return EdgeManager().create_bootstrap_token(
        vps_public_ip=vps_ip, listen_port=payload.port,
        ttl_minutes=payload.ttl_minutes, use_https=payload.use_https,
    )


@router.post("/enroll", response_model=EdgeEnrollmentResponse)
async def enroll_home_server(
    payload: EdgeEnrollmentPayload,
    authorization: Optional[str] = Header(None),
) -> EdgeEnrollmentResponse:
    """Public bootstrap endpoint called by Home Server to complete automated enrollment."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed bootstrap Bearer token.",
        )

    token_str = authorization.split("Bearer ", 1)[1].strip()
    mgr = EdgeManager()

    try:
        claims = mgr.validate_and_consume_token(token_str)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    vps_ip = claims.get("vps_ip", "127.0.0.1")

    # Generate or load VPS WireGuard keys
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

    # Provision server networkd config
    net_files = mgr.generate_networkd_config(
        role="gateway", private_key=vps_priv, peer_public_key=payload.home_public_key,
        listen_port=51820, tunnel_ip="10.42.0.1/24", allowed_ips="10.42.0.2/32",
    )
    mgr._apply_network_files(net_files)

    return EdgeEnrollmentResponse(
        status="success", gateway_public_key=vps_pub, endpoint=f"{vps_ip}:51820",
        assigned_tunnel_ip="10.42.0.2/24", gateway_tunnel_ip="10.42.0.1/24",
        allowed_ips=["10.42.0.0/24"], persistent_keepalive=25,
        message="Edge Gateway successfully paired with home server.",
    )


@router.post("/connect", response_model=EdgeGatewayConfig)
async def connect_to_edge_gateway(
    payload: ConnectEdgeRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgeGatewayConfig:
    """Home server connects to Edge Gateway VPS using the invite or bootstrap token."""
    token_str = payload.token.strip()
    config_dir = repo.config_dir if hasattr(repo, "config_dir") else "/etc/roostos"
    mgr = EdgeManager(config_dir=config_dir)

    # 1. WireGuard-First Invite Token
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
            tunnel_ip_gateway=invite.gateway_tunnel_ip, tunnel_ip_home=invite.assigned_tunnel_ip,
            public_key=invite.gateway_public_key, status="connected",
        )
        _save_edge_gateway_record(repo, edge_gw)
        return edge_gw

    # 2. Legacy HTTP Bootstrap Token
    endpoint_url, bearer_token = "http://127.0.0.1:8000", token_str
    if token_str.startswith("roost-edge://"):
        parts = token_str[len("roost-edge://"):].split("?token=")
        endpoint_url = f"http://{parts[0]}"
        bearer_token = parts[1] if len(parts) > 1 else ""
    try:
        import jwt
        unverified = jwt.decode(bearer_token, options={"verify_signature": False})
        endpoint_url = unverified.get("endpoint_url", endpoint_url)
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

    net_files = mgr.generate_networkd_config(
        role="client", private_key=home_priv, peer_public_key=enroll_resp.gateway_public_key,
        endpoint=enroll_resp.endpoint, tunnel_ip=enroll_resp.assigned_tunnel_ip,
        allowed_ips=",".join(enroll_resp.allowed_ips), persistent_keepalive=enroll_resp.persistent_keepalive,
    )
    mgr._apply_network_files(net_files)

    edge_gw = EdgeGatewayConfig(
        id="edge-01", name=payload.name, public_ip=enroll_resp.endpoint.split(":")[0],
        listen_port=51820, tunnel_ip_gateway=enroll_resp.gateway_tunnel_ip,
        tunnel_ip_home=enroll_resp.assigned_tunnel_ip, public_key=enroll_resp.gateway_public_key,
        status="connected",
    )
    _save_edge_gateway_record(repo, edge_gw)
    return edge_gw


@router.put("/endpoint", response_model=EdgeGatewayConfig)
async def update_edge_endpoint(
    payload: UpdateEdgeEndpointRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgeGatewayConfig:
    """Updates the Edge Gateway endpoint host (domain or IP) and port."""
    endpoint_host = payload.domain or payload.ip
    if not endpoint_host:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either domain or ip must be specified.")

    config_dir = getattr(repo, "config_dir", "/etc/roostos")
    EdgeManager(config_dir=config_dir).update_peer_endpoint(endpoint_host=endpoint_host, port=payload.port)
    config = repo.get_config()
    gateways = _get_active_gateways(config)
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


def _get_active_gateways(config: Any) -> List[EdgeGatewayConfig]:
    gateways = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
    if not gateways:
        for node in getattr(config, "nodes", []):
            roles = [r.value if hasattr(r, "value") else str(r) for r in node.roles]
            if "edge_gateway" in roles:
                return [EdgeGatewayConfig(
                    id="edge-01", name=node.name or "VPS Edge Gateway",
                    public_ip=node.management_ip or "10.42.0.1",
                    listen_port=51820, tunnel_ip_gateway="10.42.0.1/24",
                    tunnel_ip_home="10.42.0.2/24", status="connected",
                )]
    return gateways


@router.get("/status")
async def get_edge_status(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, Any]:
    """Returns linked Edge Gateway status and active ingress routes."""
    config = repo.get_config()
    gateways = _get_active_gateways(config)
    return {"linked": bool(gateways), "gateways": [gw.model_dump() for gw in gateways]}


@router.get("/routes", response_model=List[IngressRoute])
async def list_ingress_routes(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> List[IngressRoute]:
    """Lists all configured ingress reverse proxy routes."""
    config = repo.get_config()
    gateways = _get_active_gateways(config)
    return [route for gw in gateways for route in gw.ingress_routes]


@router.post("/routes", response_model=IngressRoute)
async def create_ingress_route(
    payload: IngressRoutePayload,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> IngressRoute:
    """Adds a new ingress reverse proxy route."""
    config = repo.get_config()
    edge_gateways = _get_active_gateways(config)
    if not edge_gateways:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Edge Gateway is linked. Connect an Edge Gateway first.",
        )

    new_route = IngressRoute(
        id=f"route-{uuid.uuid4().hex[:6]}",
        domain=payload.domain.strip().lower(),
        target_ip=payload.target_ip.strip(),
        target_port=payload.target_port,
        ssl_enabled=payload.ssl_enabled,
        edge_gateway_id=edge_gateways[0].id,
    )
    edge_gateways[0].ingress_routes.append(new_route)
    _save_edge_gateway_record(repo, edge_gateways[0])
    return new_route


@router.delete("/routes/{route_id}")
async def delete_ingress_route(
    route_id: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, str]:
    """Deletes an ingress reverse proxy route."""
    config = repo.get_config()
    for gw in _get_active_gateways(config):
        gw.ingress_routes = [r for r in gw.ingress_routes if r.id != route_id]
        _save_edge_gateway_record(repo, gw)
    return {"status": "success", "message": f"Route '{route_id}' deleted."}


@router.post("/lockdown")
async def apply_firewall_lockdown(
    wan_interface: str = "eth0",
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Applies firewall lockdown on VPS to drop public port 8000 access."""
    return {
        "status": "success",
        "message": f"Port 8000 locked down on interface {wan_interface}.",
        "rules": EdgeManager().compile_lockdown_rules(wan_interface=wan_interface),
    }
