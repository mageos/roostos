import pytest
import os
from roostos_engine.models.node import NodeConfig, NodeRole, NodeInterface, InterfaceType, InterfaceMode
from roostos_engine.models.system import SystemSettings, ClusterSettingsConfig
from roostos_engine.hardware_inspector import HardwareInspector, DetectedHardwareInterface
from roostos_engine.health import HealthChecker, NodeHealthReport
from roostos_engine.cluster_manager import ClusterManager
from roostos_engine.mdns_discovery import MDNSDiscoveryService


def test_hardware_inspector_mock():
    interfaces = HardwareInspector.inspect_network_interfaces(mock=True)
    assert len(interfaces) >= 2
    eth0 = next((i for i in interfaces if i.name == "eth0"), None)
    assert eth0 is not None
    assert eth0.type == InterfaceType.ETHERNET
    assert eth0.mac_address == "52:54:00:12:34:56"

    # Delta detection
    node = NodeConfig(
        id="node-01",
        name="Router",
        roles=[NodeRole.GATEWAY_ROUTER],
        interfaces=[NodeInterface(name="eth0", mac_address="52:54:00:12:34:56", type=InterfaceType.ETHERNET)]
    )
    delta = HardwareInspector.detect_new_hardware(configured_node=node, mock=True)
    assert len(delta) >= 1
    assert all(d.name != "eth0" for d in delta)


@pytest.mark.asyncio
async def test_health_checker_with_mqtt(tmp_path):
    checker = HealthChecker(config_dir=str(tmp_path), mock=True)
    report = checker.collect_health_report(
        node_id="node-01",
        node_name="Primary Gateway",
        roles=["controller", "gateway_router"],
        dbus_connected=True,
        check_mqtt=True,
    )
    assert report.node_id == "node-01"
    assert report.status == "healthy"
    assert report.telemetry.cpu_load >= 0
    assert report.mqtt_bus is not None
    assert report.mqtt_bus.status == "PASS"
    assert report.mqtt_bus.latency_ms > 0
    assert "node-01" in report.mqtt_bus.responding_nodes


def test_cluster_manager_status(tmp_path):
    manager = ClusterManager(config_dir=str(tmp_path), mock=True)
    
    # Standalone single node
    system = SystemSettings(hostname="roost-home", cluster=ClusterSettingsConfig(node_id="node-01"))
    nodes = [
        NodeConfig(
            id="node-01",
            name="Primary Gateway",
            roles=[NodeRole.CONTROLLER, NodeRole.GATEWAY_ROUTER],
            management_ip="192.168.1.1",
            interfaces=[NodeInterface(name="eth0", type=InterfaceType.ETHERNET, mode=InterfaceMode.WAN)]
        )
    ]
    status = manager.get_cluster_status(system, nodes)
    assert status.role == "standalone"
    assert status.is_controller is True
    assert status.registered_nodes_count == 1

    # Multiple nodes
    nodes.append(
        NodeConfig(
            id="node-02",
            name="Living Room AP",
            roles=[NodeRole.ACCESS_POINT],
            management_ip="192.168.1.2",
            interfaces=[]
        )
    )
    status_multi = manager.get_cluster_status(system, nodes)
    assert status_multi.role == "controller"
    assert status_multi.registered_nodes_count == 2

    # Pairing Token
    token = manager.generate_join_token()
    assert token.startswith("roost-")
    assert manager.validate_join_token(token) is True
    assert manager.validate_join_token("invalid-token") is False
