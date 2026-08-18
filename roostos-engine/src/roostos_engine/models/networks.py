from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from roostos_engine.models.network import ZoneConfig, QoSConfig


class WifiSSIDConfig(BaseModel):
    ssid: str
    passphrase: Optional[str] = None
    security: str = "wpa3-sae"  # "wpa3-sae", "wpa2-psk", "wpa3-mixed", "open"
    hidden: bool = False
    isolate_clients: bool = False


class DHCPSettings(BaseModel):
    enabled: bool = True
    pool_start: Optional[str] = None
    pool_end: Optional[str] = None
    lease_time_seconds: int = 86400
    domain_name: Optional[str] = None
    dns_servers: List[str] = Field(default_factory=list)


class Network(BaseModel):
    id: str  # e.g. "lan", "iot", "guest", "management"
    name: str  # e.g. "Family LAN", "Smart Home IoT"
    subnet: str  # e.g. "192.168.1.0/24"
    vlan_tag: Optional[int] = None  # e.g. 20, 50
    gateway_ip: Optional[str] = None  # e.g. "192.168.1.1"
    dhcp: DHCPSettings = Field(default_factory=DHCPSettings)
    dns_servers: List[str] = Field(default_factory=list)
    wifi_ssids: List[WifiSSIDConfig] = Field(default_factory=list)
    isolate: bool = False  # If true, isolates traffic from other subnets
    zone_id: Optional[str] = "lan"  # Maps to ZoneConfig.id

    @field_validator("vlan_tag")
    @classmethod
    def validate_vlan_tag(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 4094):
            raise ValueError(f"VLAN tag must be between 1 and 4094, got {v}")
        return v


class NetworksConfigFile(BaseModel):
    networks: List[Network] = Field(default_factory=list)
    zones: List[ZoneConfig] = Field(default_factory=list)
    qos: Optional[QoSConfig] = Field(default_factory=QoSConfig)
