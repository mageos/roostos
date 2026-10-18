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

    # 4. Verify roostos edge status displays linked gateway
    res_status = runner.invoke(cli, ["edge", "status", "--config-dir", config_dir])
    assert res_status.exit_code == 0
    assert "Gateway ID:     edge-01" in res_status.output
    assert "Public IP:      198.51.100.5" in res_status.output
    assert "Tunnel:         10.42.0.2/24 -> 10.42.0.1/24" in res_status.output
    assert "Status:         connected" in res_status.output


def test_edge_status_cli_fallback_to_nodes_yaml(tmp_path):
    """Verifies roostos edge status falls back to nodes.yaml if network.yaml has no edge gateways."""
    config_dir = str(tmp_path / "config")
    os.makedirs(config_dir, exist_ok=True)
    import yaml
    nodes_file = os.path.join(config_dir, "nodes.yaml")
    with open(nodes_file, "w") as f:
        yaml.dump({
            "nodes": [
                {
                    "id": "node-vps-99",
                    "name": "VPS Gateway Node",
                    "roles": ["edge_gateway"],
                    "management_ip": "203.0.113.88",
                    "status": "active",
                }
            ]
        }, f)

    runner = CliRunner()
    res_status = runner.invoke(cli, ["edge", "status", "--config-dir", config_dir])
    assert res_status.exit_code == 0
    assert "Gateway ID:     node-vps-99" in res_status.output
    assert "Public IP:      203.0.113.88" in res_status.output
    assert "Status:         connected (Cluster Node)" in res_status.output


def test_edge_token_cli_with_domain():
    """Verifies generating invite bundle with domain name instead of IP."""
    runner = CliRunner()
    res = runner.invoke(cli, ["edge", "token", "--domain", "vps.roostos.net", "--port", "51820"])
    assert res.exit_code == 0
    assert "vps.roostos.net:51820" in res.output
    assert "roost-edge-wg://" in res.output


def test_edge_update_cli(tmp_path, monkeypatch):
    """Verifies roostos edge update updates both netdev Endpoint and network.yaml."""
    config_dir = str(tmp_path / "config")
    net_dir = str(tmp_path / "networkd")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(net_dir, exist_ok=True)
    monkeypatch.setenv("ROOSTOS_SYSTEMD_NETWORK_DIR", net_dir)

    netdev_path = os.path.join(net_dir, "50-wg-edge.netdev")
    with open(netdev_path, "w") as f:
        f.write("[NetDev]\nName=wg-edge\n\n[WireGuardPeer]\nPublicKey=testkey\nEndpoint=1.2.3.4:51820\n")

    import yaml
    with open(os.path.join(config_dir, "network.yaml"), "w") as f:
        yaml.dump({"edge_gateways": [{"id": "edge-01", "public_ip": "1.2.3.4", "listen_port": 51820}]}, f)

    runner = CliRunner()
    res = runner.invoke(cli, ["edge", "update", "--domain", "edge.roostos.cloud", "--port", "51820", "--config-dir", config_dir])
    assert res.exit_code == 0
    assert "Edge Gateway WireGuard endpoint updated to edge.roostos.cloud:51820" in res.output

    with open(netdev_path, "r") as f:
        updated_netdev = f.read()
    assert "Endpoint=edge.roostos.cloud:51820" in updated_netdev

    with open(os.path.join(config_dir, "network.yaml"), "r") as f:
        ydata = yaml.safe_load(f)
    assert ydata["edge_gateways"][0]["domain"] == "edge.roostos.cloud"


def test_edge_sync_routes_and_verify_cli(tmp_path):
    """Verifies 'roostos edge sync-routes' and 'roostos edge verify' CLI commands."""
    config_dir = str(tmp_path / "config")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "network.yaml"), "w") as f:
        yaml.dump({
            "bridges": [{"name": "br0", "ip": "192.168.10.1/24", "isolate": False}],
            "edge_gateways": [{"id": "edge-01", "public_ip": "198.51.100.5", "listen_port": 51820}],
        }, f)

    runner = CliRunner()
    res_sync = runner.invoke(cli, ["edge", "sync-routes", "--config-dir", config_dir, "--mock"])
    assert res_sync.exit_code == 0
    assert "192.168.10.0/24" in res_sync.output

    res_verify = runner.invoke(cli, ["edge", "verify", "--config-dir", config_dir, "--mock"])
    assert res_verify.exit_code == 0
    assert "HEALTHY" in res_verify.output
    assert "192.168.10.0/24" in res_verify.output


def test_firewall_and_networkd_bidirectional_lan_edge_routing(tmp_path, monkeypatch):
    """Verifies FirewallManager and EdgeManager generate bidirectional LAN <-> wg-edge routing rules."""
    from roostos_engine.config import load_config_directory
    from roostos_engine.firewall_manager import FirewallManager
    from roostos_engine.edge_manager import EdgeManager

    config_dir = str(tmp_path / "config")
    net_dir = str(tmp_path / "networkd")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(net_dir, exist_ok=True)
    monkeypatch.setenv("ROOSTOS_SYSTEMD_NETWORK_DIR", net_dir)

    with open(os.path.join(config_dir, "network.yaml"), "w") as f:
        yaml.dump({
            "interfaces": [{"name": "eth0", "role": "wan", "mode": "dhcp"}],
            "bridges": [{"name": "br0", "interfaces": ["eth1"], "ip": "192.168.1.1/24", "isolate": False}],
        }, f)

    cfg = load_config_directory(config_dir)
    ruleset = FirewallManager(cfg).compile_ruleset()
    assert 'iifname "br0" oifname "wg-edge" accept' in ruleset
    assert 'iifname "wg-edge" oifname "br0" accept' in ruleset
    assert 'iifname "wg-edge" tcp dport { 22, 443, 8000, 9090, 53 } accept' in ruleset

    mgr = EdgeManager(config_dir=config_dir, mock=False)
    gw_files = mgr.generate_networkd_config(
        role="gateway", private_key="priv", peer_public_key="pub",
        allowed_ips="10.42.0.2/32,192.168.1.0/24", routed_subnets=["192.168.1.0/24"],
    )
    assert "AllowedIPs=10.42.0.2/32,192.168.1.0/24" in gw_files["50-wg-edge.netdev"]
    assert "IPForward=yes" in gw_files["50-wg-edge.network"]
    assert "Destination=192.168.1.0/24" in gw_files["50-wg-edge.network"]



