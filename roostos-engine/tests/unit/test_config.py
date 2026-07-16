import os
import pytest
import yaml
from roostos_engine.config import load_config_directory, RoostConfig

def write_yaml(directory, filename, data):
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        yaml.safe_dump(data, f)

def test_load_config_directory_valid(temp_config_dir):
    """Verifies valid configurations are parsed and compiled successfully."""
    config = load_config_directory(temp_config_dir)
    assert isinstance(config, RoostConfig)
    assert config.system.hostname == "sandbox-router"
    assert len(config.users) == 2
    assert len(config.devices) == 2

    # Check MAC address normalization happened
    assert config.devices[1].mac == "4c:32:75:98:76:54"


def test_invalid_user_link(temp_config_dir):
    """Verifies that a user linking to an invalid person ID throws an error."""
    write_yaml(temp_config_dir, "system.yaml", {
        "system": {},
        "users": [
            {"username": "broken_user", "role": "parent", "person": "non_existent_profile"}
        ]
    })
    
    with pytest.raises(ValueError, match="references non-existent person ID"):
        load_config_directory(temp_config_dir)


def test_invalid_room_link(temp_config_dir):
    """Verifies that a room linking to an invalid building ID throws an error."""
    write_yaml(temp_config_dir, "system.yaml", {"system": {}, "users": []})
    write_yaml(temp_config_dir, "devices.yaml", {
        "people": [],
        "buildings": [],
        "rooms": [
            {"id": "broken_room", "name": "Broken Room", "building": "fake_building"}
        ]
    })
    
    with pytest.raises(ValueError, match="references non-existent building ID"):
        load_config_directory(temp_config_dir)


def test_invalid_device_owner(temp_config_dir):
    """Verifies device linking to an invalid owner triggers validation failure."""
    write_yaml(temp_config_dir, "system.yaml", {"system": {}, "users": []})
    write_yaml(temp_config_dir, "devices.yaml", {
        "people": [{"id": "mom", "name": "Mom"}],
        "devices": [
            {"mac": "00:11:22:33:44:55", "name": "Device", "owner": "non_existent_person"}
        ]
    })
    with pytest.raises(ValueError, match="references non-existent owner ID"):
        load_config_directory(temp_config_dir)


def test_invalid_schedule_target_mac(temp_config_dir):
    """Verifies schedule targeting an unregistered MAC triggers validation failure."""
    write_yaml(temp_config_dir, "schedules.yaml", {
        "firewall": {
            "schedules": [
                {
                    "name": "Block Unregistered MAC",
                    "targets": [{"mac": "aa:bb:cc:dd:ee:ff"}],
                    "action": "block_internet"
                }
            ]
        }
    })
    with pytest.raises(ValueError, match="target MAC .* is not registered under devices"):
        load_config_directory(temp_config_dir)


def test_resolve_location_macs_recursive(temp_config_dir):
    """Verifies recursive building/room MAC selector resolution works correctly."""
    config = load_config_directory(temp_config_dir)
    
    # 1. Resolve room level: living_room
    living_room_macs = config.resolve_location_macs("living_room")
    assert "a4:83:e7:12:34:56" in living_room_macs
    assert len(living_room_macs) == 1

    # 2. Resolve building level: main_house (includes living_room + child room device)
    building_macs = config.resolve_location_macs("main_house")
    assert len(building_macs) == 2
    assert "a4:83:e7:12:34:56" in building_macs
    assert "4c:32:75:98:76:54" in building_macs


def test_resolve_selector_macs(temp_config_dir):
    """Verifies all selector categories compile MAC addresses correctly."""
    config = load_config_directory(temp_config_dir)
    
    # Test resolving a tag selector: 'kids'
    target_tag = config.firewall.schedules[0].targets[0]
    assert target_tag.tag == "kids"
    macs = config.resolve_selector_macs(target_tag)
    assert "4c:32:75:98:76:54" in macs
    assert len(macs) == 1


