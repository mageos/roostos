import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from roostos_web.main import create_app
from roostos_engine.repository import ConfigRepository
from roostos_engine.models.networks import Network, NetworkLink
from roostos_engine.config import NetworkSettings, NetworkConfig
from roostos_web.di import get_injector


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=ConfigRepository)
    config = MagicMock()
    net_settings = NetworkSettings(
        networks=[
            Network(
                id="office-lan",
                name="Primary Office LAN",
                subnet="10.0.1.0/24",
                gateway_ip="10.0.1.1",
                network_type="lan",
                interface="br-lan",
                zone_id="lan"
            ),
            Network(
                id="upstream-wan",
                name="Upstream WAN",
                subnet="198.51.100.0/24",
                gateway_ip="198.51.100.1",
                network_type="wan_upstream",
                interface="eth0",
                zone_id="wan"
            ),
        ],
        links=[
            NetworkLink(
                id="link-office-wan",
                source_network_id="office-lan",
                target_network_id="upstream-wan",
                connection_type="physical_wan",
                routing_mode="nat_masquerade",
                firewall_policy="source_to_target_only",
                status="active"
            )
        ],
        zones=[]
    )
    config.network = NetworkConfig(network=net_settings)
    repo.get_config.return_value = config
    return repo


@pytest.fixture
def client(mock_repo):
    app = create_app()
    from roostos_web.auth import get_current_parent, get_current_admin, UserSession

    mock_user = UserSession(username="admin", role="admin")
    app.dependency_overrides[get_current_parent] = lambda: mock_user
    app.dependency_overrides[get_current_admin] = lambda: mock_user

    injector = get_injector()
    injector.binder.bind(ConfigRepository, to=mock_repo)

    return TestClient(app)


def test_get_topology(client):
    res = client.get("/api/network/topology")
    assert res.status_code == 200
    data = res.json()
    assert "networks" in data
    assert "links" in data
    assert len(data["networks"]) == 2
    assert data["networks"][0]["subnet"] == "10.0.1.0/24"
    assert data["links"][0]["connection_type"] == "physical_wan"
    assert len(data["visual_nodes"]) == 2
    assert len(data["visual_edges"]) == 1


def test_upsert_subnet_and_link(client, mock_repo):
    # 1. Add cloud VPC subnet
    sub_res = client.post("/api/network/topology/subnets", json={
        "id": "cloud-vpc",
        "name": "Cloud VPC",
        "subnet": "10.100.0.0/16",
        "gateway_ip": "10.100.0.1",
        "network_type": "cloud_vpc",
        "interface": "vps-eth0",
        "zone_id": "cloud"
    })
    assert sub_res.status_code == 200
    assert sub_res.json()["subnet"] == "10.100.0.0/16"

    # 2. Add WireGuard link
    link_res = client.post("/api/network/topology/links", json={
        "id": "link-office-cloud",
        "source_network_id": "office-lan",
        "target_network_id": "cloud-vpc",
        "connection_type": "wireguard_tunnel",
        "routing_mode": "routed",
        "firewall_policy": "source_to_target_only",
        "allowed_ports": ["80", "443"]
    })
    assert link_res.status_code == 200
    assert link_res.json()["connection_type"] == "wireguard_tunnel"

    # 3. Delete link
    del_res = client.delete("/api/network/topology/links/link-office-cloud")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
