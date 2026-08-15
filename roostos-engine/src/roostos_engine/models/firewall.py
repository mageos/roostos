from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class PortForwardConfig(BaseModel):
    name: str
    protocol: str
    external_port: int
    internal_ip: str
    internal_port: int

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

class FirewallConfig(BaseModel):
    firewall: Optional[FirewallSettings] = Field(default_factory=FirewallSettings)
