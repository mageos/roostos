"""Unit tests for Devices router and hostname resolution in roostos-web."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.config import (
    RoostConfig,
    SystemSettings,
    DeviceConfig,
    PersonConfig,
)
from roostos_engine.models.devices import DevicesConfig
from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.repository import InMemoryConfigRepository, ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.auth import create_access_token
from roostos_web.services import DeviceService
from roostos_web.di import set_injector, create_web_injector



class DeviceTestRepo(InMemoryConfigRepository):
    def __init__(self):
        super().__init__()
        self.config = MagicMock(spec=RoostConfig)
        self.config.system = SystemSettings(hostname="roost-router")
        self.config.people = [PersonConfig(id="dad", name="Dad")]
        self.config.buildings = []
        self.config.rooms = []
        self.config.devices = [
            # Device with generic auto-generated name
            DeviceConfig(mac="aa:bb:cc:11:22:33", name="Device-2233", owner="dad"),
            # Device with user-assigned custom name
            DeviceConfig(mac="aa:bb:cc:44:55:66", name="Dad Office PC", owner="dad"),
        ]

    def get_config(self) -> RoostConfig:
        return self.config

    def save_devices_config(self, data: DevicesConfig) -> None:
        self.config.devices = data.devices
        self.config.people = data.people


@pytest.fixture
def device_client(tmp_path):
    repo = DeviceTestRepo()
    mock_dbus = AsyncMock(spec=RoostClient)
    mock_dbus.get_active_leases.return_value = [
        {"mac": "aa:bb:cc:11:22:33", "ip": "192.168.1.101", "hostname": "Dads-MacBook-Pro"},
        {"mac": "aa:bb:cc:44:55:66", "ip": "192.168.1.102", "hostname": "custom-pc-host"},
        {"mac": "11:22:33:77:88:99", "ip": "192.168.1.103", "hostname": "LivingRoom-Roku"},
    ]

    device_service = DeviceService(repo=repo, dbus=mock_dbus)
    injector = create_web_injector(
        config_dir=str(tmp_path),
        dbus_client=mock_dbus,
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="memory", system_client="mock"),
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=mock_dbus)
    injector.binder.bind(DeviceService, to=device_service)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: mock_dbus

    client = TestClient(app)
    token = create_access_token({"sub": "admin", "role": "admin"})
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    app.dependency_overrides.clear()


def test_get_devices_uses_hostnames(device_client):
    res = device_client.get("/api/v1/devices")
    assert res.status_code == 200
    data = res.json()
    devices = data["devices"]
    assert len(devices) == 2

    # Device 1: generic name 'Device-2233' should be replaced by hostname 'Dads-MacBook-Pro'
    dev1 = next(d for d in devices if d["mac"] == "aa:bb:cc:11:22:33")
    assert dev1["name"] == "Dads-MacBook-Pro"
    assert dev1["hostname"] == "Dads-MacBook-Pro"

    # Device 2: custom name 'Dad Office PC' preserved, while hostname is also populated
    dev2 = next(d for d in devices if d["mac"] == "aa:bb:cc:44:55:66")
    assert dev2["name"] == "Dad Office PC"
    assert dev2["hostname"] == "custom-pc-host"

    # Active leases contain full details
    assert len(data["active_leases"]) == 3
    assert data["active_leases"][0]["hostname"] == "Dads-MacBook-Pro"


def test_register_device_with_hostname(device_client):
    res = device_client.post("/api/v1/devices", json={
        "mac": "22:33:44:55:66:77",
        "name": "Smart Speaker",
        "hostname": "echo-dot-livingroom",
        "owner": "dad"
    })
    assert res.status_code == 200

    # Verify device was saved with hostname
    res2 = device_client.get("/api/v1/devices")
    devices = res2.json()["devices"]
    dev = next(d for d in devices if d["mac"] == "22:33:44:55:66:77")
    assert dev["name"] == "Smart Speaker"
    assert dev["hostname"] == "echo-dot-livingroom"
