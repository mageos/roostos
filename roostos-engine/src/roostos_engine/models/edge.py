"""Domain models and DTOs for RoostOS Edge Gateway and Ingress Reverse Proxy."""

from typing import List, Optional
from pydantic import BaseModel, Field


class IngressRoute(BaseModel):
    """Configuration mapping an external domain to an internal target application."""
    id: str
    domain: str
    target_ip: str
    target_port: int
    ssl_enabled: bool = True
    edge_gateway_id: str = "edge-01"


class EdgeGatewayConfig(BaseModel):
    """Declarative configuration for a linked VPS Edge Gateway."""
    id: str = "edge-01"
    name: str = "VPS Edge Gateway"
    public_ip: str
    listen_port: int = 51820
    tunnel_ip_gateway: str = "10.42.0.1/24"
    tunnel_ip_home: str = "10.42.0.2/24"
    public_key: Optional[str] = None
    status: str = "disconnected"  # "disconnected", "connected", "pending"
    last_handshake: Optional[str] = None
    ingress_routes: List[IngressRoute] = Field(default_factory=list)


class EdgeBootstrapToken(BaseModel):
    """Payload for bootstrap token generated on the VPS Edge Gateway."""
    token: str
    endpoint_url: str
    expires_at: int
    public_ip: str


class EdgeEnrollmentPayload(BaseModel):
    """Payload sent by Home Server to the VPS Edge Gateway enrollment API."""
    home_public_key: str
    hostname: str = "roost-home"
    requested_tunnel_ip: str = "10.42.0.2/24"


class EdgeEnrollmentResponse(BaseModel):
    """Response returned by the VPS Edge Gateway to the Home Server."""
    status: str = "success"
    gateway_public_key: str
    endpoint: str
    assigned_tunnel_ip: str = "10.42.0.2/24"
    gateway_tunnel_ip: str = "10.42.0.1/24"
    allowed_ips: List[str] = Field(default_factory=lambda: ["10.42.0.0/24"])
    persistent_keepalive: int = 25
    message: str = "Edge Gateway enrolled successfully."


class GenerateTokenRequest(BaseModel):
    public_ip: Optional[str] = None
    port: int = 8000
    ttl_minutes: int = 15
    use_https: bool = False


class ConnectEdgeRequest(BaseModel):
    token: str
    name: str = "VPS Edge Gateway"


class IngressRoutePayload(BaseModel):
    domain: str
    target_ip: str
    target_port: int
    ssl_enabled: bool = True
