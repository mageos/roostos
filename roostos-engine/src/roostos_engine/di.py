"""RoostOS Engine Dependency Injection Container and Provider Loader (using punq)."""

import os
import inspect
import yaml
from typing import Optional, Dict, Any
import punq

from roostos_engine.models.providers import ProvidersSettings, ProvidersConfigFile
from roostos_engine.repository import (
    ConfigRepository,
    StagingConfigRepository,
    YAMLConfigRepository,
    InMemoryConfigRepository,
)
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.interfaces import (
    CertificateProvider,
    FirewallProvider,
    MockFirewallProvider,
    DHCPProvider,
    MockDHCPProvider,
    DNSResolverProvider,
    MockDNSResolverProvider,
    NetworkProvider,
    MockNetworkProvider,
)
from roostos_engine.services.device_service import DeviceService
from roostos_engine.services.firewall_service import FirewallService
from roostos_engine.services.network_service import NetworkService
from roostos_engine.services.schedules_service import SchedulesService
from roostos_engine.services.plugins_service import PluginsService
from roostos_engine.services.system_service import SystemService
from roostos_sdk.client import RoostClient
from roostos_sdk.mock_client import MockRoostClient


class RoostContainer(punq.Container):
    """Punq-backed dependency injection container with backwards-compatible helper methods."""

    def resolve(self, key: Any, **kwargs: Any) -> Any:
        try:
            return super().resolve(key, **kwargs)
        except punq.MissingDependencyError:
            if inspect.isclass(key):
                return self.instantiate(key)
            raise

    def get(self, key: Any) -> Any:
        """Compatibility method for resolving dependencies like injector.get(service)."""
        return self.resolve(key)

    @property
    def binder(self) -> Any:
        """Compatibility property mimicking injector.binder for test overrides."""
        class _Binder:
            def __init__(b_self, container: "RoostContainer") -> None:
                b_self._c = container

            def bind(b_self, iface: Any, to: Any = None, scope: Any = None) -> None:
                if to is not None:
                    if inspect.isclass(to):
                        b_self._c.register(iface, to, scope=punq.Scope.singleton)
                    else:
                        b_self._c.register(iface, instance=to)
                else:
                    b_self._c.register(iface, scope=punq.Scope.singleton)
        return _Binder(self)


