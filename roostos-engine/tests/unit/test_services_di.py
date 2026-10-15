"""Unit tests for punq DI resolution and shared domain services in roostos-engine."""

import pytest
import punq
from roostos_engine.di import create_engine_container, RoostContainer
from roostos_engine.repository import ConfigRepository, InMemoryConfigRepository
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.services import (
    DeviceService,
    FirewallService,
    NetworkService,
    SchedulesService,
    PluginsService,
    SystemService,
)
from roostos_sdk.mock_client import MockRoostClient


def test_engine_container_resolves_all_services():
    container = create_engine_container(
        overrides={"config_repository": "memory", "system_client": "mock"}
    )
    assert isinstance(container, RoostContainer)

    # Verify providers
    repo = container.resolve(ConfigRepository)
    assert isinstance(repo, InMemoryConfigRepository)

    # Verify domain services
    device_service = container.resolve(DeviceService)
    assert isinstance(device_service, DeviceService)
    assert device_service.repo is repo

    firewall_service = container.resolve(FirewallService)
    assert isinstance(firewall_service, FirewallService)

    network_service = container.resolve(NetworkService)
    assert isinstance(network_service, NetworkService)

    schedules_service = container.resolve(SchedulesService)
    assert isinstance(schedules_service, SchedulesService)

    system_service = container.resolve(SystemService)
    assert isinstance(system_service, SystemService)

    plugins_service = container.resolve(PluginsService)
    assert isinstance(plugins_service, PluginsService)


def test_device_service_crud_and_validation():
    container = create_engine_container(
        overrides={"config_repository": "memory", "system_client": "mock"}
    )
    service = container.resolve(DeviceService)

    # 1. Register a person first
    person = service.register_person(name="Alice Smith", role="adult")
    assert person.name == "Alice Smith"

    # 2. Register a device with valid owner
    dev = service.register_device(
        mac="AA:BB:CC:DD:EE:01",
        name="Alice's Phone",
        owner=person.id,
        tags=["mobile", "trusted"],
    )
    assert dev.mac == "aa:bb:cc:dd:ee:01"
    assert dev.owner == person.id

    # 3. Register a device with non-existent owner raises ValueError
    with pytest.raises(ValueError, match="Owner 'ghost' does not exist"):
        service.register_device(mac="AA:BB:CC:DD:EE:02", name="Ghost Device", owner="ghost")

    # 4. Delete device
    deleted = service.delete_device("aa:bb:cc:dd:ee:01")
    assert deleted is True

    # 5. Delete non-existent device returns False
    assert service.delete_device("aa:bb:cc:dd:ee:01") is False


def test_firewall_service_crud():
    container = create_engine_container(
        overrides={"config_repository": "memory", "system_client": "mock"}
    )
    fw_service = container.resolve(FirewallService)

    # Add port forward
    pf = fw_service.add_port_forward(
        name="Web Server", proto="tcp", ext_port=8080, int_ip="192.168.1.100", int_port=80
    )
    assert pf.name == "Web Server"
    assert pf.external_port == 8080

    cfg = fw_service.get_firewall_config()
    assert any(p.name == "Web Server" for p in cfg.firewall.port_forwards)

    # Delete port forward
    assert fw_service.delete_port_forward("Web Server") is True
    assert fw_service.delete_port_forward("Web Server") is False
