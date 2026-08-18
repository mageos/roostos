from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class ScheduleTarget(BaseModel):
    tag: Optional[str] = None
    person: Optional[str] = None
    location: Optional[str] = None
    mac: Optional[str] = None
    zone: Optional[str] = None

class ScheduleConfig(BaseModel):
    name: str
    targets: List[ScheduleTarget] = Field(default_factory=list)
    days: List[str] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    daily_limit: Optional[int] = None
    action: str = "block_internet"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("block_internet", "block_all"):
            raise ValueError(f"Schedule action '{v}' must be 'block_internet' or 'block_all'")
        return v

class ScheduleSettings(BaseModel):
    schedules: List[ScheduleConfig] = Field(default_factory=list)

class SchedulesConfig(BaseModel):
    firewall: Optional[ScheduleSettings] = Field(default_factory=ScheduleSettings)
