"""Unit tests for RoostOS App Catalog and local container image router."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from roostos_engine.models.edge import EdgeGatewayConfig
from roostos_engine.models.plugins import PluginConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.di import create_web_injector, set_injector
from roostos_web.auth import create_access_token


@pytest.fixture
def catalog_client(tmp_path):
    repo = MagicMock(spec=ConfigRepository)
    config = MagicMock()
    config.plugins = [PluginConfig(id="existing-plugin", name="Existing Plugin", enabled=True)]
    config.network = MagicMock()
    config.network.bridges = [MagicMock(ip="192.168.1.1/24")]
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


def test_list_and_add_catalog_sources(catalog_client, admin_headers):
    client, _ = catalog_client
    # Initial list
    res = client.get("/api/catalog/sources", headers=admin_headers)
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) >= 1

    # Add source
    new_src = {
        "id": "my-homelab",
        "name": "My Homelab Repos",
        "url": "http://192.168.1.100:8000/catalog.json",
        "enabled": True,
        "allow_insecure": True,
    }
    post_res = client.post("/api/catalog/sources", json=new_src, headers=admin_headers)
    assert post_res.status_code == 201
    assert post_res.json()["id"] == "my-homelab"

    # Verify added
    res2 = client.get("/api/catalog/sources", headers=admin_headers)
    assert any(s["id"] == "my-homelab" for s in res2.json())


def test_delete_catalog_source(catalog_client, admin_headers):
    client, _ = catalog_client
    # Delete non-existent
    del_res = client.delete("/api/catalog/sources/non-existent", headers=admin_headers)
    assert del_res.status_code == 404


def test_list_catalog_apps(catalog_client, admin_headers):
    client, _ = catalog_client
    res = client.get("/api/catalog/apps", headers=admin_headers)
    assert res.status_code == 200
    apps = res.json()
    assert len(apps) >= 4
    app_ids = [a["id"] for a in apps]
    assert "homeassistant" in app_ids
    assert "immich" in app_ids
    assert "vaultwarden" in app_ids


def test_get_catalog_app_detail(catalog_client, admin_headers):
    client, _ = catalog_client
    res = client.get("/api/catalog/apps/homeassistant", headers=admin_headers)
    assert res.status_code == 200
    app_data = res.json()
    assert app_data["name"] == "Home Assistant"
    assert app_data["ingress_preset"]["target_port"] == 8123


def test_install_catalog_app_with_edge_ingress(catalog_client, admin_headers):
    client, repo = catalog_client
    install_payload = {
        "app_id": "homeassistant",
        "catalog_id": "official",
        "expose_edge_ingress": True,
        "ingress_domain": "ha.familydomain.org",
        "custom_ports": {8123: 8123},
    }
    res = client.post("/api/catalog/apps/install", json=install_payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["plugin_id"] == "homeassistant"
    assert data["ingress_route_id"] is not None

    # Verify plugins were saved
    repo.save_plugins_config.assert_called_once()
    # Verify ingress route was saved to network config
    repo.save_network_config.assert_called_once()


def test_list_local_docker_images(catalog_client, admin_headers):
    client, _ = catalog_client
    res = client.get("/api/catalog/images", headers=admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
