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


def test_edge_token_cli_wireguard_command():
    """Verifies default 'roostos edge token' command generates a WireGuard invite token."""
    runner = CliRunner()
    result = runner.invoke(cli, ["edge", "token", "--ip", "198.51.100.5", "--port", "51820"])
    assert result.exit_code == 0
    assert "roost-edge-wg://" in result.output
    assert "RoostOS WireGuard Edge Gateway Invitation" in result.output


def test_edge_token_cli_legacy_http_command():
    """Verifies 'roostos edge token --legacy-http' command generates legacy HTTP token."""
    runner = CliRunner()
    result = runner.invoke(cli, ["edge", "token", "--legacy-http", "--ip", "198.51.100.5", "--port", "8000"])
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


def test_edge_token_cli_persists_legacy_token(monkeypatch, tmp_path):
    """Verifies legacy HTTP token generation persists token for EdgeManager validation."""
    token_file = str(tmp_path / "edge_tokens.json")
    monkeypatch.setenv("ROOSTOS_EDGE_TOKENS_FILE", token_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["edge", "token", "--legacy-http", "--ip", "3.135.219.253", "--port", "8000"])
    assert result.exit_code == 0
    assert "roost-edge://3.135.219.253:8000?token=" in result.output

    # Extract raw JWT from command output
    raw_token = result.output.split("?token=")[1].split()[0].strip()

    # Validate using a separate EdgeManager instance
    from roostos_engine.edge_manager import EdgeManager
    mgr = EdgeManager(state_file=token_file)
    claims = mgr.validate_and_consume_token(raw_token)
    assert claims["vps_ip"] == "3.135.219.253"
    assert claims["role"] == "edge_bootstrap"


def test_edge_token_cli_export_and_connect(tmp_path):
    """Verifies exporting invite bundle to file and connecting via CLI with --file and --token."""
    export_file = str(tmp_path / "roost-edge.json")
    config_dir = str(tmp_path / "config")
    os.makedirs(config_dir, exist_ok=True)

    runner = CliRunner()
    # 1. Export bundle
    res_export = runner.invoke(cli, ["edge", "token", "--ip", "198.51.100.5", "--port", "51820", "--export", export_file])
    assert res_export.exit_code == 0
    assert os.path.exists(export_file)

    # 2. Connect via --file
    res_conn = runner.invoke(cli, ["edge", "connect", "--file", export_file, "--config-dir", config_dir, "--mock"])
    assert res_conn.exit_code == 0
    assert "Edge Gateway tunnel established" in res_conn.output

    # 3. Connect via --token (wireguard token)
    wg_token = [line for line in res_export.output.splitlines() if line.startswith("roost-edge-wg://")][0]
    res_token_conn = runner.invoke(cli, ["edge", "connect", "--token", wg_token, "--config-dir", config_dir, "--mock"])
    assert res_token_conn.exit_code == 0
    assert "Zero public web API calls made" in res_token_conn.output

