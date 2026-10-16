"""Pydantic schemas and DTOs for Multi-Network Kea DHCP Subsystem."""

from enum import Enum
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class HaModeEnum(str, Enum):
    """High-availability replication mode for DHCP servers."""
    STANDALONE = "standalone"
    HOT_STANDBY = "hot-standby"
    LOAD_BALANCING = "load-balancing"


class DhcpScopeDTO(BaseModel):
    """Configuration model for a managed subnet DHCP scope."""
    id: str = Field(..., description="Unique scope identifier (e.g. scope-lan)")
    name: str = Field(..., min_length=2, max_length=64, description="Friendly network name")
    node_id: str = Field(..., description="Authoritative cluster node hostname")
    ha_mode: HaModeEnum = Field(default=HaModeEnum.STANDALONE, description="HA replication mode")
    ha_standby_node: Optional[str] = Field(default=None, description="Standby node ID for failover")
    interface: str = Field(..., description="Linux interface or bridge (e.g. br-lan, vlan-iot)")
    subnet: str = Field(..., description="IPv4 CIDR network (e.g. 192.168.1.0/24)")
    gateway: str = Field(..., description="IPv4 Default Gateway IP")
    enabled: bool = Field(default=True, description="Whether scope dynamically allocates leases")
    pool_start: str = Field(..., description="First dynamic IP in range")
    pool_end: str = Field(..., description="Last dynamic IP in range")
    lease_time_seconds: int = Field(default=86400, ge=600, le=2592000, description="Lease TTL in seconds")
    dns_servers: List[str] = Field(default_factory=lambda: ["192.168.1.1"], description="DNS server IPs")
    domain_name: str = Field(default="lan.roost", description="Domain name handed to clients")
    authoritative: bool = Field(default=True, description="Authoritative response flag")
    active_leases_count: int = Field(default=0, description="Number of currently active dynamic leases")
    pool_size: int = Field(default=0, description="Total number of assignable addresses in the pool")


class DhcpLeaseDTO(BaseModel):
    """Active dynamic DHCP lease allocated to a client device."""
    ip: str = Field(..., description="Leased IPv4 address")
    mac: str = Field(..., description="Client Hardware MAC address")
    hostname: str = Field(default="", description="Client advertised hostname")
    network_interface: str = Field(..., description="Assigned interface or bridge")
    expires_in_seconds: int = Field(..., description="Seconds until lease expiration")
    vendor: Optional[str] = Field(default=None, description="OUI hardware manufacturer")

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, value: str) -> str:
        """Normalizes and validates MAC address format."""
        cleaned = value.strip().lower()
        if not re.match(r"^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$", cleaned):
            raise ValueError(f"Invalid MAC address format: {value}")
        return cleaned.replace("-", ":")


class DhcpReservationDTO(BaseModel):
    """Static IP reservation binding a specific MAC to a fixed IP."""
    mac: str = Field(..., description="Client Hardware MAC address")
    reserved_ip: str = Field(..., description="Static IPv4 address binding")
    hostname: str = Field(default="", description="Friendly or DNS hostname")
    zone: str = Field(default="lan", description="Security zone (lan, iot, guest)")
    description: Optional[str] = Field(default=None, description="User note or description")

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, value: str) -> str:
        """Normalizes and validates MAC address format."""
        cleaned = value.strip().lower()
        if not re.match(r"^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$", cleaned):
            raise ValueError(f"Invalid MAC address format: {value}")
        return cleaned.replace("-", ":")


class ConvertLeaseRequestDTO(BaseModel):
    """Request payload to convert an active lease to a static reservation."""
    mac: str = Field(..., description="MAC address of the lease to convert")
    hostname: Optional[str] = Field(default=None, description="Optional override hostname")
    description: Optional[str] = Field(default=None, description="Optional description note")
