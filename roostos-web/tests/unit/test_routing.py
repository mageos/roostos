import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.config import (
    RoostConfig, SystemSettings, SystemConfig, UserConfig,
    NetworkSettings, WifiSettings
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient

from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.auth import create_access_token

class DummyConfigRepository(ConfigRepository):
    def __init__(self):
        # We construct a minimal valid mock RoostConfig
        self.config = MagicMock(spec=RoostConfig)
        self.config.system = SystemSettings(hostname="test-host", domain="test-lan")
        self.config.users = []
        self.config.devices = []
        self.config.firewall = MagicMock()
        self.config.firewall.model_dump.return_value = {"schedules": []}
        self.config.network = NetworkSettings()
        self.config.wifi = WifiSettings()
        self.config.vpns = []
        self.config.plugins = []
        self.config.people = []
        self.config.buildings = []
        self.config.rooms = []

    def get_config(self) -> RoostConfig:
        return self.config

    def save_system_config(self, data: SystemConfig) -> None:
        self.config.system = data.system
        self.config.users = data.users

    def save_devices_config(self, data: any) -> None:
        pass

    def save_network_config(self, data: any) -> None:
        pass

    def save_schedules_config(self, data: any) -> None:
        pass

    def save_firewall_config(self, data: any) -> None:
        pass

    def save_plugins_config(self, data: any) -> None:
        pass


@pytest.fixture
def mock_dependencies():
    repo = DummyConfigRepository()
    dbus = AsyncMock(spec=RoostClient)
    dbus.get_active_leases.return_value = []
    
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus
    yield repo, dbus
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_get_system_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/system", headers=auth_headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["hostname"] == "test-host"
    assert json_data["domain"] == "test-lan"


def test_get_devices_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/devices", headers=auth_headers)
    assert response.status_code == 200
    json_data = response.json()
    assert "devices" in json_data
    assert "active_leases" in json_data
    assert "active_arp" in json_data


def test_get_network_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/network", headers=auth_headers)
    assert response.status_code == 200
    json_data = response.json()
    assert "network" in json_data
    assert "wifi" in json_data
    assert "vpns" in json_data


def test_post_network_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    payload = {
        "network": {
            "interfaces": [{"name": "eth0", "role": "wan", "dhcp": True}]
        },
        "wifi": {
            "access_points": []
        },
        "vpns": [
            {
                "id": "wg_vpn",
                "name": "My WG Connection",
                "type": "wireguard",
                "role": "client",
                "enabled": True,
                "config": {}
            }
        ]
    }
    response = client.post("/api/network", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_get_plugins_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/plugins", headers=auth_headers)
    assert response.status_code == 200
    assert "plugins" in response.json()


def test_post_plugins_install(mock_dependencies, auth_headers):
    client = TestClient(app)
    payload = {
        "id": "my-plugin",
        "name": "My Plugin",
        "image": "my-plugin-image:latest",
        "ui_entrypoint": None,
        "network_mode": "bridge"
    }
    response = client.post("/api/plugins", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_delete_plugin_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    repo, dbus = mock_dependencies
    mock_plugin = MagicMock()
    mock_plugin.id = "my-plugin"
    repo.config.plugins = [mock_plugin]
    
    response = client.delete("/api/plugins/my-plugin", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_get_people_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/people", headers=auth_headers)
    assert response.status_code == 200
    assert "people" in response.json()


def test_post_people_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    payload = {
        "id": "new-person",
        "name": "New Person",
        "dns_profile": "adult"
    }
    response = client.post("/api/people", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_delete_person_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    repo, dbus = mock_dependencies
    mock_person = MagicMock()
    mock_person.id = "new-person"
    repo.config.people = [mock_person]
    
    response = client.delete("/api/people/new-person", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_post_plugins_manifest(mock_dependencies, auth_headers):
    client = TestClient(app)
    payload = {
        "manifest_yaml": "id: my-manifest-plugin\nname: Manifest Plugin\nnetwork_mode: bridge\nui_entrypoint: null\ncontainers:\n  - name: test-c\n    image: test-img:latest\n"
    }
    response = client.post("/api/plugins/manifest", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_upload_plugin_zip(mock_dependencies, auth_headers, tmp_path):
    import io, zipfile, os
    client = TestClient(app)
    
    os.environ["ROOSTOS_WEB_ASSETS"] = str(tmp_path)
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        manifest_yaml = "id: test-zip-plugin\nname: Zip Plugin\nnetwork_mode: bridge\ncontainers:\n  - name: test-c\n    image: test-img:latest\n"
        zip_file.writestr("roostos-pod.yaml", manifest_yaml)
        zip_file.writestr("ui.js", "console.log('hello');")
        
    zip_buffer.seek(0)
    files = {"file": ("plugin.zip", zip_buffer, "application/zip")}
    
    try:
        response = client.post("/api/plugins/upload", files=files, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        dest_ui = tmp_path / "plugins" / "test-zip-plugin" / "ui.js"
        assert dest_ui.exists()
        assert dest_ui.read_text() == "console.log('hello');"
    finally:
        del os.environ["ROOSTOS_WEB_ASSETS"]


def test_plugin_known_services_endpoints(mock_dependencies, auth_headers):
    client = TestClient(app)
    repo, dbus = mock_dependencies

    # Test manifest endpoint with known_services
    payload = {
        "manifest_yaml": "id: my-manifest-plugin\nname: Manifest Plugin\nnetwork_mode: bridge\nui_entrypoint: null\ncontainers:\n  - name: test-c\n    image: test-img:latest\nknown_services:\n  - vpnClient\n"
    }
    response = client.post("/api/plugins/manifest", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify that the plugin registered in repository has the service
    plugin = repo.config.plugins[-1]
    assert plugin.id == "my-manifest-plugin"
    assert plugin.known_services == ["vpnClient"]

    # Test POST endpoint with manual known_services in body
    payload2 = {
        "id": "my-manual-plugin",
        "name": "Manual Plugin",
        "image": "test-img:latest",
        "known_services": ["dnsServer", "dnsFilter"]
    }
    response = client.post("/api/plugins", json=payload2, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    plugin2 = repo.config.plugins[-1]
    assert plugin2.id == "my-manual-plugin"
    assert plugin2.known_services == ["dnsServer", "dnsFilter"]


def test_operator_user_endpoints(mock_dependencies, auth_headers):
    client = TestClient(app)
    repo, dbus = mock_dependencies

    repo.config.users = [
        UserConfig(username="admin", role="admin")
    ]

    # 1. GET /api/users
    response = client.get("/api/users", headers=auth_headers)
    assert response.status_code == 200
    assert "users" in response.json()

    # 2. POST /api/users (Add new user)
    payload = {
        "username": "new_operator",
        "role": "parent",
        "person": None
    }
    response = client.post("/api/users", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify user exists in config
    assert any(u.username == "new_operator" for u in repo.config.users)

    # 3. DELETE /api/users/{username}
    response = client.delete("/api/users/new_operator", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert not any(u.username == "new_operator" for u in repo.config.users)


def test_dns_config_endpoints(mock_dependencies, auth_headers):
    client = TestClient(app)
    repo, dbus = mock_dependencies

    # 1. GET /api/dns/config
    response = client.get("/api/dns/config", headers=auth_headers)
    assert response.status_code == 200
    assert "forwarders" in response.json()
    assert "ad_blocking_enabled" in response.json()

    # 2. POST /api/dns/config
    payload = {
        "forwarders": ["1.1.1.1", "8.8.8.8"],
        "ad_blocking_enabled": True
    }
    response = client.post("/api/dns/config", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify settings stored in config
    assert repo.config.system.dns.forwarders == ["1.1.1.1", "8.8.8.8"]
    assert repo.config.system.dns.ad_blocking_enabled is True


def test_system_services_status_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/system/services", headers=auth_headers)
    assert response.status_code == 200
    services = response.json()
    assert isinstance(services, list)
    assert len(services) > 0
    assert any(s["id"] == "roostd" for s in services)


def test_firewall_blocks_endpoint(mock_dependencies, auth_headers):
    client = TestClient(app)
    response = client.get("/api/firewall/blocks", headers=auth_headers)
    assert response.status_code == 200
    blocks = response.json()
    assert isinstance(blocks, list)
    assert len(blocks) > 0
    assert "timestamp" in blocks[0]
    assert "rule" in blocks[0]



