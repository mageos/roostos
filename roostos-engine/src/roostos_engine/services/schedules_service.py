"""Shared Schedules and Time Allowance domain service for RoostOS."""

from typing import Optional
from roostos_engine.config import SchedulesConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class SchedulesService:
    """Application service for managing parental schedules and bypass time extensions."""

    def __init__(self, repo: ConfigRepository, dbus: Optional[RoostClient] = None) -> None:
        self.repo = repo
        self.dbus = dbus

    def get_schedules_config(self) -> SchedulesConfig:
        config = self.repo.get_config()
        return SchedulesConfig(schedules=config.schedules)

    def save_schedules_config(self, schedules_config: SchedulesConfig) -> None:
        self.repo.save_schedules_config(schedules_config)

    async def grant_time_extension(self, mac: str, duration_seconds: int) -> bool:
        """Grants a temporary schedule bypass extension to a device over D-Bus."""
        if not self.dbus:
            return False
        try:
            return await self.dbus.grant_time_extension(mac, duration_seconds)
        except Exception:
            return False

    async def remove_time_extension(self, mac: str) -> bool:
        """Revokes an active schedule bypass extension from a device over D-Bus."""
        if not self.dbus:
            return False
        try:
            return await self.dbus.remove_time_extension(mac)
        except Exception:
            return False
