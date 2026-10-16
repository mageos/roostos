"""Unit tests for Kea DHCP router endpoints in roostos-web."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.config import (
    RoostConfig,
    NetworkBridge,
    DeviceConfig,
    SystemSettings,
    SystemDNSConfig,
    WifiSettings,
)
from roostos_engine.repository import ConfigRepository, InMemoryConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app
from roostos_web.auth import create_access_token
from roostos_web.services.base import get_repository, get_dbus_client
from roostos_web.services.kea_service import KeaService
from roostos_web.di import set_injector, create_web_injector
from roostos_engine.models.providers import ProvidersSettings


class FakeConfigRepo(InMemoryConfigRepository):
    def __init__(self):
        super().__init__()
        self.config = MagicMock(spec=RoostConfig)
        self.config.system = SystemSettings(hostname="test-router", domain="lan.roost", dns=SystemDNSConfig())
        self.config.network = MagicMock()
        self.config.network.bridges = [
            NetworkBridge(
                name="br-lan",
                ip="192.168.1.1/24",
                dhcp_enabled=True,
                dhcp_pool_start="192.168.1.100",
                dhcp_pool_end="192.168.1.250",
            )
        ]
        self.config.network.vlans = []
        self.config.devices = [
            DeviceConfig(mac="10:9a:dd:33:44:55", name="Test Device", static_ip="192.168.1.50")
        ]
        self.config.people = []
        self.config.buildings = []
        self.config.rooms = []

    def get_config(self) -> RoostConfig:
        return self.config

    def save_network_config(self, net_cfg) -> None:
        self.config.network = net_cfg

    def save_devices_config(self, dev_cfg) -> None:
        self.config.devices = dev_cfg.devices


@pytest.fixture
def mock_deps(tmp_path):
    repo = FakeConfigRepo()
    dbus = AsyncMock(spec=RoostClient)
    dbus.get_active_leases.return_value = [
        {"ip": "192.168.1.105", "mac": "aa:bb:cc:dd:ee:ff", "hostname": "Test-Client", "network": "br-lan", "expires": 3600}
    ]
    dbus.get_config.return_value = True

    kea_service = KeaService(repo=repo, dbus=dbus)
    injector = create_web_injector(
        config_dir=str(tmp_path),
        dbus_client=dbus,
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="memory", system_client="mock"),
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    injector.binder.bind(KeaService, to=kea_service)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus
    yield repo, dbus
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_list_dhcp_scopes(mock_deps, auth_headers):
    client = TestClient(app)
    resp = client.get("/api/v1/dhcp/scopes", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["interface"] == "br-lan"
    assert data[0]["gateway"] == "192.168.1.1"


def test_get_active_leases(mock_deps, auth_headers):
    client = TestClient(app)
    resp = client.get("/api/v1/dhcp/leases", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(l["mac"] == "aa:bb:cc:dd:ee:ff" for l in data)


def test_convert_lease_to_static(mock_deps, auth_headers):
    client = TestClient(app)
    payload = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "hostname": "Permanent-Client",
        "description": "Office workstation"
    }
    resp = client.post("/api/v1/dhcp/reservations/from-lease", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mac"] == "aa:bb:cc:dd:ee:ff"
    assert data["reserved_ip"] == "192.168.1.105"
    assert data["hostname"] == "Permanent-Client"


def test_list_and_delete_reservations(mock_deps, auth_headers):
    client = TestClient(app)
    resp = client.get("/api/v1/dhcp/reservations", headers=auth_headers)
    assert resp.status_code == 200
    reservations = resp.json()
    assert len(reservations) >= 1

    del_resp = client.delete("/api/v1/dhcp/reservations/10:9a:dd:33:44:55", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"
