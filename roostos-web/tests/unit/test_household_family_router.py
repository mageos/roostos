"""Unit tests for Household Hub, Family, and Protection router endpoints in roostos-web."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.config import (
    RoostConfig,
    SystemSettings,
    SystemDNSConfig,
    NetworkSettings,
    WifiSettings,
    WifiAccessPoint,
    DeviceConfig,
    PersonConfig,
)
from roostos_engine.repository import ConfigRepository, InMemoryConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app
from roostos_web.auth import create_access_token
from roostos_web.services.base import get_repository, get_dbus_client
from roostos_web.services import DeviceService, SystemService
from roostos_web.di import set_injector, create_web_injector
from roostos_engine.models.providers import ProvidersSettings


class DummyRepo(InMemoryConfigRepository):
    def __init__(self):
        super().__init__()
        self.config = MagicMock(spec=RoostConfig)
        self.config.system = SystemSettings(
            hostname="roost-home-router",
            domain="lan.roost",
            dns=SystemDNSConfig(subsystem="technitium", forwarders=["1.1.1.1"], ad_blocking_enabled=True),
        )
        self.config.network = MagicMock()
        self.config.network.wifi = WifiSettings(
            access_points=[
                WifiAccessPoint(
                    name="Guest AP",
                    ssid="RoostHome-Guest",
                    passphrase="GuestWelcome2026",
                    security="wpa2-psk",
                    radio="wlan0",
                    bridge="br-guest",
                )
            ]
        )
        self.config.people = [
            PersonConfig(id="dad", name="Dad", dns_profile="standard"),
            PersonConfig(id="alice", name="Alice", dns_profile="kids"),
        ]
        self.config.devices = [
            DeviceConfig(mac="aa:bb:cc:11:22:33", name="Alice iPad", owner="alice")
        ]
        self.config.buildings = []
        self.config.rooms = []

    def get_config(self) -> RoostConfig:
        return self.config

    def save_network_config(self, net_cfg) -> None:
        self.config.network = net_cfg

    def save_devices_config(self, dev_cfg) -> None:
        self.config.devices = dev_cfg.devices
        self.config.people = dev_cfg.people

    def save_system_config(self, sys_cfg) -> None:
        self.config.system = sys_cfg.system


@pytest.fixture
def test_setup(tmp_path):
    repo = DummyRepo()
    dbus = AsyncMock(spec=RoostClient)
    dbus.grant_time_extension.return_value = True
    dbus.remove_time_extension.return_value = True
    dbus.get_active_leases.return_value = []
    dbus.get_config.return_value = True

    device_service = DeviceService(repo=repo, dbus=dbus)
    system_service = SystemService(repo=repo, dbus=dbus)

    injector = create_web_injector(
        config_dir=str(tmp_path),
        dbus_client=dbus,
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="memory", system_client="mock"),
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    injector.binder.bind(DeviceService, to=device_service)
    injector.binder.bind(SystemService, to=system_service)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus

    token = create_access_token(data={"sub": "dad", "role": "parent"})
    headers = {"Authorization": f"Bearer {token}"}
    yield TestClient(app), headers
    app.dependency_overrides.clear()


def test_household_pulse(test_setup):
    client, headers = test_setup
    resp = client.get("/api/v1/household/pulse", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["hostname"] == "roost-home-router"
    assert "wan_ip" in data
    assert "ping_ms" in data
    assert "status" in data


def test_guest_wifi_flow(test_setup):
    client, headers = test_setup
    resp = client.get("/api/v1/household/guest-wifi", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ssid"] == "RoostHome-Guest"
    assert "qr_payload" in data
    assert data["qr_payload"].startswith("WIFI:S:RoostHome-Guest;")

    toggle_resp = client.post("/api/v1/household/guest-wifi/toggle", json={"enabled": False}, headers=headers)
    assert toggle_resp.status_code == 200


def test_speedtest(test_setup):
    client, headers = test_setup
    resp = client.post("/api/v1/household/speedtest", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["download_mbps"] > 500
    assert data["upload_mbps"] > 500


def test_family_people_and_bonus(test_setup):
    client, headers = test_setup
    resp = client.get("/api/v1/family/people", headers=headers)
    assert resp.status_code == 200
    people = resp.json()
    assert len(people) >= 2
    alice = next((p for p in people if p["id"] == "alice"), None)
    assert alice is not None
    assert alice["role"] == "kid"

    bonus_resp = client.post("/api/v1/family/people/alice/bonus", json={"duration_minutes": 30}, headers=headers)
    assert bonus_resp.status_code == 200
    assert bonus_resp.json()["status"] == "success"


def test_pause_kids_and_dinner_time(test_setup):
    client, headers = test_setup
    pause_resp = client.post("/api/v1/family/pause-kids", json={"paused": True}, headers=headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["action"] == "pause_kids"

    dinner_resp = client.post("/api/v1/family/dinner-time", json={"duration_minutes": 60}, headers=headers)
    assert dinner_resp.status_code == 200
    assert dinner_resp.json()["action"] == "dinner_time"


def test_protection_threat_feed_and_shields(test_setup):
    client, headers = test_setup
    feed_resp = client.get("/api/v1/protection/blocked-feed", headers=headers)
    assert feed_resp.status_code == 200
    feed = feed_resp.json()
    assert len(feed) >= 1

    allow_resp = client.post("/api/v1/protection/allow", json={"target": "adservice.google.com", "subsystem": "DNS Sinkhole"}, headers=headers)
    assert allow_resp.status_code == 200
    assert allow_resp.json()["status"] == "success"

    shields_resp = client.get("/api/v1/protection/shields", headers=headers)
    assert shields_resp.status_code == 200
    assert shields_resp.json()["ad_blocking_enabled"] is True


def test_create_and_delete_family_person(test_setup):
    client, headers = test_setup
    create_resp = client.post(
        "/api/v1/family/people",
        json={"name": "Grandma", "role": "member", "screentime_limit_minutes": 0, "filter_level": "Standard"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["id"] == "grandma"
    assert created["name"] == "Grandma"

    # Verify present in list
    list_resp = client.get("/api/v1/family/people", headers=headers)
    assert any(p["id"] == "grandma" for p in list_resp.json())

    # Delete
    del_resp = client.delete("/api/v1/family/people/grandma", headers=headers)
    assert del_resp.status_code == 204

    # Verify absent from list
    after_del = client.get("/api/v1/family/people", headers=headers)
    assert not any(p["id"] == "grandma" for p in after_del.json())


def test_pause_individual_person(test_setup):
    client, headers = test_setup
    pause_resp = client.post("/api/v1/family/people/alice/pause", json={"paused": True}, headers=headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["action"] == "pause_person"

    resume_resp = client.post("/api/v1/family/people/alice/pause", json={"paused": False}, headers=headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["action"] == "resume_person"

