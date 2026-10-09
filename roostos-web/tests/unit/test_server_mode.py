import os
import pytest
from fastapi.testclient import TestClient
from roostos_web.main import determine_server_mode, create_app


def test_determine_server_mode_defaults():
    mode = determine_server_mode(config_dir="/nonexistent/dir", explicit_mode=None)
    assert mode == "full"


def test_determine_server_mode_explicit():
    assert determine_server_mode(explicit_mode="edge") == "edge_gateway"
    assert determine_server_mode(explicit_mode="edge_gateway") == "edge_gateway"
    assert determine_server_mode(explicit_mode="limited") == "edge_gateway"
    assert determine_server_mode(explicit_mode="api_only") == "api_only"


def test_determine_server_mode_env(monkeypatch):
    monkeypatch.setenv("ROOSTOS_MODE", "edge_gateway")
    assert determine_server_mode() == "edge_gateway"

    monkeypatch.setenv("ROOSTOS_ROLE", "edge")
    monkeypatch.delenv("ROOSTOS_MODE")
    assert determine_server_mode() == "edge_gateway"


def test_determine_server_mode_system_yaml(tmp_path):
    sys_file = tmp_path / "system.yaml"
    sys_file.write_text("system:\n  cluster:\n    roles:\n      - edge_gateway\n")
    mode = determine_server_mode(config_dir=str(tmp_path))
    assert mode == "edge_gateway"


def test_create_app_edge_gateway_mode():
    app = create_app(mode="edge_gateway")
    assert app.state.mode == "edge_gateway"
    assert app.state.no_ui is True
    assert app.title == "RoostOS Edge Gateway API"

    client = TestClient(app)

    # Health check is available
    res = client.get("/health")
    assert res.status_code == 200

    # Edge enrollment route exists
    res = client.post("/api/edge/enroll", json={})
    # 403 or 422 because token missing/invalid, NOT 404
    assert res.status_code in (403, 422)

    # Internal router and management endpoints are NOT mounted (return 404)
    res_devices = client.get("/api/devices")
    assert res_devices.status_code == 404

    res_setup = client.get("/api/setup/status")
    assert res_setup.status_code == 404

    res_auth = client.post("/api/auth/login", json={})
    assert res_auth.status_code == 404

    # Web UI root is NOT mounted
    res_root = client.get("/")
    assert res_root.status_code == 404


def test_create_app_api_only_mode():
    app = create_app(mode="api_only")
    assert app.state.mode == "api_only"
    assert app.state.no_ui is True

    client = TestClient(app)

    # Root UI is not mounted
    res = client.get("/")
    assert res.status_code == 404

    # API routes are mounted
    res_health = client.get("/health")
    assert res_health.status_code == 200
