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
    capabilities: Optional[NodeCapabilities] = Field(default_factory=NodeCapabilities)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[NodeRole]) -> List[NodeRole]:
        if not v:
            raise ValueError("Node must have at least one assigned role.")
        return v


class NodesConfigFile(BaseModel):
    nodes: List[NodeConfig] = Field(default_factory=list)
