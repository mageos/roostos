import os
import json
import pytest
from roostos_engine.config import load_config_directory
from roostos_engine.state_db import StateDB
from roostos_engine.dhcp_manager import DHCPManager

def test_state_db_leases_and_upnp(tmp_path):
    """Verifies SQLite transient lease cache and UPnP staging operations."""
    db_file = tmp_path / "test_state.db"
    db = StateDB(str(db_file))
    
    # 1. Test register_lease
    assert db.register_lease("aa:bb:cc:dd:ee:ff", "192.168.1.100", "test-device", quarantined=True) is True
    leases = db.get_active_leases()
    assert len(leases) == 1
    assert leases[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert leases[0]["ip"] == "192.168.1.100"
    assert leases[0]["hostname"] == "test-device"
    assert leases[0]["quarantined"] is True
    
    # 2. Test release_lease
    assert db.release_lease("aa:bb:cc:dd:ee:ff") is True
    assert len(db.get_active_leases()) == 0

    # 3. Test pending UPnP queue operations
    row_id = db.add_pending_upnp(
        mac="00:11:22:33:44:55",
        internal_ip="192.168.1.10",
        ext_port=3074,
        int_port=3074,
        protocol="udp",
        description="Xbox Live"
    )
    assert row_id > 0
    
    pending = db.get_pending_upnp()
    assert len(pending) == 1
    assert pending[0]["mac"] == "00:11:22:33:44:55"
    assert pending[0]["port"] == 3074
    assert pending[0]["protocol"] == "udp"

    # 4. Test remove_pending_upnp
    assert db.remove_pending_upnp("00:11:22:33:44:55", 3074, "udp") is True
    assert len(db.get_pending_upnp()) == 0


def test_kea_config_generation(temp_config_dir, tmp_path):
    """Verifies that DHCPManager generates a correct Kea DHCP4 JSON configuration."""
    config = load_config_directory(temp_config_dir)
    kea_file = tmp_path / "kea-dhcp4.conf"
    
    manager = DHCPManager(config, str(kea_file))
    kea_json = manager.compile_kea_config()
    
    # Assert top-level structure
    assert "Dhcp4" in kea_json
    dhcp4 = kea_json["Dhcp4"]
    assert "br0" in dhcp4["interfaces-config"]["interfaces"]
    
    # Verify subnets compiled
    subnets = dhcp4["subnet4"]
    # We have br0 (living_room) and vlan-guest (from conftest.py network definition)
    # Actually conftest.py defines eth0 (wan), eth1 (lan/br0) and br0 ip 192.168.1.1/24
    # Wait, does it define VLANs in conftest.py? Let's check:
    # conftest.py: system.yaml, network.yaml, devices.yaml.
    # devices.yaml has room: living_room (building main_house)
    # devices.yaml has devices: Mom's Laptop (mac a4:83:e7:12:34:56, static_ip 192.168.1.10)
    # Alice's iPad (mac 4c:32:75:98:76:54, static_ip 192.168.1.50)
    assert len(subnets) >= 1
    lan_subnet = next(s for s in subnets if s["subnet"] == "192.168.1.0/24")
    assert lan_subnet["interface"] == "br0"
    
    # Verify routers and DNS settings
    options = lan_subnet["option-data"]
    assert any(o["name"] == "routers" and o["data"] == "192.168.1.1" for o in options)
    assert any(o["name"] == "domain-name-servers" and o["data"] == "192.168.1.1" for o in options)

    # Verify static IP reservations are mapped
    reservations = lan_subnet["reservations"]
    assert len(reservations) == 2
    assert any(r["hw-address"] == "a4:83:e7:12:34:56" and r["ip-address"] == "192.168.1.10" for r in reservations)
    assert any(r["hw-address"] == "4c:32:75:98:76:54" and r["ip-address"] == "192.168.1.50" for r in reservations)

    # Write config to disk and verify
    manager.write_config()
    assert os.path.exists(kea_file)
    with open(kea_file, "r") as f:
        written_data = json.load(f)
    assert written_data["Dhcp4"]["interfaces-config"]["interfaces"] == ["br0"]


def test_kea_config_generation_custom_scopes(temp_config_dir, tmp_path):
    """Verifies that DHCPManager handles custom DHCP pools and disabled DHCP services correctly."""
    config = load_config_directory(temp_config_dir)
    
    # Configure custom scope on br0
    assert len(config.network.bridges) > 0
    config.network.bridges[0].dhcp_pool_start = "192.168.1.150"
    config.network.bridges[0].dhcp_pool_end = "192.168.1.220"
    
    # Configure a VLAN with DHCP disabled
    from roostos_engine.config import NetworkVlan
    disabled_vlan = NetworkVlan(
        name="vlan-disabled",
        id=99,
        interface="eth1",
        ip="10.0.99.1/24",
        dhcp_enabled=False
    )
    config.network.vlans.append(disabled_vlan)

    # Configure another VLAN with custom pool
    custom_vlan = NetworkVlan(
        name="vlan-custom",
        id=10,
        interface="eth1",
        ip="10.0.10.1/24",
        dhcp_enabled=True,
        dhcp_pool_start="10.0.10.20",
        dhcp_pool_end="10.0.10.80"
    )
    config.network.vlans.append(custom_vlan)

    kea_file = tmp_path / "kea-dhcp4.conf"
    manager = DHCPManager(config, str(kea_file))
    kea_json = manager.compile_kea_config()
    
    dhcp4 = kea_json["Dhcp4"]
    interfaces = dhcp4["interfaces-config"]["interfaces"]
    subnets = dhcp4["subnet4"]

    # Verify disabled VLAN subnet is NOT in Kea config
    assert "vlan-disabled" not in interfaces
    assert not any(s["interface"] == "vlan-disabled" for s in subnets)

    # Verify custom VLAN subnet is IN Kea config
    assert "vlan-custom" in interfaces
    vlan_subnet = next(s for s in subnets if s["interface"] == "vlan-custom")
    assert vlan_subnet["subnet"] == "10.0.10.0/24"
    assert vlan_subnet["pools"] == [{"pool": "10.0.10.20 - 10.0.10.80"}]

    # Verify bridge has custom pool
    br_subnet = next(s for s in subnets if s["interface"] == "br0")
    assert br_subnet["pools"] == [{"pool": "192.168.1.150 - 192.168.1.220"}]
