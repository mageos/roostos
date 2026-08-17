import os
from typing import Optional
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


def get_repository() -> ConfigRepository:
    from roostos_web.di import get_injector
    return get_injector().get(ConfigRepository)


def set_repository(repo: ConfigRepository):
    from roostos_web.di import get_injector
    injector = get_injector()
    injector.binder.bind(ConfigRepository, to=repo)


async def get_dbus_client() -> RoostClient:
    from roostos_web.di import get_injector
    client = get_injector().get(RoostClient)
    if getattr(client, "_interface", None) is None:
        try:
            await client.connect()
        except Exception:
            pass
    return client


def set_dbus_client(client: RoostClient):
    from roostos_web.di import get_injector
    injector = get_injector()
    injector.binder.bind(RoostClient, to=client)

