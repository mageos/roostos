import pytest
import os
import tempfile
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from roostos_engine.cluster_manager import ClusterManager
from roostos_engine.cluster_sync import ClusterSyncAgent
from roostos_engine.models.node import NodeConfig, NodeRole, NodeInterface, InterfaceMode
from roostos_engine.models.system import SystemConfig, SystemSettings, ClusterSettingsConfig
from roostos_engine.models.network import NetworkConfig, NetworkSettings, NetworkBridge
from roostos_engine.subsystems.network_interfaces import NetworkInterfacesSubsystem


def test_cluster_manager_join_and_heartbeat():
    cm = ClusterManager(mock=True)

    # 1. Token generation & validation
    token = cm.generate_join_token(ttl_seconds=300)
    assert token.startswith("roost-")
    assert cm.validate_join_token(token) is True
    assert cm.validate_join_token("invalid-token") is False

    # 2. Register node
    existing_nodes = [
        NodeConfig(id="node-01", name="Primary Gateway", roles=[NodeRole.GATEWAY_ROUTER])
    ]
    join_payload = {
        "node_id": "node-02",
        "name": "Satellite AP",
        "roles": ["access_point"],
        "management_ip": "192.168.1.2",
    }
    new_node = cm.register_node(join_payload, existing_nodes)
    assert new_node.id == "node-02"
    assert new_node.name == "Satellite AP"
    assert NodeRole.ACCESS_POINT in new_node.roles

    # 3. Heartbeat recording
    cm.record_heartbeat("node-02", {
        "status": "healthy",
        "telemetry": {"cpu_percent": 15.2, "memory_percent": 50.0},
        "updates_status": {"updates_available": 1, "security_updates_available": 0},
    })
    hb = cm.get_node_heartbeat("node-02")
    assert hb is not None
    assert hb["status"] == "healthy"
    assert hb["telemetry"]["cpu_percent"] == 15.2
    assert hb["updates_status"]["updates_available"] == 1

    # 4. Config slice synthesis
    sys_cfg = SystemConfig(system=SystemSettings(hostname="roost-ctrl", cluster=ClusterSettingsConfig(controller_url="http://192.168.1.1:8000")))
    net_cfg = NetworkConfig(network=NetworkSettings(bridges=[NetworkBridge(name="br0", ip="192.168.1.1/24")]))
    slice_data = cm.get_node_config_slice("node-02", sys_cfg, net_cfg, [existing_nodes[0], new_node])
    assert slice_data["node_id"] == "node-02"
    assert slice_data["controller_url"] == "http://192.168.1.1:8000"
    assert len(slice_data["bridges"]) == 1


@pytest.mark.asyncio
async def test_cluster_sync_agent_mock():
    agent = ClusterSyncAgent(
        node_id="node-02",
        controller_url="mock://controller",
        sync_interval_seconds=1,
        mock=True,
    )

    hb_res = await agent.send_heartbeat(status="healthy")
    assert hb_res["status"] == "acknowledged"

    slice_res = await agent.fetch_config_slice()
    assert slice_res is not None
    assert slice_res["node_id"] == "node-02"

    applied = await agent.apply_config_slice(slice_res)
    assert applied is True

    join_res = await agent.join_cluster(token="roost-mock", name="Node 02")
    assert join_res["status"] == "success"
    assert join_res["node_id"] == "node-02"


def test_network_interfaces_subsystem_node_awareness():
    # Setup daemon mock with node-specific interfaces in nodes.yaml
    node_ifaces = [
        NodeInterface(name="eth0", mode=InterfaceMode.WAN),
        NodeInterface(name="eth1", mode=InterfaceMode.ACCESS, bridge="br0"),
    ]
    node = NodeConfig(id="node-test", name="Worker", roles=[NodeRole.GATEWAY_ROUTER], interfaces=node_ifaces)

    daemon = MagicMock()
    daemon.mock = True
    daemon._config = MagicMock()
    daemon._config.system = SystemConfig(system=SystemSettings(cluster=ClusterSettingsConfig(node_id="node-test")))
    daemon._config.nodes = [node]
    daemon._config.network = NetworkConfig(network=NetworkSettings(bridges=[NetworkBridge(name="br0", ip="192.168.1.1/24")]))

    sub = NetworkInterfacesSubsystem(daemon)
    resolved = sub._resolve_target_interfaces()

    assert len(resolved) == 2
    assert resolved[0].name == "eth0"
    assert resolved[0].network == "wan"
    assert resolved[1].name == "eth1"
    assert resolved[1].bridge == "br0"
