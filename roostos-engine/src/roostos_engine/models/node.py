from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class NodeRole(str, Enum):
    CONTROLLER = "controller"
    GATEWAY_ROUTER = "gateway_router"
    ACCESS_POINT = "access_point"
    DNS_RESOLVER = "dns_resolver"
    COMPUTE_NODE = "compute_node"
    SWITCH = "switch"
    EDGE_GATEWAY = "edge_gateway"


class InterfaceType(str, Enum):
    ETHERNET = "ethernet"
    WIFI_RADIO = "wifi_radio"
    SFP = "sfp"
    CELLULAR = "cellular"
    BRIDGE = "bridge"
    VLAN = "vlan"


class InterfaceMode(str, Enum):
    ACCESS = "access"
    TRUNK = "trunk"
    WAN = "wan"
    MESH = "mesh"
    UNASSIGNED = "unassigned"


class WifiRadioSettings(BaseModel):
    band: Optional[str] = "2.4ghz"  # "2.4ghz", "5ghz", "6ghz"
    channel: Optional[int] = None
    channel_width: Optional[str] = "auto"
    tx_power_dbm: Optional[int] = None


class NodeInterface(BaseModel):
    name: str  # Local interface name e.g. "eth0", "wlan0"
    mac_address: Optional[str] = None
    type: InterfaceType = InterfaceType.ETHERNET
    network_id: Optional[str] = None  # Reference to Network.id
    mode: InterfaceMode = InterfaceMode.UNASSIGNED
    vlan_tag: Optional[int] = None
    bridge: Optional[str] = None
    wifi_settings: Optional[WifiRadioSettings] = None

    @field_validator("mac_address")
    @classmethod
    def normalize_mac(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.lower().strip()
        return v


class DetectedHardwareInterface(BaseModel):
    name: str
    mac_address: Optional[str] = None
    type: InterfaceType = InterfaceType.ETHERNET
    speed_mbps: Optional[int] = None
    driver: Optional[str] = None
    operstate: Optional[str] = "unknown"
    is_wireless: bool = False
    wireless_bands: List[str] = Field(default_factory=list)


class NodeCapabilities(BaseModel):
    has_wifi: bool = False
    nic_count: int = 1
    cpu_arch: str = "x86_64"
    cpu_cores: int = 1
    total_memory_mb: int = 1024
    has_kvm: bool = False


class NodeConfig(BaseModel):
    id: str
    name: str
    roles: List[NodeRole] = Field(default_factory=lambda: [NodeRole.GATEWAY_ROUTER])
    management_ip: Optional[str] = None
    mac_address: Optional[str] = None
    location_id: Optional[str] = None  # Foreign key to RoomConfig.id
    interfaces: List[NodeInterface] = Field(default_factory=list)
    failover_priority: int = 0
    capabilities: Optional[NodeCapabilities] = Field(default_factory=NodeCapabilities)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[NodeRole]) -> List[NodeRole]:
        if not v:
            raise ValueError("Node must have at least one assigned role.")
        return v


class NodesConfigFile(BaseModel):
    nodes: List[NodeConfig] = Field(default_factory=list)


class NodeJoinRequest(BaseModel):
    token: str
    node_id: str
    name: str
    roles: List[NodeRole] = Field(default_factory=lambda: [NodeRole.GATEWAY_ROUTER])
    management_ip: Optional[str] = None
    mac_address: Optional[str] = None
    location_id: Optional[str] = None
    failover_priority: int = 0
    capabilities: Optional[NodeCapabilities] = Field(default_factory=NodeCapabilities)
    interfaces: List[NodeInterface] = Field(default_factory=list)


class NodeJoinResponse(BaseModel):
    status: str = "success"
    node_id: str
    controller_url: str
    message: str = "Node registered successfully"


class NodeHeartbeatRequest(BaseModel):
    status: str = "healthy"
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    updates_status: Optional[Dict[str, Any]] = None


class NodeHeartbeatResponse(BaseModel):
    status: str = "acknowledged"
    commands: List[str] = Field(default_factory=list)
    epoch: Optional[int] = None
    master_node_id: Optional[str] = None


class NodeConfigSlice(BaseModel):
    node_id: str
    name: str
    roles: List[str] = Field(default_factory=list)
    controller_url: Optional[str] = None
    dns_servers: List[str] = Field(default_factory=list)
    interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    bridges: List[Dict[str, Any]] = Field(default_factory=list)
    vlans: List[Dict[str, Any]] = Field(default_factory=list)
    wifi_access_points: List[Dict[str, Any]] = Field(default_factory=list)


class ClusterStateManifest(BaseModel):
    epoch: int = 1
    master_node_id: str = "node-01"
    controller_url: Optional[str] = None
    generated_at: str = ""
    hashes: Dict[str, str] = Field(default_factory=dict)


class ClusterStateBundle(BaseModel):
    epoch: int = 1
    master_node_id: str = "node-01"
    files: Dict[str, str] = Field(default_factory=dict)


class ClusterPromotionRequest(BaseModel):
    new_epoch: Optional[int] = None
    force: bool = False


class ClusterPromotionResponse(BaseModel):
    status: str = "promoted"
    node_id: str
    epoch: int
    role: str = "controller"
    message: str = "Node successfully promoted to cluster controller."

