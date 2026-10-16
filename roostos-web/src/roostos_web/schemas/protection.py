"""Pydantic schemas and DTOs for Threat feed, security shields, and allowlist actions."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ThreatSubsystemEnum(str, Enum):
    """Subsystem responsible for dropping or blocking traffic."""
    DNS_SINKHOLE = "DNS Sinkhole"
    TIMEGUARD = "TimeGuard"
    NFTABLES = "nftables"


class ThreatCategoryEnum(str, Enum):
    """Classification category of blocked event."""
    AD_TRACKER = "Ad & Tracker"
    BEDTIME = "Bedtime Schedule"
    SCREENTIME = "Screentime Limit"
    QUARANTINE = "Device Quarantine"
    PORT_SCAN = "Port Scan"
    ZONE_ISOLATION = "Zone Isolation Violation"


class BlockedRequestDTO(BaseModel):
    """Unified record representing a blocked request across any protection engine."""
    id: str = Field(..., description="Unique event identifier")
    timestamp: str = Field(..., description="ISO 8601 or relative timestamp")
    client_name: str = Field(..., description="Name of client device making request")
    client_ip: str = Field(..., description="Source IPv4 address")
    target: str = Field(..., description="Blocked domain, IP, or destination port")
    subsystem: ThreatSubsystemEnum = Field(..., description="Subsystem that enforced the block")
    category: ThreatCategoryEnum = Field(..., description="Categorization of block")
    rule: str = Field(..., description="Rule or blocklist triggering the drop")
    action_taken: str = Field(..., description="Action summary (e.g. DNS NXDOMAIN, Drop)")
    zone: str = Field(default="lan", description="Security zone origin")
    can_allow: bool = Field(default=True, description="Whether 1-click allow/whitelist is available")
    can_bonus: bool = Field(default=False, description="Whether +30m screentime bonus applies")
    allowed: bool = Field(default=False, description="Whether event has been remediated/allowed")


class AllowTargetRequestDTO(BaseModel):
    """Request payload to unblock/allow a target from the threat feed."""
    target: str = Field(..., description="Domain or IP address to allow")
    subsystem: ThreatSubsystemEnum = Field(default=ThreatSubsystemEnum.DNS_SINKHOLE)
    client_ip: Optional[str] = Field(default=None, description="Optional client IP to restrict rule")


class SecurityShieldsDTO(BaseModel):
    """Aggregate status of all security shields."""
    ad_blocking_enabled: bool = Field(default=True, description="Technitium / AdBlock filter state")
    ad_blocking_blocked_today: int = Field(default=0, description="Total ads/trackers sinkholed today")
    ad_blocking_queries_today: int = Field(default=0, description="Total DNS queries processed today")
    safe_search_enabled: bool = Field(default=True, description="SafeSearch VIP enforcement state")
    threat_defense_enabled: bool = Field(default=True, description="Firewall port scan and probe drop state")
    threat_defense_drops_today: int = Field(default=0, description="Total perimeter drops today")
    privacy_vpn_enabled: bool = Field(default=False, description="Outbound privacy VPN killswitch state")
    privacy_vpn_endpoint: Optional[str] = Field(default=None, description="Active VPN endpoint gateway")


class UpdateShieldsRequestDTO(BaseModel):
    """Request payload to toggle individual security shields."""
    ad_blocking_enabled: Optional[bool] = None
    safe_search_enabled: Optional[bool] = None
    threat_defense_enabled: Optional[bool] = None
    privacy_vpn_enabled: Optional[bool] = None
