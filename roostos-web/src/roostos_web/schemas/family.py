"""Pydantic schemas and DTOs for Family members, Screentime limits, and Bedtimes."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FamilyRoleEnum(str, Enum):
    """Role classification within the household."""
    ADMIN = "admin"
    PARENT = "parent"
    KID = "kid"
    GUEST = "guest"


class BedtimeScheduleDTO(BaseModel):
    """Daily bedtime schedule and enforcement window."""
    start_time: str = Field(default="20:30", description="Bedtime cutoff start time (HH:MM)")
    end_time: str = Field(default="06:30", description="Bedtime cutoff end time (HH:MM)")
    enabled: bool = Field(default=True, description="Whether bedtime schedule is enforced")
    active_now: bool = Field(default=False, description="Whether user is currently in bedtime window")


class FamilyPersonDTO(BaseModel):
    """Rich family member profile model for Household Hub."""
    id: str = Field(..., description="Unique person identifier (e.g. alice)")
    name: str = Field(..., min_length=1, max_length=64, description="Display name")
    role: FamilyRoleEnum = Field(default=FamilyRoleEnum.KID, description="Household role")
    avatar: str = Field(default="👤", description="Avatar emoji or profile icon")
    color: str = Field(default="#3b82f6", description="Theme color hex code")
    screentime_limit_minutes: int = Field(default=0, ge=0, description="Daily quota in minutes (0 = unlimited)")
    screentime_used_minutes: int = Field(default=0, ge=0, description="Minutes used today")
    bonus_minutes_today: int = Field(default=0, ge=0, description="Bonus extension minutes granted today")
    bedtime: BedtimeScheduleDTO = Field(default_factory=BedtimeScheduleDTO, description="Bedtime schedule")
    filter_level: str = Field(default="Standard", description="DNS/content filter profile name")
    device_count: int = Field(default=0, description="Count of devices assigned to this person")
    devices: List[str] = Field(default_factory=list, description="MAC addresses of owned devices")


class ScreentimeBonusRequestDTO(BaseModel):
    """Request payload to grant a temporary screentime bonus."""
    duration_minutes: int = Field(..., ge=5, le=480, description="Bonus extension duration in minutes")
    reason: Optional[str] = Field(default="Parental Bonus", description="Optional note or reason")


class DinnerTimeRequestDTO(BaseModel):
    """Request payload for the Dinner Time pause action."""
    duration_minutes: int = Field(default=60, ge=15, le=180, description="Pause duration in minutes")


class PauseKidsRequestDTO(BaseModel):
    """Request payload to pause or resume all kid profiles."""
    paused: bool = Field(..., description="True to pause all kids, False to resume")
