import os
import pytest
import yaml
from click.testing import CliRunner
from roostos_engine.setup_tool import main
from roostos_engine.config import load_config_directory

@pytest.fixture
def mock_dialogs(monkeypatch):
    class MockDialogRunner:
        def __init__(self, value_to_return):
            self.value_to_return = value_to_return
        def run(self):
            return self.value_to_return

    class MockDialogsImpl:
        def __init__(self, inputs_list):
            self.inputs = list(inputs_list)
            import roostos_engine.setup_tool
            monkeypatch.setattr(roostos_engine.setup_tool, "button_dialog", self.button_dialog)
            monkeypatch.setattr(roostos_engine.setup_tool, "yes_no_dialog", self.yes_no_dialog)
            monkeypatch.setattr(roostos_engine.setup_tool, "input_dialog", self.input_dialog)
            monkeypatch.setattr(roostos_engine.setup_tool, "radiolist_dialog", self.radiolist_dialog)
            monkeypatch.setattr(roostos_engine.setup_tool, "checkboxlist_dialog", self.checkboxlist_dialog)
            monkeypatch.setattr(roostos_engine.setup_tool, "message_dialog", self.message_dialog)

        def _next_input(self):
            if not self.inputs:
                raise IndexError("MockDialogs ran out of inputs!")
            return self.inputs.pop(0)

        def button_dialog(self, title, text, buttons):
            val = self._next_input()
            return MockDialogRunner(val)

        def yes_no_dialog(self, title, text):
            val = self._next_input()
            if isinstance(val, str):
                val = val.lower() in ("y", "yes", "true", "1")
            return MockDialogRunner(val)

        def input_dialog(self, title, text, default=""):
            val = self._next_input()
            if val == "":
                return MockDialogRunner(default)
            return MockDialogRunner(val)

        def radiolist_dialog(self, title, text, values, default=None):
            val = self._next_input()
            if val == "":
                return MockDialogRunner(default)
            return MockDialogRunner(val)

        def checkboxlist_dialog(self, title, text, values, default_values=None):
            val = self._next_input()
            if val == "":
                return MockDialogRunner(default_values or [])
            if isinstance(val, str):
                return MockDialogRunner([x.strip() for x in val.split(",") if x.strip()])
            return MockDialogRunner(val)

        def message_dialog(self, title, text):
            return MockDialogRunner(None)

    return MockDialogsImpl


def test_setup_tool_dhcp_flow(temp_config_dir, monkeypatch, mock_dialogs):
    """Test standard initial setup wizard flow with DHCP WAN configuration."""
    # Mock list_interfaces to return deterministic values
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1", "eth2"])

    # Simulate inputs:
    inputs = [
        "rerun",         # Choice for existing config
        "",              # WAN interface (defaults to eth0)
        "dhcp",          # WAN protocol
        "y",             # IPv6 enabled
        "eth1,eth2",     # LAN interfaces
        "",              # LAN network (default: 192.168.1.0/24)
        "",              # LAN IP (default: 192.168.1.1)
        "y",             # Enable DHCP
        "y",             # Confirm default DHCP pool range
        "y",             # Wireless support enabled
        "",              # Upstream DNS (default: 1.1.1.1, 8.8.8.8)
        "n",             # Allow Web UI from WAN (no)
        "n",             # Allow SSH from WAN (no)
        "y"              # Apply config
    ]
    mock_dialogs(inputs)

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)])

    assert result.exit_code == 0
    assert "Selected WAN interface: eth0" in result.output
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


def test_setup_tool_static_flow(temp_config_dir, monkeypatch, mock_dialogs):
    """Test initial setup wizard flow with Static WAN and customized LAN range."""
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1"])

    # Simulate inputs:
    inputs = [
        "rerun",         # Choice for existing config
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
        "y",             # Wireless support enabled
        "8.8.4.4, 9.9.9.9",
        "n",             # Allow Web UI from WAN (no)
        "n",             # Allow SSH from WAN (no)
        "y"
    ]
    mock_dialogs(inputs)
    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)])

    
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


def test_setup_tool_wan_access_prompts(temp_config_dir, monkeypatch, mock_dialogs):
    """Test that enabling WAN SSH and Web UI access creates firewall rules in schedules.yaml."""
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1"])

    # Simulate inputs: standard DHCP flow + enable both WAN SSH and Web UI
    inputs = [
        "rerun",         # Choice for existing config
        "",              # WAN interface (defaults to eth0)
        "dhcp",          # WAN protocol
        "y",             # IPv6 enabled
        "eth1",          # LAN interfaces
        "",              # LAN network (default: 192.168.1.0/24)
        "",              # LAN IP (default: 192.168.1.1)
        "y",             # Enable DHCP
        "y",             # Confirm default DHCP pool range
        "y",             # Wireless support enabled
        "",              # Upstream DNS (default: 1.1.1.1, 8.8.8.8)
        "y",             # Allow Web UI from WAN
        "y",             # Allow SSH from WAN
        "y"              # Apply config
    ]
    mock_dialogs(inputs)

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)])

    if result.exit_code != 0:
        print("Test failed! Output was:")
        print(result.output)
        if result.exception:
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

    assert result.exit_code == 0

    # Load updated configurations and verify firewall rules in schedules.yaml
    config = load_config_directory(str(temp_config_dir))

    # Find the WAN access rules
    rule_names = [r.name for r in config.firewall.rules]
    assert "WAN SSH Access" in rule_names
    assert "WAN Web UI Access" in rule_names

    ssh_rule = next(r for r in config.firewall.rules if r.name == "WAN SSH Access")
    assert ssh_rule.interface == "eth0"
    assert ssh_rule.protocol == "tcp"
    assert ssh_rule.port == 22
    assert ssh_rule.action == "accept"
    assert ssh_rule.enabled is True

    web_rule = next(r for r in config.firewall.rules if r.name == "WAN Web UI Access")
    assert web_rule.interface == "eth0"
    assert web_rule.protocol == "tcp"
    assert web_rule.port == 8000
    assert web_rule.action == "accept"
    assert web_rule.enabled is True

    # Verify the original schedules (from conftest) are preserved
    assert len(config.schedules) > 0  # Kids Bedtime Block should still exist


