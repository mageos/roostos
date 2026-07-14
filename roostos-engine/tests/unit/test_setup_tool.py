import os
import pytest
import yaml
from click.testing import CliRunner
from roostos_engine.setup_tool import main
from roostos_engine.config import load_config_directory

def test_setup_tool_dhcp_flow(temp_config_dir, monkeypatch):
    """Test standard initial setup wizard flow with DHCP WAN configuration."""
    # Mock list_interfaces to return deterministic values
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1", "eth2"])

    # Simulate inputs:
    # 1. Select WAN interface (select "eth0" or enter) -> \n
    # 2. Configure WAN: "dhcp" -> \n
    # 3. Enable IPv6: "y" -> y\n
    # 4. Select LAN interface(s): "eth1, eth2" -> eth1,eth2\n
    # 5. LAN default network: enter -> \n
    # 6. LAN IP: enter -> \n
    # 7. DHCP server on LAN: enter -> \n
    # 8. Use default DHCP pool: enter -> \n
    # 9. Upstream DNS: enter -> \n
    # 10. Write & apply settings: "y" -> y\n
    inputs = [
        "",              # WAN interface (defaults to eth0)
        "dhcp",          # WAN protocol
        "y",             # IPv6 enabled
        "eth1,eth2",     # LAN interfaces
        "",              # LAN network (default: 192.168.1.0/24)
        "",              # LAN IP (default: 192.168.1.1)
        "y",             # Enable DHCP
        "y",             # Confirm default DHCP pool range
        "",              # Upstream DNS (default: 1.1.1.1, 8.8.8.8)
        "y"              # Apply config
    ]
    input_str = "\n".join(inputs) + "\n"

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)], input=input_str)

    assert result.exit_code == 0
    assert "Configuration Summary" in result.output
    assert "Configuration files written successfully" in result.output

    # Load updated configurations and verify values
    config = load_config_directory(str(temp_config_dir))
    
    # WAN
    wan_if = next(i for i in config.network.interfaces if i.role == "wan")
    assert wan_if.name == "eth0"
    assert wan_if.dhcp is True
    assert wan_if.ipv6 is True

    # LAN
    lan_ifs = [i.name for i in config.network.interfaces if i.role == "lan"]
    assert sorted(lan_ifs) == ["eth1", "eth2"]
    for i in config.network.interfaces:
        if i.role == "lan":
            assert i.bridge == "br0"

    # Bridge & DHCP
    assert len(config.network.bridges) == 1
    br = config.network.bridges[0]
    assert br.name == "br0"
    assert br.ip == "192.168.1.1/24"
    assert br.dhcp_enabled is True
    assert br.dhcp_pool_start == "192.168.1.100"
    assert br.dhcp_pool_end == "192.168.1.250"

    # DNS
    assert config.system.dns.forwarders == ["1.1.1.1", "8.8.8.8"]


def test_setup_tool_static_flow(temp_config_dir, monkeypatch):
    """Test initial setup wizard flow with Static WAN and customized LAN range."""
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1"])

    # Simulate inputs:
    # 1. Select WAN interface (defaults to eth0) -> \n
    # 2. Configure WAN: "static" -> static\n
    # 3. WAN static IP/netmask: "10.0.0.5/24" -> 10.0.0.5/24\n
    # 4. WAN gateway: "10.0.0.1" -> 10.0.0.1\n
    # 5. Enable IPv6: "n" -> n\n
    # 6. Select LAN interface(s): "eth1" -> eth1\n
    # 7. LAN default network: "192.168.20.0/24" -> 192.168.20.0/24\n
    # 8. LAN IP: "192.168.20.254" -> 192.168.20.254\n
    # 9. DHCP server on LAN: "y" -> y\n
    # 10. Use default DHCP pool: "n" -> n\n
    # 11. DHCP pool start: "192.168.20.50" -> 192.168.20.50\n
    # 12. DHCP pool end: "192.168.20.150" -> 192.168.20.150\n
    # 13. Upstream DNS: "8.8.4.4, 9.9.9.9" -> 8.8.4.4, 9.9.9.9\n
    # 14. Write & apply settings: "y" -> y\n
    inputs = [
        "",
        "static",
        "n",
        "10.0.0.5/24",
        "10.0.0.1",
        "eth1",
        "192.168.20.0/24",
        "192.168.20.254",
        "y",
        "n",
        "192.168.20.50",
        "192.168.20.150",
        "8.8.4.4, 9.9.9.9",
        "y"
    ]
    input_str = "\n".join(inputs) + "\n"
    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)], input=input_str)
    
    if result.exit_code != 0:
        print("Test failed! Output was:")
        print(result.output)
        if result.exception:
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
            
    assert result.exit_code == 0

    # Load updated configs
    config = load_config_directory(str(temp_config_dir))

    # WAN Static Config checks
    wan_if = next(i for i in config.network.interfaces if i.role == "wan")
    assert wan_if.name == "eth0"
    assert wan_if.dhcp is False
    assert wan_if.ip == "10.0.0.5/24"
    assert wan_if.gateway == "10.0.0.1"
    assert wan_if.ipv6 is False

    # LAN Config checks
    lan_ifs = [i.name for i in config.network.interfaces if i.role == "lan"]
    assert lan_ifs == ["eth1"]
    
    br = config.network.bridges[0]
    assert br.ip == "192.168.20.254/24"
    assert br.dhcp_pool_start == "192.168.20.50"
    assert br.dhcp_pool_end == "192.168.20.150"

    # Upstream DNS
    assert config.system.dns.forwarders == ["8.8.4.4", "9.9.9.9"]
