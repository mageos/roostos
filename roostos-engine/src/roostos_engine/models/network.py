from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator

class PPPoEConfig(BaseModel):
    username: str
    password: str

class NetworkInterface(BaseModel):
    name: str
    network: str = Field(alias="role")  # maps role/network
    protocol: Optional[str] = None      # "dhcp", "static", "pppoe", "pptp", "l2tp"
    vlan_tag: Optional[int] = None
    pppoe: Optional[PPPoEConfig] = None
    dhcp: Optional[bool] = None
    bridge: Optional[str] = None
    ip: Optional[str] = None
    gateway: Optional[str] = None
    ipv6: Optional[bool] = None

    model_config = {
        "populate_by_name": True
    }

    @field_validator("network", mode="before")
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v not in ("wan", "lan"):
            raise ValueError(f"Network interface role '{v}' must be 'wan' or 'lan'")
        return v

    @property
    def role(self) -> str:
        return self.network

    @role.setter
    def role(self, value: str) -> None:
        self.network = value

class NetworkBridge(BaseModel):
    name: str
    ip: str
    isolate: bool = False
    dhcp_enabled: bool = True
    dhcp_pool_start: Optional[str] = None
    dhcp_pool_end: Optional[str] = None

class NetworkVlan(BaseModel):
    name: str
    id: int
    interface: str
    ip: str
    isolate: bool = True
    dhcp_enabled: bool = True
    dhcp_pool_start: Optional[str] = None
    dhcp_pool_end: Optional[str] = None

class NetworkGateway(BaseModel):
    id: str
    name: str
    interface: str
    type: str = "dhcp"
    metric: int = 10

class QoSConfig(BaseModel):
    enabled: bool = False
    wan_upload_kbps: Optional[int] = None
    wan_download_kbps: Optional[int] = None
    prioritize_tags: List[str] = Field(default_factory=list)

class ZoneConfig(BaseModel):
    id: str
    name: str
    interfaces: List[str] = Field(default_factory=list)
    isolate: bool = False
    allow_zones: List[str] = Field(default_factory=list)
    masquerade: bool = False

class NetworkSettings(BaseModel):
    interfaces: List[NetworkInterface] = Field(default_factory=list)
    bridges: List[NetworkBridge] = Field(default_factory=list)
    vlans: List[NetworkVlan] = Field(default_factory=list)
    zones: List[ZoneConfig] = Field(default_factory=list)
    gateways: List[NetworkGateway] = Field(default_factory=list)
    qos: Optional[QoSConfig] = Field(default_factory=QoSConfig)

class WifiRadio(BaseModel):
    interface: str
    band: str  # "2.4ghz", "5ghz", "both"
    channel: Union[str, int] = "auto"
    width: int = 20  # 20, 40, 80, 160
    tx_power: str = "high"  # "low", "medium", "high"

class WifiAccessPoint(BaseModel):
    name: Optional[str] = None
    ssid: str
    interface: Optional[str] = None
    passphrase: str
    security: str = "wpa3-sae"  # "wpa2-psk", "wpa3-sae", "mixed"
    radio: Optional[str] = None
    bridge: Optional[str] = None
    vlan: Optional[int] = None

class WifiMesh(BaseModel):
    enabled: bool = False
    interface: str
    ssid: str
    passphrase: str
    frequency: int = 5180

class WifiSettings(BaseModel):
    radios: List[WifiRadio] = Field(default_factory=list)
    access_points: List[WifiAccessPoint] = Field(default_factory=list)
    mesh: Optional[WifiMesh] = None

class VPNConfig(BaseModel):
    id: str
    name: str
    type: str = "wireguard"  # "wireguard" or "openvpn"
    role: str = "client"     # "client" or "server"
    enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)

class NetworkConfig(BaseModel):
    network: Optional[NetworkSettings] = Field(default_factory=NetworkSettings)
    wifi: Optional[WifiSettings] = None
    vpns: List[VPNConfig] = Field(default_factory=list)
