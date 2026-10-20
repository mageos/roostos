"""Unit tests for RoostOS Healthcheck and Orphaned Records CLI commands."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from roostos_engine.cli import main
from roostos_engine.models.node import NodeConfig, NodeRole, NodesConfigFile
from roostos_engine.models.system import SystemConfig, SystemSettings, ClusterSettingsConfig
from roostos_engine.models.network import NetworkConfig, NetworkSettings, NetworkBridge
from roostos_engine.models.devices import DevicesConfig
from roostos_engine.repository import YAMLConfigRepository


@pytest.fixture
def health_repo_env(tmp_path: Path):
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
    ]))
    repo.save_network_config(NetworkConfig(network=NetworkSettings(bridges=[
        NetworkBridge(name="br-lan", ip="192.168.1.1/24", ha_standby_node="none")
    ])))
    repo.save_devices_config(DevicesConfig(devices=[], people=[], buildings=[], rooms=[]))

    return repo, config_dir


def test_cli_healthcheck_help():
    runner = CliRunner()
    res = runner.invoke(main, ["healthcheck", "--help"])
    assert res.exit_code == 0
    assert "--fix" in res.output
    assert "--mqtt" in res.output


def test_cli_cluster_healthcheck_help():
    runner = CliRunner()
    res = runner.invoke(main, ["cluster", "healthcheck", "--help"])
    assert res.exit_code == 0
    assert "--fix" in res.output
    assert "--mqtt" in res.output


def test_cli_healthcheck_clean_state(health_repo_env):
    repo, config_dir = health_repo_env
    runner = CliRunner()
    res = runner.invoke(main, ["healthcheck", "--config-dir", str(config_dir)])
    assert res.exit_code == 0
    assert "Overall Status:" in res.output
    assert "No orphaned records detected" in res.output


def test_cli_healthcheck_detects_and_fixes_orphans(health_repo_env):
    repo, config_dir = health_repo_env
    orphan_cert = config_dir / "certs" / "services" / "node-abandoned"
    orphan_cert.mkdir(parents=True, exist_ok=True)

    net = repo.get_config().network
    net.bridges[0].ha_standby_node = "node-abandoned"
    repo.save_network_config(NetworkConfig(network=net))

    runner = CliRunner()
    # 1. Run without --fix
    res1 = runner.invoke(main, ["healthcheck", "--config-dir", str(config_dir)])
    assert res1.exit_code == 0
    assert "Orphaned Record(s) Found" in res1.output
    assert "node-abandoned" in res1.output
    assert orphan_cert.exists()

    # 2. Run with --fix
    res2 = runner.invoke(main, ["healthcheck", "--config-dir", str(config_dir), "--fix"])
    assert res2.exit_code == 0
    assert "Executing automatic cleanup" in res2.output
    assert "Purged:" in res2.output
    assert not orphan_cert.exists()

    # 3. Subsequent check is clean
    res3 = runner.invoke(main, ["cluster", "healthcheck", "--config-dir", str(config_dir)])
    assert res3.exit_code == 0
    assert "No orphaned records detected" in res3.output