def load_providers_settings(
    config_dir: str = "/etc/roostos",
    providers_config_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> ProvidersSettings:
    """Loads ProvidersSettings from container.yaml/providers.yaml, applying environment and CLI overrides."""
    settings_dict: Dict[str, Any] = {}
    target_file = None

    if providers_config_path in ("mock", "mock_container"):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidate = os.path.join(repo_root, "config", "mock_container.yaml")
        if os.path.exists(candidate):
            target_file = candidate
        else:
            settings_dict.update({
                "auth_provider": "mock",
                "config_repository": "memory",
                "system_client": "mock",
                "cert_manager": "mock",
                "firewall_manager": "mock",
                "dhcp_manager": "mock",
                "dns_manager": "mock",
                "network_manager": "mock",
                "data_seeder": "concept1",
                "auto_auth": True,
            })
    elif providers_config_path in ("prod", "production"):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidate = os.path.join(repo_root, "config", "container.yaml")
        if os.path.exists(candidate):
            target_file = candidate
    else:
        target_file = providers_config_path or os.environ.get(
            "ROOSTOS_CONTAINER_CONFIG",
            os.environ.get(
                "ROOSTOS_PROVIDERS_CONFIG",
                os.path.join(config_dir, "container.yaml")
                if os.path.exists(os.path.join(config_dir, "container.yaml"))
                else os.path.join(config_dir, "providers.yaml")
            )
        )

    if target_file and os.path.exists(target_file):
        try:
            with open(target_file, "r") as f:
                content = yaml.safe_load(f) or {}
                if "container" in content and isinstance(content["container"], dict):
                    settings_dict.update(content["container"])
                elif "providers" in content and isinstance(content["providers"], dict):
                    settings_dict.update(content["providers"])
                elif isinstance(content, dict):
                    settings_dict.update(content)
        except Exception as e:
            print(f"Warning: Failed to parse container config file '{target_file}': {e}")

    env_mappings = {
        "ROOSTOS_AUTH_PROVIDER": "auth_provider",
        "ROOSTOS_CONFIG_REPO": "config_repository",
        "ROOSTOS_SYSTEM_CLIENT": "system_client",
        "ROOSTOS_CERT_MANAGER": "cert_manager",
        "ROOSTOS_FIREWALL_MANAGER": "firewall_manager",
        "ROOSTOS_DHCP_MANAGER": "dhcp_manager",
        "ROOSTOS_DNS_MANAGER": "dns_manager",
        "ROOSTOS_NETWORK_MANAGER": "network_manager",
        "ROOSTOS_DATA_SEEDER": "data_seeder",
    }
    for env_key, setting_key in env_mappings.items():
        val = os.environ.get(env_key)
        if val:
            settings_dict[setting_key] = val

    if overrides:
        for k, v in overrides.items():
            if v is not None:
                settings_dict[k] = v

    if os.environ.get("ROOSTOS_MOCK_AUTH") == "1" and "auth_provider" not in settings_dict:
        settings_dict["auth_provider"] = "mock"

    return ProvidersSettings(**settings_dict)


def configure_engine_container(
    container: RoostContainer,
    config_dir: str = "/etc/roostos",
    staged_dir: Optional[str] = None,
    cert_dir: Optional[str] = None,
    providers_settings: Optional[ProvidersSettings] = None
) -> RoostContainer:
    """Configures core roostos-engine provider and service bindings in a RoostContainer."""
    settings = providers_settings or load_providers_settings(config_dir)
    actual_staged_dir = staged_dir or os.environ.get(
        "ROOSTOS_STAGED_CONFIG_DIR",
        os.path.join(os.path.dirname(config_dir.rstrip("/")), "staged_config")
        if config_dir != "/etc/roostos"
        else "/var/lib/roostos/staged_config"
    )
    actual_cert_dir = cert_dir or os.environ.get(
        "ROOSTOS_CERT_DIR",
        os.path.join(config_dir, "certs")
    )

    container.register(ProvidersSettings, instance=settings)

    repo_impl = settings.config_repository.lower()
    if repo_impl in ("staging", "staged"):
        repo_instance = StagingConfigRepository(config_dir, actual_staged_dir)
    elif repo_impl in ("yaml", "file", "direct"):
        repo_instance = YAMLConfigRepository(config_dir)
    elif repo_impl in ("memory", "inmemory", "mock"):
        seeder = getattr(settings, "data_seeder", "concept1").lower()
        if seeder in ("empty", "none", "clean"):
            repo_instance = InMemoryConfigRepository()
        elif os.path.exists(seeder):
            from roostos_engine.config import load_config_directory
            repo_instance = InMemoryConfigRepository(initial_config=load_config_directory(seeder))
        else:
            from roostos_engine.mock_data import create_mock_config
            repo_instance = InMemoryConfigRepository(initial_config=create_mock_config())
    else:
        repo_instance = StagingConfigRepository(config_dir, actual_staged_dir)

    container.register(ConfigRepository, instance=repo_instance)

    cert_impl = settings.cert_manager.lower()
    if cert_impl in ("mock", "memory"):
        from roostos_engine.mock_cert_manager import MockCertificateManager
        cert_mgr = MockCertificateManager()
    else:
        cert_mgr = CertificateManager(cert_dir=actual_cert_dir)
    container.register(CertificateManager, instance=cert_mgr)
    container.register(CertificateProvider, instance=cert_mgr)

    try:
        initial_cfg = repo_instance.get_config()
    except Exception:
        initial_cfg = None

    fw_impl = settings.firewall_manager.lower()
    if fw_impl in ("mock", "memory") or initial_cfg is None:
        fw_mgr = MockFirewallProvider(initial_cfg)
    else:
        from roostos_engine.firewall_manager import FirewallManager
        fw_mgr = FirewallManager(initial_cfg)
    container.register(FirewallProvider, instance=fw_mgr)

    dhcp_impl = settings.dhcp_manager.lower()
    if dhcp_impl in ("mock", "memory") or initial_cfg is None:
        dhcp_mgr = MockDHCPProvider(initial_cfg)
    else:
        from roostos_engine.dhcp_manager import DHCPManager
        dhcp_mgr = DHCPManager(initial_cfg)
    container.register(DHCPProvider, instance=dhcp_mgr)

    dns_mgr = MockDNSResolverProvider(initial_cfg)
    container.register(DNSResolverProvider, instance=dns_mgr)

    net_mgr = MockNetworkProvider(initial_cfg)
    container.register(NetworkProvider, instance=net_mgr)

    # Bind RoostClient
    if settings.system_client == "mock":
        default_client = MockRoostClient()
    else:
        session_bus = os.environ.get("ROOSTOS_SESSION_BUS") == "1"
        default_client = RoostClient(session=session_bus)
    container.register(RoostClient, instance=default_client)

    # Register domain services
    container.register(DeviceService, scope=punq.Scope.singleton)
    container.register(FirewallService, scope=punq.Scope.singleton)
    container.register(NetworkService, scope=punq.Scope.singleton)
    container.register(SchedulesService, scope=punq.Scope.singleton)
    container.register(PluginsService, scope=punq.Scope.singleton)
    container.register(SystemService, scope=punq.Scope.singleton)

    return container


class EngineDIModule:
    """Backwards-compatibility module for EngineDIModule."""
    def __init__(
        self,
        config_dir: str = "/etc/roostos",
        staged_dir: Optional[str] = None,
        cert_dir: Optional[str] = None,
        providers_settings: Optional[ProvidersSettings] = None
    ) -> None:
        self.config_dir = config_dir
        self.staged_dir = staged_dir
        self.cert_dir = cert_dir
        self.providers_settings = providers_settings


def create_engine_container(
    config_dir: str = "/etc/roostos",
    staged_dir: Optional[str] = None,
    cert_dir: Optional[str] = None,
    providers_settings: Optional[ProvidersSettings] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> RoostContainer:
    """Factory creating a RoostContainer configured with core engine providers and services."""
    settings = providers_settings or load_providers_settings(config_dir, overrides=overrides)
    container = RoostContainer()
    return configure_engine_container(
        container=container,
        config_dir=config_dir,
        staged_dir=staged_dir,
        cert_dir=cert_dir,
        providers_settings=settings
    )


create_engine_injector = create_engine_container
