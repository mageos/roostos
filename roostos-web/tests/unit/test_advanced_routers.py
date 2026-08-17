import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from roostos_engine.repository import ConfigRepository, StagingConfigRepository
from roostos_engine.models.providers import ProvidersSettings
from roostos_sdk.client import RoostClient
from roostos_web.main import app, get_repository, get_dbus_client
from roostos_web.di import create_web_injector, set_injector
from roostos_web.auth import create_access_token

@pytest.fixture
def mock_staging_repo(tmp_path):
    repo = MagicMock(spec=StagingConfigRepository)
    repo.staged_dir = str(tmp_path / "staged")
    repo.has_staged_changes.return_value = True
    repo.active_repo = MagicMock()
    repo.active_repo.config_dir = str(tmp_path / "active")
    
    dbus = AsyncMock()

    injector = create_web_injector(
        config_dir=str(tmp_path),
        providers_settings=ProvidersSettings(auth_provider="mock", config_repository="staging", system_client="mock")
    )
    injector.binder.bind(ConfigRepository, to=repo)
    injector.binder.bind(RoostClient, to=dbus)
    set_injector(injector)
    
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_dbus_client] = lambda: dbus
    yield repo, dbus
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def parent_auth_headers():
    token = create_access_token({"sub": "parent", "role": "parent"})
    return {"Authorization": f"Bearer {token}"}

def test_guest_wifi_creation(mock_staging_repo, auth_headers):
    repo, dbus = mock_staging_repo
    client = TestClient(app)
    
    from roostos_engine.config import RoostConfig, NetworkConfig, NetworkSettings, WifiSettings
    mock_config = MagicMock(spec=RoostConfig)
    net_config = NetworkConfig(
        network=NetworkSettings(bridges=[]),
        wifi=WifiSettings(access_points=[]),
        vpns=[]
    )
    mock_config.network = net_config
    repo.get_config.return_value = mock_config

    payload = {"ssid": "Guest_AP", "passphrase": "supersecurepass", "subnet": "192.168.10.0/24"}
    res = client.post("/api/wifi/guest/create", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert "Guest_AP" in res.json()["message"]
    assert repo.save_network_config.called

def test_diagnostics_endpoints(mock_staging_repo, parent_auth_headers):
    client = TestClient(app)
    
    # Test ping (parent has access)
    res = client.post("/api/diagnostics/ping", json={"host": "8.8.8.8", "count": 2}, headers=parent_auth_headers)
    assert res.status_code == 200
    assert "status" in res.json()

    # Test DNS Resolution
    res = client.post("/api/diagnostics/dns-lookup", json={"host": "google.com"}, headers=parent_auth_headers)
    assert res.status_code == 200
    assert "status" in res.json()

    # Test shell command injection validation
    res = client.post("/api/diagnostics/ping", json={"host": "8.8.8.8; rm -rf /", "count": 2}, headers=parent_auth_headers)
    assert res.status_code == 400

def test_log_viewer_endpoint(mock_staging_repo, auth_headers, parent_auth_headers):
    client = TestClient(app)
    
    # Test admin can read logs
    res = client.get("/api/diagnostics/logs?service=roostd&limit=5", headers=auth_headers)
    assert res.status_code == 200
    assert "logs" in res.json()

    # Test parent cannot read logs (forbidden role)
    res = client.get("/api/diagnostics/logs?service=roostd&limit=5", headers=parent_auth_headers)
    assert res.status_code == 403

    # Test non-permitted service
    res = client.get("/api/diagnostics/logs?service=nginx&limit=5", headers=auth_headers)
    assert res.status_code == 400

def test_staging_endpoints(mock_staging_repo, auth_headers):
    repo, dbus = mock_staging_repo
    client = TestClient(app)
    
    # GET staged status
    res = client.get("/api/config/staged", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["has_staged_changes"] is True

    # POST discard
    res = client.post("/api/config/discard", headers=auth_headers)
    assert res.status_code == 200
    assert repo.discard_staged_changes.called
