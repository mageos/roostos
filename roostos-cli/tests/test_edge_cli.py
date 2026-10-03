import os
import tempfile
import yaml
from click.testing import CliRunner

from roostos_cli.models import NodeRole, EdgeGatewayConfigParams
from roostos_cli.wizard import SetupWizard
from roostos_cli.main import cli


def test_wizard_setup_edge_gateway():
    """Verifies setup wizard configures Edge Gateway role on a VPS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wizard = SetupWizard(config_dir=tmpdir, mock_install=True)
        params = EdgeGatewayConfigParams(wan_interface="eth0")
        res = wizard.run_setup(role=NodeRole.EDGE_GATEWAY, edge_params=params)

        assert res.success is True
        assert res.role == NodeRole.EDGE_GATEWAY
        assert "wireguard" in res.installed_packages

        # Verify system.yaml
        sys_path = os.path.join(tmpdir, "system.yaml")
        assert os.path.exists(sys_path)
        with open(sys_path, "r") as f:
            sys_data = yaml.safe_load(f)
        assert "edge_gateway" in sys_data["system"]["cluster"]["roles"]

        # Verify network.yaml
        net_path = os.path.join(tmpdir, "network.yaml")
        assert os.path.exists(net_path)
        with open(net_path, "r") as f:
            net_data = yaml.safe_load(f)
        assert net_data["network"]["interfaces"][0]["name"] == "eth0"
        assert net_data["network"]["interfaces"][0]["role"] == "wan"


def test_edge_token_cli_command():
    """Verifies 'roostos edge token' command generates a valid bootstrap token."""
    runner = CliRunner()
    result = runner.invoke(cli, ["edge", "token", "--ip", "198.51.100.5", "--port", "8000"])
    assert result.exit_code == 0
    assert "roost-edge://198.51.100.5:8000?token=" in result.output
    assert "RoostOS Edge Gateway Bootstrap Token" in result.output


def test_edge_lockdown_cli_command():
    """Verifies 'roostos edge lockdown' command outputs firewall rule."""
    runner = CliRunner()
    result = runner.invoke(cli, ["edge", "lockdown", "--wan", "eth0"])
    assert result.exit_code == 0
    assert "tcp dport 8000 drop" in result.output
    assert "restricted to internal WireGuard tunnel" in result.output


def test_edge_status_cli_unlinked():
    """Verifies 'roostos edge status' displays unlinked message when no gateway configured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()
        result = runner.invoke(cli, ["edge", "status", "--config-dir", tmpdir])
        assert result.exit_code == 0
        assert "No Edge Gateway currently linked" in result.output
