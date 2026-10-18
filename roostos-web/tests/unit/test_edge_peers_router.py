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


def test_vpn_servers_listing_and_update(auth_headers, setup_test_repo):
    client = TestClient(app)
    repo = setup_test_repo

    # Add a cluster node
    from roostos_engine.models.node import NodeConfig, NodeRole
    config = repo.get_config()
    config.nodes = [
        NodeConfig(
            id="node-01",
            name="Main Router",
            roles=[NodeRole.GATEWAY_ROUTER],
            management_ip="192.168.1.1",
        )
    ]
    from roostos_engine.models.node import NodesConfigFile
    repo.save_nodes_config(NodesConfigFile(nodes=config.nodes))

    # 1. List VPN servers
    res = client.get("/api/v1/edge/peers/servers", headers=auth_headers)
    assert res.status_code == 200
    servers = res.json()
    server_ids = [s["id"] for s in servers]
    assert "edge-01" in server_ids
    assert "node-01" in server_ids

    # 2. Update Edge Gateway VPN server hostname
    up_edge = client.put(
        "/api/v1/edge/peers/servers/edge-01",
        json={"hostname": "edge.myvps.cloud", "port": 51820},
        headers=auth_headers,
    )
    assert up_edge.status_code == 200
    assert up_edge.json()["hostname"] == "edge.myvps.cloud"

    # 3. Update Cluster Node VPN server hostname and enable VPN server
    up_node = client.put(
        "/api/v1/edge/peers/servers/node-01",
        json={"hostname": "vpn.home.org", "port": 51822, "is_vpn_server": True},
        headers=auth_headers,
    )
    assert up_node.status_code == 200
    assert up_node.json()["hostname"] == "vpn.home.org"
    assert up_node.json()["port"] == 51822
    assert up_node.json()["is_vpn_server"] is True

    # 4. Create peer targeted to node-01
    peer_res = client.post(
        "/api/v1/edge/peers",
        json={"name": "Matt's Android", "peer_type": "mobile", "server_node_id": "node-01", "route_internet": True},
        headers=auth_headers,
    )
    assert peer_res.status_code == 200
    peer_data = peer_res.json()
    assert peer_data["server_node_id"] == "node-01"
    assert "Endpoint = vpn.home.org:51822" in peer_data["client_config"]


def test_disconnect_edge_gateway_and_cleanup(auth_headers, setup_test_repo, tmp_path, monkeypatch):
    client = TestClient(app)
    repo = setup_test_repo

    # Set up mock networkd and cert files
    net_dir = str(tmp_path / "networkd")
    import os
    os.makedirs(net_dir, exist_ok=True)
    monkeypatch.setenv("ROOSTOS_SYSTEMD_NETWORK_DIR", net_dir)
    with open(os.path.join(net_dir, "50-wg-edge.netdev"), "w") as f:
        f.write("[NetDev]\nName=wg-edge\n")

    # Add ingress route and certificate
    from roostos_engine.models.edge import IngressRoute
    config = repo.get_config()
    gw = config.network.edge_gateways[0]
    gw.ingress_routes = [
        IngressRoute(id="r1", domain="testapp.vps.com", target_ip="192.168.1.100", target_port=8080)
    ]
    repo.save_network_config(config.network)

    cert_dir = os.path.join(repo.config_dir, "certs", "domains", "testapp.vps.com")
    os.makedirs(cert_dir, exist_ok=True)
    with open(os.path.join(cert_dir, "cert.pem"), "w") as f:
        f.write("CERT_DATA")

    # Call disconnect
    res = client.post("/api/v1/edge/disconnect", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "testapp.vps.com" in data["cleaned_certificates"]
    assert data["networkd_removed"] is True
    assert not os.path.exists(cert_dir)
    assert not os.path.exists(os.path.join(net_dir, "50-wg-edge.netdev"))

    # Verify edge status is unlinked
    st_res = client.get("/api/v1/edge/status", headers=auth_headers)
    assert st_res.status_code == 200
    assert st_res.json()["linked"] is False

