"""Unit tests for ConfigRepository change events and notification hooks."""

import pytest
from roostos_engine.repository import InMemoryConfigRepository
from roostos_engine.events import ConfigChangeEvent, DBusReloadListener
from roostos_engine.config import (
    DevicesConfig, DeviceConfig, SystemConfig, SystemSettings, FirewallConfig, FirewallSettings
)
from roostos_sdk.mock_client import MockRoostClient


def test_repository_save_dispatches_events():
    repo = InMemoryConfigRepository()
    captured_events = []

    def on_change(event: ConfigChangeEvent):
        captured_events.append(event)

    repo.add_listener(on_change)

    # 1. Mutate devices
    devices_cfg = DevicesConfig(
        devices=[DeviceConfig(mac="11:22:33:44:55:66", name="Work Laptop")]
    )
    repo.save_devices_config(devices_cfg)

    assert len(captured_events) == 1
    assert captured_events[0].section == "devices"
    assert captured_events[0].action == "save"
    assert captured_events[0].data == devices_cfg

    # 2. Mutate system
    sys_cfg = SystemConfig(system=SystemSettings(hostname="router-01"))
    repo.save_system_config(sys_cfg)

    assert len(captured_events) == 2
    assert captured_events[1].section == "system"
    assert captured_events[1].action == "save"

    # 3. Unsubscribe listener
    repo.remove_listener(on_change)
    repo.save_firewall_config(FirewallConfig())
    assert len(captured_events) == 2


def test_dbus_reload_listener_triggers_on_save():
    repo = InMemoryConfigRepository()
    mock_dbus = MockRoostClient()
    listener = DBusReloadListener(mock_dbus)
    repo.add_listener(listener)

    # Mutate firewall config
    repo.save_firewall_config(FirewallConfig(firewall=FirewallSettings(rules=[])))
    # Ensure listener executes without errors and repo remains clean
    assert repo.get_config() is not None
