"""Unit tests for Edge Gateway multi-peer VPN and mobile enrollment router."""

import pytest
from fastapi.testclient import TestClient

from roostos_engine.models.edge import EdgeGatewayConfig
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import create_access_token
from roostos_web.di import create_web_injector, set_injector
from roostos_web.main import app


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_test_repo(tmp_path):
    config_dir = str(tmp_path / "config")
    injector = create_web_injector(config_dir=config_dir)
    set_injector(injector)
    repo = injector.get(ConfigRepository)

    # Initialize a connected Edge Gateway
    gw = EdgeGatewayConfig(
        id="edge-01",
        name="Test VPS Gateway",
        public_ip="203.0.113.5",
        listen_port=51820,
        tunnel_ip_gateway="10.42.0.1/24",
        tunnel_ip_home="10.42.0.2/24",
        public_key="GATEWAY_PUB_KEY_1234567890=",
        status="connected",
    )
    config = repo.get_config()
    config.network.edge_gateways = [gw]
    repo.save_network_config(config.network)
    yield repo


def test_list_edge_peers_initially_empty(auth_headers):
    client = TestClient(app)
    res = client.get("/api/edge/peers", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_create_mobile_and_site_peers(auth_headers):
    client = TestClient(app)

    # 1. Create Mobile Peer (e.g. iPhone)
    mobile_payload = {
        "name": "Matt's iPhone",
        "peer_type": "mobile",
        "route_internet": True,
    }
    m_res = client.post("/api/edge/peers", json=mobile_payload, headers=auth_headers)
    assert m_res.status_code == 200
    m_data = m_res.json()
    assert m_data["name"] == "Matt's iPhone"
    assert m_data["peer_type"] == "mobile"
    assert "10.42.0.10" in m_data["assigned_ip"]
    assert "[Interface]" in m_data["client_config"]
    assert "Endpoint = 203.0.113.5:51820" in m_data["client_config"]
    assert "AllowedIPs = 0.0.0.0/0, ::/0" in m_data["client_config"]

    # 2. Create Site-to-Site Peer (e.g. Vacation House)
    site_payload = {
        "name": "Vacation House Router",
        "peer_type": "site",
        "subnets": ["192.168.2.0/24"],
        "route_internet": False,
    }
    s_res = client.post("/api/edge/peers", json=site_payload, headers=auth_headers)
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["name"] == "Vacation House Router"
    assert s_data["peer_type"] == "site"
    assert s_data["subnets"] == ["192.168.2.0/24"]

    # 3. List peers returns both
    list_res = client.get("/api/edge/peers", headers=auth_headers)
    assert list_res.status_code == 200
    peers = list_res.json()
    assert len(peers) == 2

    # 4. Download WireGuard client configuration file
    peer_id = m_data["id"]
    conf_res = client.get(f"/api/edge/peers/{peer_id}/config", headers=auth_headers)
    assert conf_res.status_code == 200
    assert "[Interface]" in conf_res.text
    assert ".conf" in conf_res.headers.get("Content-Disposition", "")

    # 5. Delete Peer
    del_res = client.delete(f"/api/edge/peers/{peer_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify only site peer remains
    remaining = client.get("/api/edge/peers", headers=auth_headers).json()
    assert len(remaining) == 1
    assert remaining[0]["name"] == "Vacation House Router"
