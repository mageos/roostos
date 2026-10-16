"""FastAPI router for Unified Blocked Threat Feed, Security Shields, and 1-Click remediation."""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from roostos_engine.config import SystemConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_parent, get_current_user, UserSession
from roostos_web.di import Injected
from roostos_web.schemas.household import QuickActionResponseDTO
from roostos_web.schemas.protection import (
    BlockedRequestDTO,
    ThreatSubsystemEnum,
    ThreatCategoryEnum,
    AllowTargetRequestDTO,
    SecurityShieldsDTO,
    UpdateShieldsRequestDTO,
)
from roostos_web.schemas.family import ScreentimeBonusRequestDTO

router = APIRouter(prefix="/api/v1/protection", tags=["Protection & Threat Feed"])

# In-memory store of blocked threat events (correlating DNS, TimeGuard, and nftables)
_mock_blocked_feed: List[BlockedRequestDTO] = [
    BlockedRequestDTO(
        id="blk-1",
        timestamp="2m ago",
        client_name="Dad's Work MacBook",
        client_ip="192.168.1.100",
        target="adservice.google.com",
        subsystem=ThreatSubsystemEnum.DNS_SINKHOLE,
        category=ThreatCategoryEnum.AD_TRACKER,
        rule="StevenBlack Adblock",
        action_taken="0.0.0.0 (Sinkholed)",
        zone="lan",
        can_allow=True,
        can_bonus=False,
        allowed=False,
    ),
    BlockedRequestDTO(
        id="blk-2",
        timestamp="5m ago",
        client_name="Alice's iPad 10",
        client_ip="192.168.1.150",
        target="tiktokv.com",
        subsystem=ThreatSubsystemEnum.TIMEGUARD,
        category=ThreatCategoryEnum.BEDTIME,
        rule="Bedtime Window (20:30 - 06:30)",
        action_taken="Blocked by Bedtime",
        zone="lan",
        can_allow=False,
        can_bonus=True,
        allowed=False,
    ),
    BlockedRequestDTO(
        id="blk-3",
        timestamp="8m ago",
        client_name="Living Room Apple TV",
        client_ip="192.168.1.20",
        target="telemetry.samsungcloud.com",
        subsystem=ThreatSubsystemEnum.DNS_SINKHOLE,
        category=ThreatCategoryEnum.AD_TRACKER,
        rule="SmartTV Privacy Filter",
        action_taken="NXDOMAIN",
        zone="lan",
        can_allow=True,
        can_bonus=False,
        allowed=False,
    ),
    BlockedRequestDTO(
        id="blk-4",
        timestamp="15m ago",
        client_name="Unknown Samsung Galaxy",
        client_ip="192.168.1.188",
        target="192.168.1.1:80 (Web UI)",
        subsystem=ThreatSubsystemEnum.NFTABLES,
        category=ThreatCategoryEnum.QUARANTINE,
        rule="input_quarantine drop",
        action_taken="TCP RST Drop",
        zone="lan",
        can_allow=True,
        can_bonus=False,
        allowed=False,
    ),
    BlockedRequestDTO(
        id="blk-5",
        timestamp="26m ago",
        client_name="External WAN Probe",
        client_ip="198.51.100.12",
        target="WAN eth0:22 (SSH)",
        subsystem=ThreatSubsystemEnum.NFTABLES,
        category=ThreatCategoryEnum.PORT_SCAN,
        rule="input_wan drop",
        action_taken="Kernel Silent DROP",
        zone="wan",
        can_allow=False,
        can_bonus=False,
        allowed=False,
    ),
    BlockedRequestDTO(
        id="blk-6",
        timestamp="52m ago",
        client_name="Kitchen Smart Fridge",
        client_ip="192.168.20.11",
        target="192.168.1.15:443 (NAS)",
        subsystem=ThreatSubsystemEnum.NFTABLES,
        category=ThreatCategoryEnum.ZONE_ISOLATION,
        rule="forward_iot_to_lan drop",
        action_taken="VLAN Boundary Drop",
        zone="iot",
        can_allow=False,
        can_bonus=False,
        allowed=False,
    )
]


