"""Dependency Injection configuration, Web Container setup, and FastAPI bridge for RoostOS Web."""

import os
from typing import Optional, Dict, Any, TypeVar
from fastapi import Depends

import punq
from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.di import (
    RoostContainer,
    create_engine_container,
    load_providers_settings,
)
from roostos_engine.repository import ConfigRepository
from roostos_engine.events import DBusReloadListener
from roostos_engine.services import (
    DeviceService,
    FirewallService,
    NetworkService,
    SchedulesService,
    PluginsService,
    SystemService,
)
from roostos_sdk.client import RoostClient

from roostos_web.interfaces.auth import (
    AuthProvider, PAMAuthProvider, MockAuthProvider, MultiAuthorityAuthProvider
)
from roostos_web.services.cluster import ClusterService

T = TypeVar("T")


def configure_web_container(
    container: RoostContainer,
    providers_settings: ProvidersSettings,
    dbus_client: Optional[RoostClient] = None,
) -> RoostContainer:
    """Configures web-specific auth, D-Bus client, and event wiring onto a RoostContainer."""
    # 1. Bind AuthProvider implementation
    auth_impl = providers_settings.auth_provider.lower()
    if auth_impl == "mock":
        container.register(AuthProvider, instance=MockAuthProvider())
    elif auth_impl == "ldap":
        from roostos_web.interfaces.auth import LDAPAuthProvider
        container.register(AuthProvider, instance=LDAPAuthProvider())
    elif auth_impl in ("multi_authority", "centralized"):
        from roostos_web.interfaces.auth import LDAPAuthProvider
        container.register(
            AuthProvider,
            instance=MultiAuthorityAuthProvider(
                local_provider=PAMAuthProvider(),
                central_provider=LDAPAuthProvider()
            )
        )
    else:
        container.register(AuthProvider, instance=PAMAuthProvider())

    # 2. Bind RoostClient
    if dbus_client is not None:
        client_instance = dbus_client
    elif providers_settings.system_client == "mock":
        from roostos_sdk.mock_client import MockRoostClient
        client_instance = MockRoostClient()
    else:
        session_bus = os.environ.get("ROOSTOS_SESSION_BUS") == "1"
        client_instance = RoostClient(session=session_bus)

    container.register(RoostClient, instance=client_instance)

    # 3. Wire Repository Event Hooks for automatic D-Bus reload & SSE broadcast
    try:
        repo = container.resolve(ConfigRepository)
        repo.add_listener(DBusReloadListener(client_instance))
    except Exception:
        pass

    # 4. Register Web-specific services
    container.register(ClusterService, scope=punq.Scope.singleton)

    return container


class WebDIModule:
    """Backwards-compatibility class for WebDIModule."""
    def __init__(
        self,
        providers_settings: Optional[ProvidersSettings] = None,
        dbus_client: Optional[RoostClient] = None
    ) -> None:
        self.providers_settings = providers_settings
        self.dbus_client = dbus_client


_app_injector: Optional[RoostContainer] = None


def get_injector() -> RoostContainer:
    """Returns the global application RoostContainer."""
    global _app_injector
    if _app_injector is None:
        if os.environ.get("ROOSTOS_MOCK") == "1" or os.environ.get("ROOSTOS_DEV_MOCK") == "1":
            _app_injector = create_mock_web_injector()
        else:
            config_dir = os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
            providers_settings = load_providers_settings(config_dir)
            _app_injector = create_web_injector(
                config_dir=config_dir,
                providers_settings=providers_settings
            )
    return _app_injector


def set_injector(injector: Optional[RoostContainer]) -> None:
    """Sets or overrides the global application container (useful for testing)."""
    global _app_injector
    _app_injector = injector


def create_web_injector(
    config_dir: str = "/etc/roostos",
    staged_dir: Optional[str] = None,
    cert_dir: Optional[str] = None,
    providers_settings: Optional[ProvidersSettings] = None,
    dbus_client: Optional[RoostClient] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> RoostContainer:
    """Factory creating a unified RoostContainer with engine and web dependencies."""
    settings = providers_settings or load_providers_settings(config_dir, overrides=overrides)
    container = create_engine_container(
        config_dir=config_dir,
        staged_dir=staged_dir,
        cert_dir=cert_dir,
        providers_settings=settings
    )
    return configure_web_container(
        container=container,
        providers_settings=settings,
        dbus_client=dbus_client
    )


def create_mock_web_injector(
    config_dir: str = "/tmp/roostos-mock",
    dbus_client: Optional[RoostClient] = None,
    providers_settings: Optional[ProvidersSettings] = None,
) -> RoostContainer:
    """Convenience factory creating a fully mocked, in-memory RoostContainer."""
    settings = providers_settings or ProvidersSettings(
        description="Default Mock Container",
        auth_provider="mock",
        config_repository="memory",
        system_client="mock",
        cert_manager="mock",
        firewall_manager="mock",
        data_seeder="concept1",
        auto_auth=True,
    )
    from roostos_sdk.mock_client import MockRoostClient
    client = dbus_client or MockRoostClient()
    return create_web_injector(
        config_dir=config_dir,
        cert_dir=f"{config_dir}/certs",
        providers_settings=settings,
        dbus_client=client
    )


def Injected(interface: type[T]) -> Any:
    """FastAPI Depends helper that resolves an interface via the RoostContainer."""
    def _resolve_injected(container: RoostContainer = Depends(get_injector)) -> T:
        return container.resolve(interface)
    return Depends(_resolve_injected)