def test_vpn_config_parsing(temp_config_dir):
    """Verifies that network configurations including VPN profiles are parsed correctly."""
    write_yaml(temp_config_dir, "network.yaml", {
        "network": {
            "interfaces": [{"name": "eth0", "role": "wan", "dhcp": True}]
        },
        "wifi": {
            "access_points": []
        },
        "vpns": [
            {
                "id": "wg_client",
                "name": "Mullvad WG",
                "type": "wireguard",
                "role": "client",
                "enabled": True,
                "config": {"endpoint": "1.2.3.4:51820"}
            }
        ]
    })
    config = load_config_directory(temp_config_dir)
    assert len(config.vpns) == 1
    assert config.vpns[0].id == "wg_client"
    assert config.vpns[0].name == "Mullvad WG"
    assert config.vpns[0].enabled is True
    assert config.vpns[0].config["endpoint"] == "1.2.3.4:51820"


def test_plugin_known_services_parsing(temp_config_dir):
    """Verifies that PluginConfig parses known_services under different aliases and formats."""
    # 1. Singular key name with string value (snake_case)
    write_yaml(temp_config_dir, "plugins.yaml", {
        "plugins": [
            {
                "id": "openvpn",
                "name": "OpenVPN Client",
                "enabled": True,
                "known_service": "vpnClient"
            }
        ]
    })
    config = load_config_directory(temp_config_dir)
    assert len(config.plugins) == 1
    assert config.plugins[0].known_services == ["vpnClient"]

    # 2. Singular key name with string value (camelCase)
    write_yaml(temp_config_dir, "plugins.yaml", {
        "plugins": [
            {
                "id": "wireguard",
                "name": "WireGuard",
                "enabled": True,
                "knownService": "vpnServer"
            }
        ]
    })
    config = load_config_directory(temp_config_dir)
    assert config.plugins[0].known_services == ["vpnServer"]

    # 3. Plural key name with list of string values (camelCase)
    write_yaml(temp_config_dir, "plugins.yaml", {
        "plugins": [
            {
                "id": "technitium-dns",
                "name": "Technitium DNS",
                "enabled": True,
                "knownServices": ["dnsServer", "dnsFilter"]
            }
        ]
    })
    config = load_config_directory(temp_config_dir)
    assert config.plugins[0].known_services == ["dnsServer", "dnsFilter"]

    # 4. Plural key name with list of string values (snake_case) and duplicates/mixed keys
    write_yaml(temp_config_dir, "plugins.yaml", {
        "plugins": [
            {
                "id": "technitium-dns",
                "name": "Technitium DNS",
                "enabled": True,
                "known_services": ["dnsServer"],
                "knownService": "dnsFilter",
                "knownServices": ["dnsServer"]
            }
        ]
    })
    config = load_config_directory(temp_config_dir)
    # The deduplicated combined list
    assert set(config.plugins[0].known_services) == {"dnsServer", "dnsFilter"}


def test_input_rule_config_parsing(temp_config_dir):
    """Verifies that InputRuleConfig entries are correctly parsed from schedules.yaml."""
    config = load_config_directory(temp_config_dir)

    # The conftest fixture includes 2 rules
    assert len(config.firewall.rules) == 2

    ssh_rule = config.firewall.rules[0]
    assert ssh_rule.name == "Allow SSH from Internet"
    assert ssh_rule.interface == "eth0"
    assert ssh_rule.protocol == "tcp"
    assert ssh_rule.port == 22
    assert ssh_rule.action == "accept"
    assert ssh_rule.enabled is True
    assert ssh_rule.source is None

    disabled_rule = config.firewall.rules[1]
    assert disabled_rule.name == "Block HTTP on WAN"
    assert disabled_rule.enabled is False
    assert disabled_rule.action == "drop"


def test_input_rule_protocol_validation():
    """Verifies InputRuleConfig rejects invalid protocol values."""
    from roostos_engine.config import InputRuleConfig

    # Valid protocols
    r = InputRuleConfig(name="test", port=22, protocol="tcp")
    assert r.protocol == "tcp"

    r = InputRuleConfig(name="test", port=22, protocol="udp")
    assert r.protocol == "udp"

    r = InputRuleConfig(name="test", port=22, protocol="tcp/udp")
    assert r.protocol == "tcp/udp"

    # Invalid protocol
    with pytest.raises(ValueError, match="protocol must be"):
        InputRuleConfig(name="test", port=22, protocol="icmp")


def test_input_rule_action_validation():
    """Verifies InputRuleConfig rejects invalid action values."""
    from roostos_engine.config import InputRuleConfig

    with pytest.raises(ValueError, match="action must be"):
        InputRuleConfig(name="test", port=22, action="reject")
