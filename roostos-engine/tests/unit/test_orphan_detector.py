"""Unit tests for RoostOS Orphaned Records Detection and Cleanup Engine."""

import os
import shutil
import pytest
from pathlib import Path

from roostos_engine.models.node import NodeConfig, NodeRole, NodesConfigFile
from roostos_engine.models.system import SystemConfig, SystemSettings, ClusterSettingsConfig
from roostos_engine.models.network import NetworkConfig, NetworkSettings, NetworkBridge
from roostos_engine.models.devices import DevicesConfig, DeviceConfig, PersonConfig, BuildingConfig, RoomConfig
from roostos_engine.repository import YAMLConfigRepository
from roostos_engine.orphan_detector import scan_orphaned_records, cleanup_orphaned_records


@pytest.fixture
def test_repo_env(tmp_path: Path):
    config_dir = tmp_path / "roostos"
    config_dir.mkdir(parents=True, exist_ok=True)
    certs_dir = config_dir / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)

    repo = YAMLConfigRepository(str(config_dir))
    repo.save_system_config(SystemConfig(system=SystemSettings(
        hostname="router-01",
        cluster=ClusterSettingsConfig(node_id="node-01")
    )))
    repo.save_nodes_config(NodesConfigFile(nodes=[
        NodeConfig(id="node-01", name="Primary Router", roles=[NodeRole.GATEWAY_ROUTER]),
        NodeConfig(id="node-02", name="Active AP", roles=[NodeRole.ACCESS_POINT]),
    ]))
    repo.save_network_config(NetworkConfig(network=NetworkSettings(bridges=[
        NetworkBridge(name="br-lan", ip="192.168.1.1/24", ha_standby_node="none")
    ])))
    repo.save_devices_config(DevicesConfig(devices=[], people=[], buildings=[], rooms=[]))

    return repo, config_dir


def test_scan_no_orphans(test_repo_env):
    repo, config_dir = test_repo_env
    res = scan_orphaned_records(str(config_dir))
    assert res.total_orphans == 0
    assert len(res.orphans) == 0


def test_scan_orphaned_service_certificates(test_repo_env):
    repo, config_dir = test_repo_env
    valid_cert = config_dir / "certs" / "services" / "node-02"
    valid_cert.mkdir(parents=True, exist_ok=True)
    orphan_cert = config_dir / "certs" / "services" / "node-99"
    orphan_cert.mkdir(parents=True, exist_ok=True)

    res = scan_orphaned_records(str(config_dir))
    assert res.total_orphans == 1
    assert res.orphans[0].category == "certificate"
    assert res.orphans[0].identifier == "node-99"


def test_scan_orphaned_domain_certificates(test_repo_env):
    repo, config_dir = test_repo_env
    domain_dir = config_dir / "certs" / "domains" / "unused.example.com"
    domain_dir.mkdir(parents=True, exist_ok=True)

    res = scan_orphaned_records(str(config_dir))
    assert res.total_orphans == 1
    assert res.orphans[0].category == "domain_certificate"
    assert res.orphans[0].identifier == "unused.example.com"


def test_scan_orphaned_dhcp_standby(test_repo_env):
    repo, config_dir = test_repo_env
    net = repo.get_config().network
    net.bridges[0].ha_standby_node = "ghost-node-404"
    repo.save_network_config(NetworkConfig(network=net))

    res = scan_orphaned_records(str(config_dir))
    assert res.total_orphans == 1
    assert res.orphans[0].category == "dhcp_standby"
    assert "ghost-node-404" in res.orphans[0].description


def test_scan_orphaned_device_linkages(test_repo_env):
    repo, config_dir = test_repo_env
    repo.save_devices_config(DevicesConfig(
        devices=[
            DeviceConfig(
                mac="aa:bb:cc:dd:ee:ff",
                name="Orphaned Phone",
                owner="person-missing",
                location="building-missing"
            )
        ],
        people=[],
        buildings=[],
        rooms=[]
    ))

    res = scan_orphaned_records(str(config_dir))
    assert res.total_orphans == 2
    for o in res.orphans:
        assert o.category == "device_linkage"


def test_cleanup_orphaned_records(test_repo_env):
    repo, config_dir = test_repo_env
    orphan_cert = config_dir / "certs" / "services" / "node-dead"
    orphan_cert.mkdir(parents=True, exist_ok=True)
    orphan_domain = config_dir / "certs" / "domains" / "orphan.domain.tld"
    orphan_domain.mkdir(parents=True, exist_ok=True)

    net = repo.get_config().network
    net.bridges[0].ha_standby_node = "node-dead"
    repo.save_network_config(NetworkConfig(network=net))

    repo.save_devices_config(DevicesConfig(
        devices=[
            DeviceConfig(
                mac="11:22:33:44:55:66",
                name="Laptop",
                owner="nonexistent-person"
            )
        ],
        people=[],
        buildings=[],
        rooms=[]
    ))

    # Verify they exist
    scan_before = scan_orphaned_records(str(config_dir))
    assert scan_before.total_orphans == 4

    # Run cleanup
    clean_result = cleanup_orphaned_records(repo)
    assert len(clean_result["cleaned_records"]) >= 3

    # Verify disk paths removed
    assert not orphan_cert.exists()
    assert not orphan_domain.exists()

    # Verify configs updated
    cfg_after = repo.get_config()
    assert cfg_after.network.bridges[0].ha_standby_node == "none"
    assert cfg_after.devices[0].owner is None

    # Rescan should detect 0 orphans
    scan_after = scan_orphaned_records(str(config_dir))
    assert scan_after.total_orphans == 0
