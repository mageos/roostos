import os
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from roostos_engine.models.edge import EdgeGatewayConfig, IngressRoute
from roostos_engine.models.network import NetworkConfig, NetworkSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.di import create_web_injector, set_injector
from roostos_web.auth import create_access_token


@pytest.fixture
def edge_client(tmp_path):
    repo = MagicMock(spec=ConfigRepository)
    config = MagicMock()
    config.network = MagicMock()
    config.network.edge_gateways = [
        EdgeGatewayConfig(
            id="edge-01",
            name="Test VPS Gateway",
            public_ip="198.51.100.10",
            listen_port=51820,
            tunnel_ip_gateway="10.42.0.1/24",
            tunnel_ip_home="10.42.0.2/24",
            status="connected",
            ingress_routes=[],
        )
    ]
    repo.get_config.return_value = config
    repo.config_dir = str(tmp_path)
    dbus = AsyncMock()

    from roostos_engine.models.providers import ProvidersSettings
    injector = create_web_injector(
        config_dir=str(tmp_path),
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="staging", system_client="mock")
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus

    client = TestClient(app)
    yield client, repo
    app.dependency_overrides.clear()
    set_injector(None)


@pytest.fixture
def admin_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_generate_bootstrap_token(edge_client, admin_headers):
    client, _ = edge_client
    payload = {"public_ip": "203.0.113.10", "port": 8000, "ttl_minutes": 10}
    res = client.post("/api/edge/token", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["public_ip"] == "203.0.113.10"
    assert data["endpoint_url"] == "http://203.0.113.10:8000"


def test_enroll_endpoint_with_bootstrap_token(edge_client, admin_headers):
    client, _ = edge_client
    # 1. Generate token
    token_res = client.post("/api/edge/token", json={"public_ip": "203.0.113.10"}, headers=admin_headers)
    bootstrap_token = token_res.json()["token"]

    # 2. Call public enrollment with Bearer token
    enroll_payload = {
        "home_public_key": "home_wireguard_mock_public_key_abc=",
        "hostname": "roost-home-node",
    }
    enroll_headers = {"Authorization": f"Bearer {bootstrap_token}"}
    res = client.post("/api/edge/enroll", json=enroll_payload, headers=enroll_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "gateway_public_key" in data
    assert data["endpoint"] == "203.0.113.10:51820"
    assert data["assigned_tunnel_ip"] == "10.42.0.2/24"


def test_enroll_endpoint_unauthorized(edge_client):
    client, _ = edge_client
    res = client.post("/api/edge/enroll", json={"home_public_key": "abc"})
    assert res.status_code == 401


def test_edge_status_and_routes_crud(edge_client, admin_headers):
    client, repo = edge_client

    # Check status
    res = client.get("/api/edge/status", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["linked"] is True

    # Add ingress route
    route_payload = {
        "domain": "homeassistant.example.com",
        "target_ip": "192.168.1.10",
        "target_port": 8123,
        "ssl_enabled": True,
    }
    add_res = client.post("/api/edge/routes", json=route_payload, headers=admin_headers)
    assert add_res.status_code == 200
    route_data = add_res.json()
    assert route_data["domain"] == "homeassistant.example.com"
    route_id = route_data["id"]

    # List routes
    list_res = client.get("/api/edge/routes", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(r["id"] == route_id for r in list_res.json())

    # Delete route
    del_res = client.delete(f"/api/edge/routes/{route_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"


def test_edge_lockdown_endpoint(edge_client, admin_headers):
    client, _ = edge_client
    res = client.post("/api/edge/lockdown?wan_interface=eth0", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert len(res.json()["rules"]) > 0


def test_enroll_consumed_token_returns_403(edge_client, admin_headers):
    client, _ = edge_client
    token_res = client.post("/api/edge/token", json={"public_ip": "203.0.113.10"}, headers=admin_headers)
    token = token_res.json()["token"]

    enroll_payload = {"home_public_key": "home_key_123=", "hostname": "roost-home"}
    headers = {"Authorization": f"Bearer {token}"}

    # 1. First enrollment succeeds
    first = client.post("/api/edge/enroll", json=enroll_payload, headers=headers)
    assert first.status_code == 200

    # 2. Second enrollment with consumed token must return 403
    second = client.post("/api/edge/enroll", json=enroll_payload, headers=headers)
    assert second.status_code == 403
    assert "already been consumed" in second.json()["detail"]


def test_connect_endpoint_wireguard_token(edge_client, admin_headers):
    """Verifies connecting via WireGuard invite token (Option 1 zero web exposure)."""
    from roostos_engine.edge_manager import EdgeManager

    client, repo = edge_client
    mgr = EdgeManager(mock=True)
    invite = mgr.create_wireguard_invite(vps_public_ip="203.0.113.88", listen_port=51820)
    token = invite.to_token()

    res = client.post("/api/edge/connect", json={"token": token, "name": "Zero-Web VPS"}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["public_ip"] == "203.0.113.88"
    assert data["status"] == "connected"
    assert data["tunnel_ip_gateway"] == "10.42.0.1/24"
    assert data["tunnel_ip_home"] == "10.42.0.2/24"


def test_connect_and_status_with_real_repository(tmp_path, admin_headers):
    """Verifies connecting via API persists to real YAML repository and updates /api/edge/status to linked."""
    from roostos_engine.repository import YAMLConfigRepository
    from roostos_engine.edge_manager import EdgeManager
    from roostos_engine.models import load_config_directory
    from roostos_engine.models.providers import ProvidersSettings

    real_repo = YAMLConfigRepository(str(tmp_path))
    dbus = AsyncMock()

    injector = create_web_injector(
        config_dir=str(tmp_path),
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="staging", system_client="mock")
    )
    injector.binder.bind(ConfigRepository, to=real_repo)
    injector.binder.bind(RoostClient, to=dbus)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: real_repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus

    test_client = TestClient(app)

    # 1. Before connecting: status should be unlinked
    st_before = test_client.get("/api/edge/status", headers=admin_headers)
    assert st_before.status_code == 200
    assert st_before.json()["linked"] is False

    # 2. Connect via WireGuard token
    mgr = EdgeManager(mock=True)
    invite = mgr.create_wireguard_invite(vps_public_ip="203.0.113.99", listen_port=51820)
    token = invite.to_token()

    conn_res = test_client.post("/api/edge/connect", json={"token": token, "name": "Prod Edge VPS"}, headers=admin_headers)
    assert conn_res.status_code == 200

    # 3. After connecting: status should be linked: True with gateway details
    st_after = test_client.get("/api/edge/status", headers=admin_headers)
    assert st_after.status_code == 200
    st_data = st_after.json()
    assert st_data["linked"] is True
    assert len(st_data["gateways"]) == 1
    assert st_data["gateways"][0]["public_ip"] == "203.0.113.99"
    assert st_data["gateways"][0]["status"] == "connected"

    # 4. Verify network.yaml is persisted on disk and reloaded by load_config_directory
    reloaded_cfg = load_config_directory(str(tmp_path))
    assert len(reloaded_cfg.edge_gateways) == 1
    assert reloaded_cfg.edge_gateways[0].public_ip == "203.0.113.99"
    assert len(reloaded_cfg.network.edge_gateways) == 1

    app.dependency_overrides.clear()
    set_injector(None)


def test_edge_status_fallback_to_cluster_nodes(tmp_path, admin_headers):
    """Verifies that if network.yaml edge_gateways is empty, edge status falls back to joined cluster nodes."""
    from roostos_engine.models.node import NodeConfig, NodeRole
    from roostos_engine.models.network import NetworkSettings
    from roostos_engine.models.providers import ProvidersSettings
    fake_repo = MagicMock(spec=ConfigRepository)
    mock_config = MagicMock()
    mock_config.network = NetworkSettings()
    mock_config.edge_gateways = []
    mock_config.nodes = [
        NodeConfig(
            id="node-vps-01",
            name="VPS Edge Node",
            roles=[NodeRole.EDGE_GATEWAY],
            management_ip="198.51.100.22",
            status="active",
        )
    ]
    fake_repo.get_config.return_value = mock_config
    fake_repo.config_dir = str(tmp_path)

    injector = create_web_injector(
        config_dir=str(tmp_path),
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="staging", system_client="mock")
    )
    injector.binder.bind(ConfigRepository, to=fake_repo)
    injector.binder.bind(RoostClient, to=AsyncMock())
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: fake_repo
    client = TestClient(app)

    res = client.get("/api/edge/status", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["linked"] is True
    assert len(data["gateways"]) == 1
    assert data["gateways"][0]["id"] == "edge-01"
    assert data["gateways"][0]["name"] == "VPS Edge Node"
    assert data["gateways"][0]["public_ip"] == "198.51.100.22"
    assert data["gateways"][0]["status"] == "connected"

    app.dependency_overrides.clear()
    set_injector(None)


def test_update_edge_endpoint(edge_client, admin_headers, tmp_path, monkeypatch):
    """Verifies updating edge endpoint domain via PUT /api/edge/endpoint."""
    client, repo = edge_client
    net_dir = str(tmp_path / "networkd")
    os.makedirs(net_dir, exist_ok=True)
    monkeypatch.setenv("ROOSTOS_SYSTEMD_NETWORK_DIR", net_dir)
    with open(os.path.join(net_dir, "50-wg-edge.netdev"), "w") as f:
        f.write("[WireGuardPeer]\nEndpoint=1.1.1.1:51820\n")

    res = client.put("/api/edge/endpoint", json={"domain": "vps.example.com", "port": 51820}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["domain"] == "vps.example.com"

    with open(os.path.join(net_dir, "50-wg-edge.netdev"), "r") as f:
        assert "Endpoint=vps.example.com:51820" in f.read()




