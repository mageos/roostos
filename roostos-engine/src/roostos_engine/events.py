"""Repository mutation and lifecycle event definitions for RoostOS."""

import time
import asyncio
from typing import Any, Callable, List, Optional
from pydantic import BaseModel, Field


class ConfigChangeEvent(BaseModel):
    """Event emitted whenever a configuration section is mutated in the repository."""
    section: str = Field(description="Configuration section mutated (e.g., 'devices', 'network', 'firewall')")
    action: str = Field(default="save", description="Action performed: 'save', 'stage', 'commit', 'delete'")
    data: Any = Field(default=None, description="The payload or config model associated with the change")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of the mutation")


ConfigChangeListener = Callable[[ConfigChangeEvent], Any]


class DBusReloadListener:
    """Listener that triggers daemon config reload over D-Bus upon repository save."""

    def __init__(self, dbus_client: Any) -> None:
        self.dbus_client = dbus_client

    def __call__(self, event: ConfigChangeEvent) -> None:
        if self.dbus_client is None:
            return

        # Skip intermediate staging events if not committed yet
        if event.action == "stage":
            return

        async def _trigger_reload() -> None:
            try:
                if hasattr(self.dbus_client, "reload_config"):
                    await self.dbus_client.reload_config()
                elif hasattr(self.dbus_client, "get_config"):
                    await self.dbus_client.get_config()
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_trigger_reload())
        except RuntimeError:
            try:
                asyncio.run(_trigger_reload())
            except Exception:
                pass