def test_setup_tool_existing_config_exit(temp_config_dir, monkeypatch, mock_dialogs):
    """Test that if config files already exist, the tool prompts and exits if requested."""
    # Write a dummy config file
    config_file = os.path.join(str(temp_config_dir), "system.yaml")
    with open(config_file, "w") as f:
        f.write("system:\n  hostname: roost-router-test\n")

    # Inputs:
    # 1. Choose "use_existing" -> exits
    inputs = ["use_existing"]
    mock_dialogs(inputs)

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)])

    assert result.exit_code == 0
    assert "Using existing configuration. Exiting." in result.output


def test_setup_tool_existing_config_rerun(temp_config_dir, monkeypatch, mock_dialogs):
    """Test that if config files already exist, the tool re-runs setup if requested."""
    # Write a dummy config file
    config_file = os.path.join(str(temp_config_dir), "system.yaml")
    with open(config_file, "w") as f:
        f.write("system:\n  hostname: roost-router-test\n")

    # Mock list_interfaces to return deterministic values
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1", "eth2"])

    # Inputs:
    # 1. Existing config prompt -> "rerun"
    # 2. Select WAN interface -> default
    # 3. Configure WAN -> dhcp
    # 4. Enable IPv6 -> y
    # ...
    inputs = [
        "rerun",         # Existing config choice
        "",              # WAN interface (defaults to eth0)
        "dhcp",          # WAN protocol
        "y",             # IPv6 enabled
        "eth1,eth2",     # LAN interfaces
        "",              # LAN network (default: 192.168.1.0/24)
        "",              # LAN IP (default: 192.168.1.1)
        "y",             # Enable DHCP
        "y",             # Confirm default DHCP pool range
        "y",             # Wireless support enabled
        "",              # Upstream DNS (default: 1.1.1.1, 8.8.8.8)
        "n",             # Allow Web UI from WAN (no)
        "n",             # Allow SSH from WAN (no)
        "y"              # Apply config
    ]
    mock_dialogs(inputs)

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)])

    assert result.exit_code == 0
    assert "Configuration files written successfully" in result.output


def test_setup_tool_wifi_disabled(temp_config_dir, monkeypatch, mock_dialogs):
    """Test setup wizard flow when wireless/WiFi support is explicitly disabled."""
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1"])

    inputs = [
        "rerun",         # Choice for existing config
        "",              # WAN interface (defaults to eth0)
        "dhcp",          # WAN protocol
        "y",             # IPv6 enabled
        "eth1",          # LAN interfaces
        "",              # LAN network (default: 192.168.1.0/24)
        "",              # LAN IP (default: 192.168.1.1)
        "y",             # Enable DHCP
        "y",             # Confirm default DHCP pool range
        "n",             # Wireless support DISABLED
        "",              # Upstream DNS (default: 1.1.1.1, 8.8.8.8)
        "n",             # Allow Web UI from WAN (no)
        "n",             # Allow SSH from WAN (no)
        "y"              # Apply config
    ]
    mock_dialogs(inputs)

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir)])

    assert result.exit_code == 0
    assert "Configuration files written successfully" in result.output

    # Load updated configurations and verify wifi is None
    config = load_config_directory(str(temp_config_dir))
    assert config.wifi is None


def test_setup_tool_mdns_discovery(temp_config_dir, monkeypatch, mock_dialogs):
    """Test setup wizard with --discover flag triggering mDNS controller discovery."""
    import roostos_engine.setup_tool
    monkeypatch.setattr(roostos_engine.setup_tool, "list_interfaces", lambda: ["eth0", "eth1"])
    monkeypatch.setenv("ROOSTOS_MOCK_DISCOVERY", "1")

    inputs = [
        "rerun",
        "",
        "dhcp",
        "y",
        "eth1",
        "",
        "",
        "y",
        "y",
        "n",
        "",
        "n",
        "n",
        "y"
    ]
    mock_dialogs(inputs)

    runner = CliRunner()
    result = runner.invoke(main, ["--dir", str(temp_config_dir), "--discover"])

    assert result.exit_code == 0
    assert "RoostOS Cluster Controller Discovery" in result.output
    assert "Discovered 1 active controller(s)" in result.output


