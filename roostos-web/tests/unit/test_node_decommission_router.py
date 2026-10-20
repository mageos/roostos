import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.models.node import NodeConfig, NodeRole
from roostos_engine.models.system import SystemSettings, ClusterSettingsConfig
from roostos_engine.models.network import NetworkSettings
from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.di import create_web_injector, set_injector
from roostos_web.auth import create_access_token


class DummyDecomRepo(ConfigRepository):
    def __init__(self, tmp_path):
        super().__init__()
        self.config_dir = str(tmp_path)
        self.config = MagicMock()
        self.config.system = SystemSettings(
            hostname="roost-unit-router",
            cluster=ClusterSettingsConfig(node_id="node-01", controller_url="https://controller.local:8443", epoch=2)
        )
        self.config.network = NetworkSettings(bridges=[])
        self.config.network.edge_gateways = []
        self.config.nodes = [
            NodeConfig(id="node-01", name="Primary Router", roles=[NodeRole.CONTROLLER, NodeRole.GATEWAY_ROUTER]),
            NodeConfig(id="node-02", name="Worker Node", roles=[NodeRole.GATEWAY_ROUTER], management_ip="192.168.1.50"),
        ]

    def get_config(self): return self.config
    def save_system_config(self, data): self.config.system = data
    def save_nodes_config(self, data): self.config.nodes = data.nodes
    def save_network_config(self, data): self.config.network = data
    def save_devices_config(self, data): pass
    def save_schedules_config(self, data): pass
    def save_firewall_config(self, data): pass
    def save_plugins_config(self, data): pass


@pytest.fixture
def decom_setup(tmp_path):
    repo = DummyDecomRepo(tmp_path)
    dbus = AsyncMock()
    dbus.save_nodes.return_value = True

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
def admin_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_delete_node_decommissions_and_invalidates(decom_setup, admin_headers):
    repo, dbus = decom_setup
    client = TestClient(app)

    # 1. DELETE node-02
    res = client.delete("/api/v1/cluster/nodes/node-02", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == "node-02"
    assert data["credentials_invalidated"] is True
    assert data["success"] is True

    # Check inventory
    assert len(repo.config.nodes) == 1
    assert repo.config.nodes[0].id == "node-01"


def test_evict_node_endpoint(decom_setup, admin_headers):
    repo, dbus = decom_setup
    client = TestClient(app)

    res = client.post("/api/v1/cluster/nodes/node-02/evict", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == "node-02"
    assert data["credentials_invalidated"] is True


def test_leave_cluster_endpoint(decom_setup, admin_headers):
    repo, dbus = decom_setup
    client = TestClient(app)

    res = client.post("/api/v1/cluster/leave", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_self"] is True
    assert data["credentials_invalidated"] is True
    assert repo.config.system.cluster.controller_url is None
