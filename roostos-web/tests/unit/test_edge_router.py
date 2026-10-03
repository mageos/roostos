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
