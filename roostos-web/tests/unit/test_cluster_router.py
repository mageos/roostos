import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.models.node import NodeConfig, NodeRole, NodeInterface, InterfaceType, InterfaceMode
from roostos_engine.models.system import SystemSettings
from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.di import create_web_injector, set_injector
from roostos_web.auth import create_access_token


class DummyClusterConfigRepo(ConfigRepository):
    def __init__(self):
        self.config = MagicMock()
        self.config.system = SystemSettings(hostname="roost-unit-router")
        from roostos_engine.models.network import NetworkSettings
        self.config.network = NetworkSettings(bridges=[])
        self.config.nodes = [
            NodeConfig(
                id="node-01",
                name="Unit Primary Router",
                roles=[NodeRole.CONTROLLER, NodeRole.GATEWAY_ROUTER],
                management_ip="192.168.1.1",
                interfaces=[]
            )
        ]
        self.config.users = []

    def get_config(self):
        return self.config

    def save_system_config(self, data):
        pass

    def save_nodes_config(self, data):
        self.config.nodes = data.nodes

    def save_devices_config(self, data):
        pass

    def save_network_config(self, data):
        pass

    def save_schedules_config(self, data):
        pass

    def save_firewall_config(self, data):
        pass

    def save_plugins_config(self, data):
        pass


@pytest.fixture
def cluster_test_setup(tmp_path):
    repo = DummyClusterConfigRepo()
    dbus = AsyncMock()
    dbus.get_cluster_status.return_value = {
        "role": "standalone",
        "is_controller": True,
        "node_id": "node-01",
        "node_name": "Unit Primary Router",
        "roles": ["controller", "gateway_router"],
        "controller_url": None,
        "connected_to_controller": True,
        "registered_nodes_count": 1,
        "nodes": [repo.config.nodes[0].model_dump()],
    }
    dbus.get_nodes.return_value = [repo.config.nodes[0].model_dump()]
    dbus.generate_join_token.return_value = "roost-test-token"
    dbus.validate_join_token.side_effect = lambda t: t.startswith("roost-")
    dbus.discover_controllers.return_value = [{"hostname": "roost-other.local", "ip": "192.168.1.50", "port": 8000, "node_id": "node-02"}]
    dbus.get_detected_hardware.return_value = [{"name": "eth0", "mac_address": "52:54:00:12:34:56", "type": "ethernet"}]
    dbus.get_node_health.return_value = {
        "node_id": "node-01",
        "node_name": "Unit Primary Router",
        "status": "healthy",
        "timestamp": "2026-08-18T00:00:00Z",
        "roles": ["controller", "gateway_router"],
        "subsystems": [],
        "telemetry": {"cpu_usage_percent": 5.0, "memory_usage_percent": 20.0, "disk_usage_percent": 10.0, "uptime_seconds": 1200},
        "mqtt_health": {"status": "healthy", "latency_ms": 1.2, "nodes_responded": ["node-01"], "message": "All nodes responding."},
    }

    injector = create_web_injector(
        config_dir=str(tmp_path),
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="yaml", system_client="mock")
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus
    yield repo, dbus
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_cluster_endpoints(cluster_test_setup, auth_headers):
    repo, dbus = cluster_test_setup
    client = TestClient(app)

    # 1. Status
    res = client.get("/api/cluster/status", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["role"] == "standalone"

    # 2. Nodes
    res = client.get("/api/cluster/nodes", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["nodes"]) == 1

    # 3. Create Node
    new_node = {
        "id": "node-02",
        "name": "Access Point 1",
        "roles": ["access_point"],
        "management_ip": "192.168.1.10",
        "interfaces": [{"name": "eth0", "type": "ethernet", "mode": "trunk"}]
    }
    res = client.post("/api/cluster/nodes", json=new_node, headers=auth_headers)
    assert res.status_code == 200

    # 4. Generate Token
    res = client.post("/api/cluster/token", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["token"] == "roost-test-token"

    # 5. Discover
    res = client.post("/api/cluster/discover", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["controllers"]) == 1

    # 6. Hardware
    res = client.get("/api/cluster/hardware", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["hardware"]) == 1


def test_health_endpoint(cluster_test_setup, auth_headers):
    repo, dbus = cluster_test_setup
    client = TestClient(app)

    # Standard health check
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == "node-01"
    assert data["status"] == "healthy"
    assert data["mqtt_health"] is not None


def test_cluster_sync_and_heartbeat_endpoints(cluster_test_setup, auth_headers):
    repo, dbus = cluster_test_setup
    client = TestClient(app)

    # 1. Join with invalid token
    res = client.post("/api/cluster/join", json={
        "token": "invalid-token",
        "node_id": "node-02",
        "name": "Access Point",
        "roles": ["access_point"],
    })
    assert res.status_code == 400

    # 2. Join with mock valid token (in mock mode "roost-" prefix passes)
    res = client.post("/api/cluster/join", json={
        "token": "roost-valid-1234",
        "node_id": "node-02",
        "name": "Access Point",
        "roles": ["access_point"],
        "management_ip": "192.168.1.50",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["node_id"] == "node-02"

    # 3. Post Heartbeat
    hb_payload = {
        "status": "healthy",
        "telemetry": {"cpu_percent": 14.0, "memory_percent": 30.0},
        "warnings": [],
        "updates_status": {"updates_available": 0, "security_updates_available": 0}
    }
    res = client.post("/api/cluster/nodes/node-02/heartbeat", json=hb_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "acknowledged"

    # 4. Get Heartbeat
    res = client.get("/api/cluster/nodes/node-02/heartbeat", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["telemetry"]["cpu_percent"] == 14.0

    # 5. Get Config Slice
    res = client.get("/api/cluster/nodes/node-02/config")
    assert res.status_code == 200
    slice_data = res.json()
    assert slice_data["node_id"] == "node-02"
    assert "access_point" in slice_data["roles"]

    # 6. Get Cluster Updates Summary
    res = client.get("/api/cluster/updates", headers=auth_headers)
    assert res.status_code == 200
    up_summary = res.json()
    assert "total_updates" in up_summary
    assert len(up_summary["nodes"]) >= 1

    # 7. Queue Node Update Command
    res = client.post("/api/cluster/nodes/node-02/updates/install?security_only=true", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["command"] == "install_security_updates"


def test_cluster_join_with_admin_jwt(cluster_test_setup):
    repo, dbus = cluster_test_setup
    client = TestClient(app)
    admin_token = create_access_token({"sub": "admin", "role": "admin"})

    res = client.post("/api/cluster/join", json={
        "token": admin_token,
        "node_id": "node-03",
        "name": "Edge VPS Node",
        "roles": ["edge_gateway"],
        "management_ip": "10.42.0.1",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["node_id"] == "node-03"
    assert "successfully enrolled" in data["message"]



