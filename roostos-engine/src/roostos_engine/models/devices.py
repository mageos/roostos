from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class PersonConfig(BaseModel):
    id: str
    name: str
    dns_profile: Optional[str] = None

class BuildingConfig(BaseModel):
    id: str
    name: str

class RoomConfig(BaseModel):
    id: str
    name: str
    building: str

class UPnPAllowedPort(BaseModel):
    port: int
    protocol: str

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if v.lower() not in ("tcp", "udp"):
            raise ValueError(f"UPnP protocol '{v}' must be 'tcp' or 'udp'")
        return v.lower()

class DeviceConfig(BaseModel):
    mac: str
    name: str
    owner: Optional[str] = None
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    static_ip: Optional[str] = None
    upnp_trusted: bool = False
    upnp_allowed_ports: List[UPnPAllowedPort] = Field(default_factory=list)
    gateway: Optional[str] = None
    max_download_kbps: Optional[int] = None
    max_upload_kbps: Optional[int] = None

    @field_validator("mac")
    @classmethod
    def normalize_mac(cls, v: str) -> str:
        mac = v.replace("-", ":").replace(".", ":").lower()
        parts = mac.split(":")
        if len(parts) != 6 or not all(len(p) <= 2 for p in parts):
            raise ValueError(f"Invalid MAC address format: '{v}'")
        return ":".join(p.zfill(2) for p in parts)

class DevicesConfig(BaseModel):
    people: List[PersonConfig] = Field(default_factory=list)
    buildings: List[BuildingConfig] = Field(default_factory=list)
    rooms: List[RoomConfig] = Field(default_factory=list)
    devices: List[DeviceConfig] = Field(default_factory=list)
