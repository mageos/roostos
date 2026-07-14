from fastapi import Depends
from roostos_engine.config import SchedulesConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.services.base import get_repository, get_dbus_client

class SchedulesService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository), dbus: RoostClient = Depends(get_dbus_client)):
        self.repo = repo
        self.dbus = dbus

    def get_schedules_config(self) -> SchedulesConfig:
        config = self.repo.get_config()
        return config.firewall

    async def save_schedules_config(self, schedules_config: SchedulesConfig):
        self.repo.save_schedules_config(schedules_config)
        await self.dbus.get_config()
