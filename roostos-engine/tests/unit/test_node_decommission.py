import os
import json
import pytest
from unittest.mock import MagicMock

from roostos_engine.models.node import NodeConfig, NodeRole
from roostos_engine.models.system import SystemSettings, ClusterSettingsConfig
from roostos_engine.models.network import NetworkSettings
from roostos_engine.repository import ConfigRepository
from roostos_engine.cluster_manager import ClusterManager
from roostos_engine.node_decommission import decommission_cluster_node, leave_cluster_locally


class MockRepo(ConfigRepository):
    def __init__(self, tmp_path):
        super().__init__()
        self.config_dir = str(tmp_path)
        self.config = MagicMock()
        self.config.system = SystemSettings(
            hostname="roost-primary",
            cluster=ClusterSettingsConfig(node_id="node-01", controller_url="https://controller.local:8443", epoch=2)
        )
        fake_bridge = MagicMock()
        fake_bridge.name = "br-lan"
        fake_bridge.ha_standby_node = "node-02"
        self.config.network = MagicMock()
        self.config.network.bridges = [fake_bridge]
        self.config.network.vlans = []
        self.config.network.edge_gateways = []
        self.config.nodes = [
            NodeConfig(id="node-01", name="Primary Router", roles=[NodeRole.CONTROLLER, NodeRole.GATEWAY_ROUTER]),
            NodeConfig(id="node-02", name="Worker Node 2", roles=[NodeRole.GATEWAY_ROUTER], management_ip="192.168.1.20"),
        ]

    def get_config(self):
        return self.config

    def save_system_config(self, data):
        self.config.system = data

    def save_nodes_config(self, data):
        self.config.nodes = data.nodes

    def save_network_config(self, data):
        self.config.network = data

    def save_devices_config(self, data): pass
    def save_schedules_config(self, data): pass
    def save_firewall_config(self, data): pass
    def save_plugins_config(self, data): pass


def test_decommission_cluster_node(tmp_path):
    repo = MockRepo(tmp_path)
    cm = ClusterManager(config_dir=str(tmp_path), mock=True)
    cm.record_heartbeat("node-02", {"status": "healthy"})

    # Setup fake service certificates for node-02
    node_cert_dir = tmp_path / "certs" / "services" / "node-node-02"
    node_cert_dir.mkdir(parents=True)
    (node_cert_dir / "client.crt").write_text("FAKE_CERT")
    (node_cert_dir / "client.key").write_text("FAKE_KEY")

    res = decommission_cluster_node(repo, "node-02", cluster_manager=cm)

    assert res.success is True
    assert res.node_id == "node-02"
    assert res.credentials_invalidated is True
    assert any("node-02" in c for c in res.certs_removed)
    assert not os.path.exists(node_cert_dir)

    # Check revoked_nodes.json
    revoked_file = tmp_path / "certs" / "revoked_nodes.json"
    assert revoked_file.exists()
    revoked_data = json.loads(revoked_file.read_text())
    assert any(r["node_id"] == "node-02" for r in revoked_data)

    # Check DHCP standby rebalanced
    assert any("br-lan" in s for s in res.dhcp_rebalanced)
    assert repo.config.network.bridges[0].ha_standby_node == "none"

    # Check inventory updated
    assert len(repo.config.nodes) == 1
    assert repo.config.nodes[0].id == "node-01"

    # Check heartbeat purged
    assert cm.get_node_heartbeat("node-02") is None


def test_decommission_nonexistent_node(tmp_path):
    repo = MockRepo(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        decommission_cluster_node(repo, "node-999")


def test_leave_cluster_locally(tmp_path):
    repo = MockRepo(tmp_path)
    cm = ClusterManager(config_dir=str(tmp_path), mock=True)

    # Setup fake local client certificate
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir(parents=True)
    (certs_dir / "client.crt").write_text("LOCAL_CLIENT_CERT")
    (certs_dir / "client.key").write_text("LOCAL_CLIENT_KEY")

    res = leave_cluster_locally(repo, cluster_manager=cm, notify_controller=False)

    assert res.success is True
    assert res.is_self is True
    assert res.credentials_invalidated is True

    # Check client cert deleted
    assert not (certs_dir / "client.crt").exists()
    assert not (certs_dir / "client.key").exists()

    # Check cluster settings reset
    assert repo.config.system.cluster.controller_url is None
    assert repo.config.system.cluster.epoch == 1

    # Check local node roles reset to standalone
    assert len(repo.config.nodes) == 1
    assert repo.config.nodes[0].id == "node-01"
    assert repo.config.nodes[0].roles == [NodeRole.GATEWAY_ROUTER]
