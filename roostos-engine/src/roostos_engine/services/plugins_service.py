"""Shared Plugins domain service for RoostOS."""

from typing import List, Dict, Any, Optional
from roostos_engine.config import PluginsConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class PluginsService:
    """Application service for managing plugin installations and runtime state."""

    def __init__(self, repo: ConfigRepository, dbus: Optional[RoostClient] = None) -> None:
        self.repo = repo
        self.dbus = dbus

    def get_plugins_config(self) -> PluginsConfig:
        config = self.repo.get_config()
        return config.plugins_config or PluginsConfig(plugins=[])

    def save_plugins_config(self, plugins_config: PluginsConfig) -> None:
        self.repo.save_plugins_config(plugins_config)

    async def get_plugins_status(self) -> List[Dict[str, Any]]:
        if self.dbus:
            try:
                return await self.dbus.get_plugins()
            except Exception:
                pass
        return []
