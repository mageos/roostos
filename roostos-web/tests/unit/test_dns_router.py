"""Unit tests for DNS router and dependency endpoints in roostos-web."""

from typing import Any, Dict, List
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from roostos_engine.config import (
    RoostConfig,
    SystemSettings,
    SystemConfig,
    SystemDNSConfig,
    NetworkSettings,
    WifiSettings,
)
from roostos_engine.models.plugins import PluginsConfig
from roostos_engine.models.firewall import FirewallSettings
from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.repository import ConfigRepository
from roostos_engine.pkg_manager.models import InstallResult
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.auth import create_access_token
from roostos_web.di import create_web_injector, set_injector


class DummyConfigRepository(ConfigRepository):
    def __init__(self) -> None:
        self.config = MagicMock(spec=RoostConfig)
        self.config.system = SystemSettings(
            hostname="test-gateway",
            domain="test-lan",
            dns=SystemDNSConfig(subsystem="local", forwarders=["1.1.1.1", "8.8.8.8"], ad_blocking_enabled=False),
        )
        self.config.users = []
        self.config.devices = []
        self.config.firewall = FirewallSettings()
        self.config.network = NetworkSettings()
        self.config.wifi = WifiSettings()
        self.config.vpns = []
        self.config.plugins = PluginsConfig(plugins=[])
        self.config.people = []
        self.config.buildings = []
        self.config.rooms = []
        self.config.nodes = []

    def get_config(self) -> RoostConfig:
        return self.config

    def save_system_config(self, data: SystemConfig) -> None:
        self.config.system = data.system
        self.config.users = data.users

    def save_plugins_config(self, data: PluginsConfig) -> None:
        self.config.plugins = data

    def save_nodes_config(self, data: Any) -> None:
        pass

    def save_devices_config(self, data: Any) -> None:
        pass

    def save_network_config(self, data: Any) -> None:
        pass

    def save_schedules_config(self, data: Any) -> None:
        pass

    def save_firewall_config(self, data: Any) -> None:
        pass


@pytest.fixture
def mock_dependencies(tmp_path: Any):
    repo = DummyConfigRepository()
    dbus = AsyncMock(spec=RoostClient)
    dbus._bus = None
    dbus.get_config.return_value = repo.config

    injector = create_web_injector(
        config_dir=str(tmp_path),
        dbus_client=dbus,
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="memory", system_client="mock"),
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus
    yield repo, dbus
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers() -> Dict[str, str]:
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def parent_headers() -> Dict[str, str]:
    token = create_access_token({"sub": "parent", "role": "parent"})
    return {"Authorization": f"Bearer {token}"}


def test_get_dns_config(mock_dependencies: Any, parent_headers: Dict[str, str]):
    client = TestClient(app)
    response = client.get("/api/dns/config", headers=parent_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["subsystem"] == "local"
    assert "forwarders" in data
    assert "dependencies" in data
    assert data["dependencies"]["feature"] == "dns_local"


def test_update_dns_config_to_technitium(
    mock_dependencies: Any, admin_headers: Dict[str, str]
):
    repo, dbus = mock_dependencies
    client = TestClient(app)

    payload = {
        "subsystem": "technitium",
        "forwarders": ["9.9.9.9"],
        "ad_blocking_enabled": True,
        "auto_install_dependencies": False,
    }
    response = client.post("/api/dns/config", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["subsystem"] == "technitium"
    assert data["ad_blocking_enabled"] is True
    assert data["dependencies"]["feature"] == "dns_technitium"

    # Verify plugins were updated with technitium-dns container
    plugins = repo.config.plugins.plugins
    tech_plugin = next((p for p in plugins if p.id == "technitium-dns"), None)
    assert tech_plugin is not None
    assert tech_plugin.enabled is True
    assert tech_plugin.containers[0].name == "dns-server"


def test_update_dns_config_with_auto_install(
    mock_dependencies: Any, admin_headers: Dict[str, str]
):
    client = TestClient(app)

    with patch("roostos_web.routers.dns.detect_package_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.install_packages.return_value = InstallResult(
            success=True,
            installed=["docker.io"],
            message="Installed successfully",
        )
        mock_mgr_getter.return_value = mock_mgr

        payload = {
            "subsystem": "technitium",
            "forwarders": ["1.1.1.1"],
            "ad_blocking_enabled": True,
            "auto_install_dependencies": True,
        }
        response = client.post("/api/dns/config", json=payload, headers=admin_headers)
        assert response.status_code == 200
        mock_mgr.install_packages.assert_called_once()


def test_system_dependencies_overview(
    mock_dependencies: Any, parent_headers: Dict[str, str]
):
    client = TestClient(app)
    response = client.get("/api/system/dependencies", headers=parent_headers)
    assert response.status_code == 200
    data = response.json()
    assert "manager_name" in data
    assert "os_family" in data
    assert "reports" in data
    features = [r["feature"] for r in data["reports"]]
    assert "gateway" in features
    assert "dns_local" in features
    assert "dns_technitium" in features


def test_install_system_dependencies(
    mock_dependencies: Any, admin_headers: Dict[str, str]
):
    client = TestClient(app)

    with patch("roostos_web.routers.system.detect_package_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.install_packages.return_value = InstallResult(
            success=True,
            installed=["nftables", "dnsmasq"],
            message="Packages installed",
        )
        mock_mgr_getter.return_value = mock_mgr

        payload = {"feature": "dns_local"}
        response = client.post(
            "/api/system/dependencies/install", json=payload, headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_mgr.install_packages.assert_called_once()
