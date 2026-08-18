import os
import yaml
import pytest
from pydantic import ValidationError
from roostos_engine.config import load_config_directory
from roostos_engine.firewall_manager import FirewallManager

def test_vpn_gateway_config_validation(tmp_path):
    """Verifies that gateway configuration schemas and linkage checks function correctly."""
    # 1. Write basic configurations
    with open(tmp_path / "system.yaml", "w") as f:
        yaml.safe_dump({"system": {"hostname": "vpn-router", "timezone": "UTC"}}, f)
        
    with open(tmp_path / "schedules.yaml", "w") as f:
        yaml.safe_dump({"firewall": {}}, f)
        
    with open(tmp_path / "plugins.yaml", "w") as f:
        yaml.safe_dump({"plugins": []}, f)

    # 2. Write network.yaml defining a default and VPN gateway
    with open(tmp_path / "network.yaml", "w") as f:
        yaml.safe_dump({
            "network": {
                "interfaces": [{"name": "eth0", "role": "wan"}],
                "bridges": [{"name": "br0", "ip": "192.168.1.1/24"}],
                "gateways": [
                    {"id": "default", "name": "Default ISP", "interface": "eth0"},
                    {"id": "vpn_east", "name": "NordVPN East", "interface": "wg0", "type": "wireguard"}
                ]
            }
        }, f)

    # 3. Write valid devices.yaml setting a valid gateway override
    with open(tmp_path / "devices.yaml", "w") as f:
        yaml.safe_dump({
            "devices": [
                {"mac": "a4:83:e7:12:34:56", "name": "Mom's TV", "gateway": "vpn_east"}
            ]
        }, f)

    # Validate load matches
    config = load_config_directory(str(tmp_path))
    assert len(config.network.gateways) == 2
    assert config.network.gateways[1].id == "vpn_east"
    assert config.devices[0].gateway == "vpn_east"

    # 4. Write INVALID devices.yaml referencing a missing gateway ID
    with open(tmp_path / "devices.yaml", "w") as f:
        yaml.safe_dump({
            "devices": [
                {"mac": "a4:83:e7:12:34:56", "name": "Mom's TV", "gateway": "missing_vpn"}
            ]
        }, f)

    # Expect cross-reference validation to throw ValidationError
    with pytest.raises(ValidationError) as exc:
        load_config_directory(str(tmp_path))
    assert "references non-existent gateway ID 'missing_vpn'" in str(exc.value)


def test_vpn_firewall_and_pbr_compilation(tmp_path):
    """Verifies compiled rulesets stamp packet marks and masquerade VPN interfaces."""
    with open(tmp_path / "system.yaml", "w") as f:
        yaml.safe_dump({"system": {"hostname": "vpn-router", "timezone": "UTC"}}, f)
    with open(tmp_path / "schedules.yaml", "w") as f:
        yaml.safe_dump({"firewall": {}}, f)
    with open(tmp_path / "plugins.yaml", "w") as f:
        yaml.safe_dump({"plugins": []}, f)
        
    with open(tmp_path / "network.yaml", "w") as f:
        yaml.safe_dump({
            "network": {
                "interfaces": [{"name": "eth0", "role": "wan"}],
                "bridges": [{"name": "br0", "ip": "192.168.1.1/24"}],
                "gateways": [
                    {"id": "default", "name": "Default ISP", "interface": "eth0"},
                    {"id": "vpn_us", "name": "NordVPN", "interface": "wg0", "type": "wireguard"}
                ]
            }
        }, f)

    with open(tmp_path / "devices.yaml", "w") as f:
        yaml.safe_dump({
            "devices": [
                {"mac": "a4:83:e7:12:34:56", "name": "Mom's TV", "gateway": "vpn_us"}
            ]
        }, f)

    config = load_config_directory(str(tmp_path))
    manager = FirewallManager(config)
    
    rules = manager.compile_ruleset()
    
    # Assert packet mark assignment generated in NAT prerouting
    assert "ether saddr a4:83:e7:12:34:56 meta mark set 100" in rules
    
    # Assert masquerade generated for WAN (eth0) and VPN interface (wg0)
    assert 'oifname "eth0" masquerade' in rules
    assert 'oifname "wg0" masquerade' in rules

    # Assert compiled setup system commands generated
    cmds = manager.compile_routing_setup_cmds()
    assert len(cmds) == 2
    assert cmds[0] == ["ip", "route", "replace", "default", "dev", "wg0", "table", "100"]
    assert cmds[1] == ["ip", "rule", "add", "fwmark", "100", "table", "100"]
