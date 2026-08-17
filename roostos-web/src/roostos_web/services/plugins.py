from typing import List, Dict, Any
from injector import inject

from roostos_engine.config import PluginsConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class PluginsService:
    @inject
    def __init__(self, repo: ConfigRepository, dbus: RoostClient):
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
