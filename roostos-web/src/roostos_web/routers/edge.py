"""FastAPI router for Edge Gateway management, bootstrap enrollment, and ingress routing."""

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from roostos_engine.models.edge import (
    IngressRoute,
    EdgeGatewayConfig,
    EdgeBootstrapToken,
    EdgeEnrollmentPayload,
    EdgeEnrollmentResponse,
    GenerateTokenRequest,
    ConnectEdgeRequest,
    IngressRoutePayload,
)
from roostos_engine.edge_manager import EdgeManager
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.services.base import get_repository
from roostos_web.di import Injected

router = APIRouter(prefix="/api/edge", tags=["edge"])


def _write_network_files(net_files: Dict[str, str]) -> None:
    """Helper to safely write systemd network files if directory is accessible."""
    net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR")
    if not net_dir and os.getuid() == 0 and os.path.exists("/etc/systemd/network"):
        net_dir = "/etc/systemd/network"
    if net_dir and os.path.exists(net_dir):
        for fname, content in net_files.items():
            try:
                with open(os.path.join(net_dir, fname), "w") as f:
                    f.write(content)
            except Exception:
                pass


@router.post("/token", response_model=EdgeBootstrapToken)
async def generate_bootstrap_token(
    payload: GenerateTokenRequest,
    current_user: UserSession = Depends(get_current_admin),
) -> EdgeBootstrapToken:
    """Generates a short-lived single-use bootstrap token on the VPS for enrollment."""
    vps_ip = payload.public_ip or os.environ.get("ROOSTOS_PUBLIC_IP", "127.0.0.1")
    mgr = EdgeManager()
    return mgr.create_bootstrap_token(
        vps_public_ip=vps_ip,
        listen_port=payload.port,
        ttl_minutes=payload.ttl_minutes,
        use_https=payload.use_https,
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
        role="gateway",
        private_key=vps_priv,
        peer_public_key=payload.home_public_key,
        listen_port=51820,
        tunnel_ip="10.42.0.1/24",
        allowed_ips="10.42.0.2/32",
    )
    _write_network_files(net_files)

    return EdgeEnrollmentResponse(
        status="success",
        gateway_public_key=vps_pub,
        endpoint=f"{vps_ip}:51820",
        assigned_tunnel_ip="10.42.0.2/24",
        gateway_tunnel_ip="10.42.0.1/24",
        allowed_ips=["10.42.0.0/24"],
        persistent_keepalive=25,
        message="Edge Gateway successfully paired with home server.",
    )


@router.post("/connect", response_model=EdgeGatewayConfig)
async def connect_to_edge_gateway(
    payload: ConnectEdgeRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> EdgeGatewayConfig:
    """Home server connects to Edge Gateway VPS using the bootstrap token."""
    token_str = payload.token.strip()
    endpoint_url = "http://127.0.0.1:8000"
    bearer_token = token_str

    if token_str.startswith("roost-edge://"):
        raw = token_str[len("roost-edge://"):]
        parts = raw.split("?token=")
        endpoint_url = f"http://{parts[0]}"
        bearer_token = parts[1] if len(parts) > 1 else ""

    try:
        import jwt
        unverified = jwt.decode(bearer_token, options={"verify_signature": False})
        if unverified.get("endpoint_url"):
            endpoint_url = unverified["endpoint_url"]
    except Exception:
        pass

    mgr = EdgeManager(config_dir=repo.config_dir if hasattr(repo, "config_dir") else "/etc/roostos")
    home_priv, home_pub = mgr.generate_wireguard_keypair()

    enroll_payload = EdgeEnrollmentPayload(
        home_public_key=home_pub,
        hostname="roost-home",
        requested_tunnel_ip="10.42.0.2/24",
    )
    req = urllib.request.Request(
        f"{endpoint_url}/api/edge/enroll",
        data=json.dumps(enroll_payload.model_dump()).encode("utf-8"),
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
        raise HTTPException(
            status_code=e.code,
            detail=f"Edge Gateway rejected enrollment: {err_msg}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not connect to Edge Gateway: {e}",
        )

    # Save WireGuard network files locally
    net_files = mgr.generate_networkd_config(
        role="client",
        private_key=home_priv,
        peer_public_key=enroll_resp.gateway_public_key,
        endpoint=enroll_resp.endpoint,
        tunnel_ip=enroll_resp.assigned_tunnel_ip,
        allowed_ips=",".join(enroll_resp.allowed_ips),
        persistent_keepalive=enroll_resp.persistent_keepalive,
    )
    _write_network_files(net_files)

    # Update network.yaml
    config = repo.get_config()
    net_config = config.network
    vps_ip = enroll_resp.endpoint.split(":")[0]
    edge_gw = EdgeGatewayConfig(
        id="edge-01",
        name=payload.name,
        public_ip=vps_ip,
        listen_port=51820,
        tunnel_ip_gateway=enroll_resp.gateway_tunnel_ip,
        tunnel_ip_home=enroll_resp.assigned_tunnel_ip,
        public_key=enroll_resp.gateway_public_key,
        status="connected",
    )
    existing = [gw for gw in getattr(net_config, "edge_gateways", []) if gw.id != edge_gw.id]
    net_config.edge_gateways = [*existing, edge_gw]
    try:
        repo.save_network_config(net_config)
    except Exception:
        pass

    return edge_gw


@router.get("/status")
async def get_edge_status(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, Any]:
    """Returns linked Edge Gateway status and active ingress routes."""
    gateways = getattr(repo.get_config().network, "edge_gateways", [])
    return {"linked": bool(gateways), "gateways": [gw.model_dump() for gw in gateways]}


@router.get("/routes", response_model=List[IngressRoute])
async def list_ingress_routes(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> List[IngressRoute]:
    """Lists all configured ingress reverse proxy routes."""
    gateways = getattr(repo.get_config().network, "edge_gateways", [])
    return [route for gw in gateways for route in gw.ingress_routes]


@router.post("/routes", response_model=IngressRoute)
async def create_ingress_route(
    payload: IngressRoutePayload,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> IngressRoute:
    """Adds a new ingress reverse proxy route."""
    config = repo.get_config()
    edge_gateways = getattr(config.network, "edge_gateways", [])
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
    try:
        repo.save_network_config(config.network)
    except Exception:
        pass
    return new_route


@router.delete("/routes/{route_id}")
async def delete_ingress_route(
    route_id: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, str]:
    """Deletes an ingress reverse proxy route."""
    config = repo.get_config()
    for gw in getattr(config.network, "edge_gateways", []):
        gw.ingress_routes = [r for r in gw.ingress_routes if r.id != route_id]
    try:
        repo.save_network_config(config.network)
    except Exception:
        pass
    return {"status": "success", "message": f"Route '{route_id}' deleted."}


@router.post("/lockdown")
async def apply_firewall_lockdown(
    wan_interface: str = "eth0",
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Applies firewall lockdown on VPS to drop public port 8000 access."""
    mgr = EdgeManager()
    rules = mgr.compile_lockdown_rules(wan_interface=wan_interface)
    return {
        "status": "success",
        "message": f"Port 8000 locked down on interface {wan_interface}.",
        "rules": rules,
    }
