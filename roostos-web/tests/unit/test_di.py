"""Unit tests for Dependency Injection, providers.yaml parsing, and container resolution."""

import os
import tempfile
import pytest
import yaml
from injector import Injector, inject

from roostos_engine.models.providers import ProvidersSettings, ProvidersConfigFile
from roostos_engine.di import (
    load_providers_settings,
    EngineDIModule,
    create_engine_injector,
)
from roostos_engine.repository import (
    ConfigRepository,
    StagingConfigRepository,
    YAMLConfigRepository,
    InMemoryConfigRepository,
)
from roostos_engine.cert_manager import CertificateManager
from roostos_sdk.client import RoostClient

from roostos_web.interfaces.auth import AuthProvider, PAMAuthProvider, MockAuthProvider
from roostos_web.di import (
    WebDIModule,
    create_web_injector,
    get_injector,
    set_injector,
    Injected,
)
from roostos_web.services.devices import DeviceService
from roostos_web.services.network import NetworkService
from roostos_web.services.system import SystemService
from roostos_web.services.schedules import SchedulesService
from roostos_web.services.plugins import PluginsService


def test_load_providers_settings_defaults():
    settings = load_providers_settings(config_dir="/nonexistent/dir")
    assert settings.auth_provider in ("pam", "mock")
    assert settings.config_repository == "staging"
    assert settings.system_client == "dbus"
    assert settings.cert_manager == "standard"
    assert settings.firewall_manager == "nftables"


def test_load_providers_settings_from_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        prov_file = os.path.join(tmp_dir, "providers.yaml")
        with open(prov_file, "w") as f:
            yaml.safe_dump({
                "providers": {
                    "auth_provider": "mock",
                    "config_repository": "yaml",
                    "system_client": "mock",
                    "cert_manager": "mock",
                    "firewall_manager": "mock"
                }
            }, f)

        settings = load_providers_settings(config_dir=tmp_dir)
        assert settings.auth_provider == "mock"
        assert settings.config_repository == "yaml"
        assert settings.system_client == "mock"
        assert settings.cert_manager == "mock"
        assert settings.firewall_manager == "mock"


def test_load_providers_settings_overrides():
    with tempfile.TemporaryDirectory() as tmp_dir:
        prov_file = os.path.join(tmp_dir, "providers.yaml")
        with open(prov_file, "w") as f:
            yaml.safe_dump({
                "providers": {
                    "auth_provider": "pam",
                    "config_repository": "staging"
                }
            }, f)

        overrides = {
            "auth_provider": "mock",
            "config_repository": "memory"
        }
        settings = load_providers_settings(config_dir=tmp_dir, overrides=overrides)
        assert settings.auth_provider == "mock"
        assert settings.config_repository == "memory"


def test_engine_injector_resolution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = ProvidersSettings(
            auth_provider="mock",
            config_repository="staging",
            system_client="mock"
        )
        injector = create_engine_injector(config_dir=tmp_dir, providers_settings=settings)
        repo = injector.get(ConfigRepository)
        assert isinstance(repo, StagingConfigRepository)

        cert_mgr = injector.get(CertificateManager)
        assert isinstance(cert_mgr, CertificateManager)


def test_engine_injector_in_memory_repo():
    settings = ProvidersSettings(config_repository="memory")
    injector = create_engine_injector(providers_settings=settings)
    repo = injector.get(ConfigRepository)
    assert isinstance(repo, InMemoryConfigRepository)


def test_web_injector_service_resolution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = ProvidersSettings(
            auth_provider="mock",
            config_repository="memory",
            system_client="mock"
        )
        injector = create_web_injector(config_dir=tmp_dir, providers_settings=settings)

        auth_prov = injector.get(AuthProvider)
        assert isinstance(auth_prov, MockAuthProvider)
        assert auth_prov.authenticate("admin", "password") is True
        assert auth_prov.authenticate("admin", "wrong") is False

        device_service = injector.get(DeviceService)
        assert isinstance(device_service, DeviceService)
        assert isinstance(device_service.repo, InMemoryConfigRepository)

        net_service = injector.get(NetworkService)
        assert isinstance(net_service, NetworkService)

        sys_service = injector.get(SystemService)
        assert isinstance(sys_service, SystemService)

        sched_service = injector.get(SchedulesService)
        assert isinstance(sched_service, SchedulesService)

        plg_service = injector.get(PluginsService)
        assert isinstance(plg_service, PluginsService)


def test_pam_auth_provider_interface():
    pam_prov = PAMAuthProvider()
    # Non-existent user should fail PAM cleanly without crashing
    assert pam_prov.authenticate("non_existent_dummy_user_12345", "badpassword") is False


class SampleInjectedClass:
    @inject
    def __init__(self, auth: AuthProvider, repo: ConfigRepository):
        self.auth = auth
        self.repo = repo


def test_custom_class_injection():
    settings = ProvidersSettings(auth_provider="mock", config_repository="memory")
    injector = create_web_injector(providers_settings=settings)
    instance = injector.get(SampleInjectedClass)
    assert isinstance(instance.auth, MockAuthProvider)
    assert isinstance(instance.repo, InMemoryConfigRepository)


def test_multi_authority_di_injection():
    from roostos_web.interfaces.auth import MultiAuthorityAuthProvider
    settings = ProvidersSettings(auth_provider="multi_authority", config_repository="memory")
    injector = create_web_injector(providers_settings=settings)
    auth_prov = injector.get(AuthProvider)
    assert isinstance(auth_prov, MultiAuthorityAuthProvider)

