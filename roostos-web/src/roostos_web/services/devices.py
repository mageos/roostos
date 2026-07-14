from typing import List, Dict, Any
from fastapi import Depends

from roostos_engine.config import DevicesConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.services.base import get_repository, get_dbus_client

class DeviceService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository), dbus: RoostClient = Depends(get_dbus_client)):
        self.repo = repo
        self.dbus = dbus

    def get_devices_config(self) -> DevicesConfig:
        config = self.repo.get_config()
        return DevicesConfig(
            people=config.people,
            buildings=config.buildings,
            rooms=config.rooms,
            devices=config.devices
        )

    def save_devices_config(self, devices_config: DevicesConfig):
        self.repo.save_devices_config(devices_config)

    async def get_active_leases(self) -> List[Dict[str, Any]]:
        try:
            return await self.dbus.get_active_leases()
        except Exception:
            return []

    async def trigger_config_reload(self):
        await self.dbus.get_config()
