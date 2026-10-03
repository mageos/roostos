"""Domain models and DTOs for the RoostOS CLI and setup system."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class NodeRole(str, Enum):
    """Supported node roles for deployment."""
    GATEWAY = "gateway"
    CONTROLLER = "controller"
    STANDALONE = "standalone"
    COMPUTE = "compute"
    WORKSTATION = "workstation"
    EDGE_GATEWAY = "edge_gateway"
    CUSTOM = "custom"


class InterfaceInfo(BaseModel):
    """Network adapter hardware descriptor."""
    name: str
    mac_address: Optional[str] = None
    operstate: str = "unknown"
    speed_mbps: Optional[int] = None
    is_wireless: bool = False
    driver: Optional[str] = None


class DiscoveredService(BaseModel):
    """Remote service discovered via mDNS on the LAN."""
    name: str
    ip: str
    port: int
    service_type: str  # "controller", "gateway"
    properties: Dict[str, Any] = Field(default_factory=dict)


class SystemEnvironment(BaseModel):
    """Introspected host hardware, chassis, and network state."""
    arch: str = "x86_64"
    cpu_cores: int = 1
    memory_total_mb: int = 1024
    memory_free_mb: int = 512
    disk_total_gb: float = 16.0
    disk_free_gb: float = 8.0
    interfaces: List[InterfaceInfo] = Field(default_factory=list)
    is_laptop: bool = False
    discovered_controllers: List[DiscoveredService] = Field(default_factory=list)
    discovered_gateways: List[DiscoveredService] = Field(default_factory=list)
    recommended_role: NodeRole = NodeRole.STANDALONE
    recommendation_reason: str = ""


class GatewayConfigParams(BaseModel):
    """User-supplied parameters for Gateway Router role."""
    wan_interface: str
    wan_proto: str = "dhcp"  # "dhcp", "static", "pppoe"
    wan_ip: Optional[str] = None
    wan_gateway: Optional[str] = None
    lan_interfaces: List[str] = Field(default_factory=list)
    lan_network: str = "192.168.1.0/24"
    lan_ip: str = "192.168.1.1"
    dhcp_enabled: bool = True
    dhcp_start: str = "192.168.1.100"
    dhcp_end: str = "192.168.1.250"
    dns_servers: List[str] = Field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])


class ControllerConfigParams(BaseModel):
    """User-supplied parameters for Controller role."""
    cluster_name: str = "RoostOS Home"
    domain: str = "roostos.local"
    admin_username: str = "admin"
    admin_password: Optional[str] = None
    adopted_gateway_ip: Optional[str] = None
    enable_dns_container: bool = True
    enable_samba_ad: bool = False


class WorkstationConfigParams(BaseModel):
    """User-supplied parameters for Workstation role."""
    controller_host: str = "roostos.local"
    controller_port: int = 1883
    join_token: Optional[str] = None
    enable_domain_login: bool = False
    family_user_mapping: Dict[str, str] = Field(default_factory=dict)


class EdgeGatewayConfigParams(BaseModel):
    """User-supplied parameters for Edge Gateway role."""
    wan_interface: str = "eth0"
    public_ip: Optional[str] = None
    listen_port: int = 51820
    tunnel_subnet: str = "10.42.0.0/24"
    enable_nginx_ingress: bool = True


class SetupResult(BaseModel):
    """Result of running the setup wizard."""
    success: bool
    role: NodeRole
    installed_packages: List[str] = Field(default_factory=list)
    created_configs: List[str] = Field(default_factory=list)
    dashboard_url: Optional[str] = None
    message: str = ""
