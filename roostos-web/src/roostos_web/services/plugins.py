from typing import List, Dict, Any
from fastapi import Depends

from roostos_engine.config import PluginsConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.services.base import get_repository, get_dbus_client

class PluginsService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository), dbus: RoostClient = Depends(get_dbus_client)):
        self.repo = repo
        self.dbus = dbus

    def get_plugins_config(self) -> PluginsConfig:
        config = self.repo.get_config()
        return config.plugins_config or PluginsConfig(plugins=[])

    async def save_plugins_config(self, plugins_config: PluginsConfig):
        self.repo.save_plugins_config(plugins_config)
        await self.dbus.get_config()

    async def get_plugins_status(self) -> List[Dict[str, Any]]:
        try:
            return await self.dbus.get_plugins()
        except Exception:
            return []
