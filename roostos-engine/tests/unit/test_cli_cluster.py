import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock

from roostos_engine.cli import main
from roostos_engine.models.node import NodeConfig, NodeRole
from roostos_engine.models.system import SystemSettings, ClusterSettingsConfig
from roostos_engine.repository import YAMLConfigRepository


def test_cli_cluster_help():
    runner = CliRunner()
    res = runner.invoke(main, ["cluster", "--help"])
    assert res.exit_code == 0
    assert "leave" in res.output
    assert "remove-node" in res.output
    assert "status" in res.output


def test_cli_cluster_leave_aborted():
    runner = CliRunner()
    res = runner.invoke(main, ["cluster", "leave"], input="n\n")
    assert res.exit_code == 0
    assert "Aborted" in res.output


def test_cli_cluster_remove_node_aborted():
    runner = CliRunner()
    res = runner.invoke(main, ["cluster", "remove-node", "node-02"], input="n\n")
    assert res.exit_code == 0
    assert "Aborted" in res.output


def test_cli_cluster_remove_node_yes(tmp_path):
    # Initialize a YAML repo with nodes.yaml and system.yaml
    repo = YAMLConfigRepository(str(tmp_path))
    from roostos_engine.models.node import NodesConfigFile
    from roostos_engine.models.system import SystemConfig
    from roostos_engine.models.network import NetworkConfig, NetworkSettings

    repo.save_system_config(SystemConfig(system=SystemSettings(hostname="router-01")))
    repo.save_network_config(NetworkConfig(network=NetworkSettings(bridges=[])))
    repo.save_nodes_config(NodesConfigFile(nodes=[
        NodeConfig(id="node-01", name="Primary Router", roles=[NodeRole.GATEWAY_ROUTER]),
        NodeConfig(id="node-02", name="Failing Worker", roles=[NodeRole.GATEWAY_ROUTER])
    ]))

    runner = CliRunner()
    res = runner.invoke(main, ["cluster", "remove-node", "node-02", "--config-dir", str(tmp_path), "--yes"])
    assert res.exit_code == 0
    assert "successfully decommissioned" in res.output

    # Verify node-02 was removed from YAML
    updated_cfg = repo.get_config()
    assert len(updated_cfg.nodes) == 1
    assert updated_cfg.nodes[0].id == "node-01"


def test_cli_cluster_leave_yes(tmp_path):
    repo = YAMLConfigRepository(str(tmp_path))
    from roostos_engine.models.node import NodesConfigFile
    from roostos_engine.models.system import SystemConfig
    from roostos_engine.models.network import NetworkConfig, NetworkSettings

    repo.save_system_config(SystemConfig(system=SystemSettings(
        hostname="worker-02",
        cluster=ClusterSettingsConfig(node_id="node-02", controller_url="https://master:8443", epoch=3)
    )))
    repo.save_network_config(NetworkConfig(network=NetworkSettings(bridges=[])))
    repo.save_nodes_config(NodesConfigFile(nodes=[
        NodeConfig(id="node-02", name="Worker 2", roles=[NodeRole.GATEWAY_ROUTER])
    ]))

    runner = CliRunner()
    res = runner.invoke(main, ["cluster", "leave", "--config-dir", str(tmp_path), "--yes", "--no-notify"])
    assert res.exit_code == 0
    assert "left the cluster" in res.output

    updated_cfg = repo.get_config()
    assert updated_cfg.system.cluster.controller_url is None
    assert updated_cfg.system.cluster.epoch == 1
