import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from roostos_web.main import create_app
from roostos_engine.repository import ConfigRepository
from roostos_engine.models.networks import Network, NetworkLink


from roostos_engine.config import NetworkSettings, NetworkConfig


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=ConfigRepository)
    config = MagicMock()
    net_settings = NetworkSettings(
        networks=[
            Network(
                id="lab-lan",
                name="RoostOS Lab",
                subnet="192.168.1.0/24",
                gateway_ip="192.168.1.1",
                network_type="lan",
                interface="br-lan",
                zone_id="lab"
            ),
            Network(
                id="home-lan",
                name="Upstream Home",
                subnet="192.168.5.0/24",
                gateway_ip="192.168.5.1",
                network_type="wan_upstream",
                interface="eth0",
                zone_id="home"
            ),
        ],
        links=[
            NetworkLink(
                id="link-lab-home",
                source_network_id="lab-lan",
                target_network_id="home-lan",
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


from roostos_web.di import get_injector


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
    assert data["networks"][0]["subnet"] == "192.168.1.0/24"
    assert data["links"][0]["connection_type"] == "physical_wan"
    assert len(data["visual_nodes"]) == 2
    assert len(data["visual_edges"]) == 1


def test_upsert_subnet_and_link(client, mock_repo):
    # 1. Add VPS subnet
    sub_res = client.post("/api/network/topology/subnets", json={
        "id": "vps-vpc",
        "name": "Cloud VPS",
        "subnet": "172.26.0.0/20",
        "gateway_ip": "172.26.2.49",
        "network_type": "cloud_vpc",
        "interface": "vps-eth0",
        "zone_id": "vps"
    })
    assert sub_res.status_code == 200
    assert sub_res.json()["subnet"] == "172.26.0.0/20"

    # 2. Add WireGuard link between Lab and VPS
    link_res = client.post("/api/network/topology/links", json={
        "id": "link-lab-vps",
        "source_network_id": "lab-lan",
        "target_network_id": "vps-vpc",
        "connection_type": "wireguard_tunnel",
        "routing_mode": "routed",
        "firewall_policy": "source_to_target_only",
        "allowed_ports": ["80", "443"]
    })
    assert link_res.status_code == 200
    assert link_res.json()["connection_type"] == "wireguard_tunnel"

    # 3. Delete link
    del_res = client.delete("/api/network/topology/links/link-lab-vps")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
