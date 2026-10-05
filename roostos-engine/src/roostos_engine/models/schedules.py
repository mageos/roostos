from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

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
    schedules: List[ScheduleConfig] = Field(default_factory=list)
    firewall: Optional[ScheduleSettings] = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_schedules(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "firewall" in data and isinstance(data["firewall"], dict):
                fw_sch = data["firewall"].get("schedules", [])
                if "schedules" not in data or not data["schedules"]:
                    data["schedules"] = fw_sch
            elif "schedules" in data and "firewall" not in data:
                data["firewall"] = {"schedules": data["schedules"]}
        return data

    @model_validator(mode="after")
    def sync_firewall(self) -> "SchedulesConfig":
        if self.firewall is None:
            self.firewall = ScheduleSettings(schedules=self.schedules)
        elif not self.schedules and self.firewall.schedules:
            self.schedules = self.firewall.schedules
        return self

