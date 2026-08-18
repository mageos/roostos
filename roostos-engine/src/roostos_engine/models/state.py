from typing import Optional
from pydantic import BaseModel, Field

class ActiveLease(BaseModel):
    mac: str
    ip: str
    hostname: Optional[str] = None
    quarantined: bool = True
    last_seen: Optional[str] = None

class PendingUPnPRequest(BaseModel):
    id: Optional[int] = None
    mac: str
    internal_ip: str
    external_port: int
    internal_port: int
    protocol: str = "tcp"
    description: Optional[str] = None
    requested_at: Optional[str] = None

class BypassGrant(BaseModel):
    mac: str
    expiry: str
    duration_seconds: int

class TimeGuardHeartbeat(BaseModel):
    username: str
    hostname: str
    active_seconds: int = 30
    remaining_seconds: int = 3600

class TimeGuardUserLimits(BaseModel):
    username: str
    remaining_seconds: int = 3600
    daily_limit_seconds: int = 3600
    locked: bool = False

class ClusterNode(BaseModel):
    node_id: str
    hostname: str
    role: str = "compute_worker"  # "primary_router", "secondary_router", "compute_worker"
    ip_address: str
    status: str = "online"        # "online", "offline", "degraded"
    last_seen: Optional[str] = None