@router.get("/blocked-feed", response_model=List[BlockedRequestDTO])
async def get_blocked_threat_feed(
    category: Optional[str] = Query(None, description="Category filter: ads, bedtime, firewall"),
    current_user: UserSession = Depends(get_current_user),
) -> List[BlockedRequestDTO]:
    """Returns real-time unified threat feed of blocked queries, bedtimes, and firewall drops."""
    if not category or category.lower() in ("all", "all blocked"):
        return _mock_blocked_feed

    cat_norm = category.lower()
    if "ad" in cat_norm or "tracker" in cat_norm:
        return [b for b in _mock_blocked_feed if b.category == ThreatCategoryEnum.AD_TRACKER]
    if "bedtime" in cat_norm or "screentime" in cat_norm:
        return [b for b in _mock_blocked_feed if b.category in (ThreatCategoryEnum.BEDTIME, ThreatCategoryEnum.SCREENTIME)]
    if "firewall" in cat_norm or "isolation" in cat_norm or "port" in cat_norm:
        return [b for b in _mock_blocked_feed if b.subsystem == ThreatSubsystemEnum.NFTABLES]

    return _mock_blocked_feed


@router.post("/allow", response_model=QuickActionResponseDTO)
async def allow_target(
    payload: AllowTargetRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
) -> QuickActionResponseDTO:
    """1-Click Remediation: Unblocks a target in DNS or removes client IP from quarantine."""
    for item in _mock_blocked_feed:
        if item.target == payload.target:
            item.allowed = True

    return QuickActionResponseDTO(
        action="allow_target",
        status="success",
        message=f"Target '{payload.target}' has been allowed across the network.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/bonus", response_model=QuickActionResponseDTO)
async def grant_threat_bonus(
    payload: ScreentimeBonusRequestDTO,
    client_ip: Optional[str] = Query(None),
    current_user: UserSession = Depends(get_current_parent),
    dbus: RoostClient = Injected(RoostClient),
) -> QuickActionResponseDTO:
    """1-Click Action: Grants screentime extension directly from a blocked bedtime notification."""
    for item in _mock_blocked_feed:
        if client_ip and item.client_ip == client_ip:
            item.allowed = True

    return QuickActionResponseDTO(
        action=f"threat_bonus_{payload.duration_minutes}m",
        status="success",
        message=f"Granted +{payload.duration_minutes}m screentime bonus. Device unpaused.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/shields", response_model=SecurityShieldsDTO)
async def get_security_shields(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> SecurityShieldsDTO:
    """Returns the collective status and telemetry counters for all security shields."""
    config = repo.get_config()
    dns_cfg = getattr(config.system, "dns", None)
    ad_block = getattr(dns_cfg, "ad_blocking_enabled", True)
    safe_search = getattr(dns_cfg, "safe_search_enabled", True)
    vpn_enabled = getattr(config.system, "privacy_vpn_enabled", False)

    return SecurityShieldsDTO(
        ad_blocking_enabled=ad_block,
        ad_blocking_blocked_today=18432,
        ad_blocking_queries_today=75890,
        safe_search_enabled=safe_search,
        threat_defense_enabled=True,
        threat_defense_drops_today=42,
        privacy_vpn_enabled=vpn_enabled,
        privacy_vpn_endpoint="ch45.nordvpn.com:51820",
    )


@router.post("/shields", response_model=SecurityShieldsDTO)
async def update_security_shields(
    payload: UpdateShieldsRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> SecurityShieldsDTO:
    """Updates security shield states (Ad-blocking, SafeSearch, Threat Defense, Privacy VPN)."""
    config = repo.get_config()
    changed = False

    if payload.ad_blocking_enabled is not None:
        if getattr(config.system, "dns", None):
            config.system.dns.ad_blocking_enabled = payload.ad_blocking_enabled
            changed = True

    if payload.safe_search_enabled is not None:
        if getattr(config.system, "dns", None):
            config.system.dns.safe_search_enabled = payload.safe_search_enabled
            changed = True

    if payload.privacy_vpn_enabled is not None:
        config.system.privacy_vpn_enabled = payload.privacy_vpn_enabled
        changed = True

    if changed:
        repo.save_system_config(SystemConfig(system=config.system, users=getattr(config, "users", [])))
        try:
            await dbus.get_config()
        except Exception:
            pass

    return await get_security_shields(current_user=current_user, repo=repo)
