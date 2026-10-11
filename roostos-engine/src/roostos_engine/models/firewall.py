from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

class PortForwardConfig(BaseModel):
    name: str
    protocol: str = "tcp"
    external_port: int = 0
    internal_ip: str = ""
    internal_port: int = 0
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "external_port" not in data and "wan_port" in data:
                data["external_port"] = data["wan_port"]
            if "internal_ip" not in data and "lan_ip" in data:
                data["internal_ip"] = data["lan_ip"]
            if "internal_port" not in data and "lan_port" in data:
                data["internal_port"] = data["lan_port"]
        return data

    @property
    def wan_port(self) -> int:
        return self.external_port

    @property
    def lan_ip(self) -> str:
        return self.internal_ip

    @property
    def lan_port(self) -> int:
        return self.internal_port

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if v.lower() not in ("tcp", "udp"):
            raise ValueError(f"Port forward protocol '{v}' must be 'tcp' or 'udp'")
        return v.lower()

class InputRuleConfig(BaseModel):
    name: str
    interface: str = "*"          # "*" = all interfaces, or "eth0", "br0", etc.
    protocol: str = "tcp"         # "tcp", "udp", "tcp/udp"
    port: int
    source: Optional[str] = None  # Optional source IP/CIDR filter, e.g. "192.168.1.0/24"
    action: str = "accept"        # "accept" or "drop"
    enabled: bool = True

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if v.lower() not in ("tcp", "udp", "tcp/udp"):
            raise ValueError(f"Input rule protocol '{v}' must be 'tcp', 'udp', or 'tcp/udp'")
        return v.lower()

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v.lower() not in ("accept", "drop"):
            raise ValueError(f"Input rule action '{v}' must be 'accept' or 'drop'")
        return v.lower()

class FirewallSettings(BaseModel):
    port_forwards: List[PortForwardConfig] = Field(default_factory=list)
    rules: List[InputRuleConfig] = Field(default_factory=list)
    block_doh: bool = False
    block_vpns: bool = False
    block_quic: bool = False
    custom_doh_ips: List[str] = Field(default_factory=list)
    custom_vpn_ips: List[str] = Field(default_factory=list)

class FirewallConfig(BaseModel):
    firewall: Optional[FirewallSettings] = Field(default_factory=FirewallSettings)

    @model_validator(mode="before")
    @classmethod
    def normalize_firewall(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "firewall" not in data:
                keys = {"rules", "port_forwards", "block_doh", "block_vpns", "block_quic", "custom_doh_ips", "custom_vpn_ips"}
                if any(k in data for k in keys):
                    return {"firewall": data}
        return data

