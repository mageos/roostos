import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.config import (
    RoostConfig, SystemSettings, SystemConfig, NetworkSettings, WifiSettings
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_engine.models.providers import ProvidersSettings
from roostos_engine.models.firewall import FirewallSettings
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.auth import create_access_token
from roostos_web.di import create_web_injector, set_injector


class DummyConfigRepository(ConfigRepository):
    def __init__(self) -> None:
        self.config = MagicMock(spec=RoostConfig)
        self.config.system = SystemSettings(hostname="test-host", domain="test-lan")
        self.config.users = []
        self.config.devices = []
        self.config.firewall = FirewallSettings()
        self.config.network = NetworkSettings()
        self.config.wifi = WifiSettings()
        self.config.vpns = []
        self.config.plugins = []
        self.config.people = []
        self.config.buildings = []
        self.config.rooms = []
        self.config.nodes = []

    def get_config(self) -> RoostConfig:
        return self.config

    def save_system_config(self, data: SystemConfig) -> None:
        self.config.system = data.system
        self.config.users = data.users

    def save_nodes_config(self, data: Any) -> None:
        pass

    def save_devices_config(self, data: Any) -> None:
        pass

    def save_network_config(self, data: Any) -> None:
        pass

    def save_schedules_config(self, data: Any) -> None:
        pass

    def save_firewall_config(self, data: Any) -> None:
        if hasattr(data, "firewall"):
            self.config.firewall = data.firewall
        else:
            self.config.firewall = data

    def save_plugins_config(self, data: Any) -> None:
        pass


@pytest.fixture
def mock_dependencies(tmp_path: Any) -> Any:
    repo = DummyConfigRepository()
    dbus = AsyncMock(spec=RoostClient)
    dbus.get_active_leases.return_value = []

    injector = create_web_injector(
        config_dir=str(tmp_path),
        dbus_client=dbus,
        providers_settings=ProvidersSettings(
            auth_provider="mock", config_repository="memory", system_client="mock"
        ),
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    set_injector(injector)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus
    yield repo, dbus
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_api_v1_direct_access(mock_dependencies: Any, auth_headers: dict[str, str]) -> None:
    client = TestClient(app)
    # Direct /api/v1/ access
    resp = client.get("/api/v1/system", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["hostname"] == "test-host"

    resp_health = client.get("/api/v1/health")
    assert resp_health.status_code == 200
    assert "status" in resp_health.json()


def test_legacy_api_fallback_middleware(
    mock_dependencies: Any, auth_headers: dict[str, str]
) -> None:
    client = TestClient(app)
    # Legacy /api/ request without /v1/ should be rewritten by ApiV1FallbackMiddleware
    resp_legacy = client.get("/api/system", headers=auth_headers)
    assert resp_legacy.status_code == 200
    assert resp_legacy.json()["hostname"] == "test-host"

    # Both endpoints return equivalent system configuration
    resp_v1 = client.get("/api/v1/system", headers=auth_headers)
    assert resp_v1.status_code == 200
    assert resp_legacy.json()["hostname"] == resp_v1.json()["hostname"]
    assert resp_legacy.json()["domain"] == resp_v1.json()["domain"]


def test_openapi_schema_has_v1_routes() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = list(schema.get("paths", {}).keys())

    # Verify standard API endpoints are listed under /api/v1/
    v1_paths = [p for p in paths if p.startswith("/api/v1/")]
    assert len(v1_paths) > 20
    assert "/api/v1/system" in paths
    assert "/api/v1/devices" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/network" in paths
    assert "/api/v1/catalog/sources" in paths

    # Verify no unversioned /api/ routes are defined in OpenAPI except health
    unversioned_api_paths = [
        p for p in paths if p.startswith("/api/") and not p.startswith("/api/v1/")
    ]
    # Only /api/health was explicitly kept alongside /health and /api/v1/health
    assert set(unversioned_api_paths) <= {"/api/health"}
