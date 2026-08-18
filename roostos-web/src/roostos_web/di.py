"""Dependency Injection configuration, WebDIModule, and FastAPI bridge for RoostOS Web."""

import os
from typing import Optional, Dict, Any, TypeVar, Callable
from injector import Module, Binder, singleton, provider, inject, Injector
from fastapi import Depends

from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.di import EngineDIModule, load_providers_settings
from roostos_engine.repository import ConfigRepository
from roostos_engine.cert_manager import CertificateManager
from roostos_sdk.client import RoostClient

from roostos_web.interfaces.auth import AuthProvider, PAMAuthProvider, MockAuthProvider
from roostos_web.services.devices import DeviceService
from roostos_web.services.network import NetworkService
from roostos_web.services.system import SystemService
from roostos_web.services.schedules import SchedulesService
from roostos_web.services.plugins import PluginsService
from roostos_web.services.cluster import ClusterService

T = TypeVar("T")


class WebDIModule(Module):
    """Injector Module configuring roostos-web provider bindings and services."""

    def __init__(
        self,
        providers_settings: Optional[ProvidersSettings] = None,
        dbus_client: Optional[RoostClient] = None
    ):
        self.providers_settings = providers_settings or ProvidersSettings()
        self.dbus_client = dbus_client

    def configure(self, binder: Binder) -> None:
        # 1. Bind AuthProvider implementation based on settings
        auth_impl = self.providers_settings.auth_provider.lower()
        if auth_impl == "mock":
            binder.bind(AuthProvider, to=MockAuthProvider(), scope=singleton)
        else:
            binder.bind(AuthProvider, to=PAMAuthProvider(), scope=singleton)

        # 2. Bind RoostClient
        if self.dbus_client is not None:
            binder.bind(RoostClient, to=self.dbus_client, scope=singleton)
        else:
            session_bus = os.environ.get("ROOSTOS_SESSION_BUS") == "1" or self.providers_settings.system_client == "mock"
            client = RoostClient(session=session_bus)
            binder.bind(RoostClient, to=client, scope=singleton)

        # 3. Bind Domain Services (automatically injected via @inject in constructors)
        binder.bind(DeviceService, scope=singleton)
        binder.bind(NetworkService, scope=singleton)
        binder.bind(SystemService, scope=singleton)
        binder.bind(SchedulesService, scope=singleton)
        binder.bind(PluginsService, scope=singleton)
        binder.bind(ClusterService, scope=singleton)


# Global Application Injector instance
_app_injector: Optional[Injector] = None


def get_injector() -> Injector:
    """Returns the global application Injector container."""
    global _app_injector
    if _app_injector is None:
        config_dir = os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
        providers_settings = load_providers_settings(config_dir)
        _app_injector = create_web_injector(
            config_dir=config_dir,
            providers_settings=providers_settings
        )
    return _app_injector


def set_injector(injector: Injector) -> None:
    """Sets or overrides the global application Injector container (useful for testing)."""
    global _app_injector
    _app_injector = injector


def create_web_injector(
    config_dir: str = "/etc/roostos",
    staged_dir: Optional[str] = None,
    cert_dir: Optional[str] = None,
    providers_settings: Optional[ProvidersSettings] = None,
    dbus_client: Optional[RoostClient] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> Injector:
    """Factory creating a unified Injector with EngineDIModule and WebDIModule."""
    settings = providers_settings or load_providers_settings(config_dir, overrides=overrides)
    engine_module = EngineDIModule(
        config_dir=config_dir,
        staged_dir=staged_dir,
        cert_dir=cert_dir,
        providers_settings=settings
    )
    web_module = WebDIModule(
        providers_settings=settings,
        dbus_client=dbus_client
    )
    return Injector([engine_module, web_module])


def Injected(interface: type[T]) -> Any:
    """FastAPI Depends helper that resolves an interface via the Injector container."""
    def _resolve_injected(injector: Injector = Depends(get_injector)):
        return injector.get(interface)
    return Depends(_resolve_injected)
