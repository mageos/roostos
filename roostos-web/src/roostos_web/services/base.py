import os
from typing import Optional
from roostos_engine.repository import ConfigRepository, YAMLConfigRepository
from roostos_sdk.client import RoostClient

# Global Repository & D-Bus Client Dependency Injection Hooks
_config_repo: Optional[ConfigRepository] = None
_roost_client: Optional[RoostClient] = None

def get_repository() -> ConfigRepository:
    global _config_repo
    if _config_repo is None:
        config_dir = os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
        _config_repo = YAMLConfigRepository(config_dir)
    return _config_repo

def set_repository(repo: ConfigRepository):
    global _config_repo
    _config_repo = repo

async def get_dbus_client() -> RoostClient:
    global _roost_client
    if _roost_client is None or getattr(_roost_client, "_interface", None) is None:
        session_bus = os.environ.get("ROOSTOS_SESSION_BUS") == "1"
        client = RoostClient(session=session_bus)
        try:
            await client.connect()
            _roost_client = client
        except Exception as e:
            _roost_client = None
            raise e
    return _roost_client

def set_dbus_client(client: RoostClient):
    global _roost_client
    _roost_client = client
