"""Unit tests for telemetry and alerts FastAPI routers."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from roostos_web.main import app
from roostos_web.auth import get_current_user, UserSession
from roostos_engine.telemetry_manager import TelemetryManager
from roostos_engine.telemetry_collector import TelemetryCollector
from roostos_engine.alert_manager import AlertManager, ActiveAlert
from roostos_web.routers.telemetry import get_telemetry_manager, get_telemetry_collector
from roostos_web.routers.alerts import get_alert_manager, set_alert_manager


@pytest.fixture
def client():
    # Override auth dependency to simulate authenticated admin user
    app.dependency_overrides[get_current_user] = lambda: UserSession(username="admin", role="admin")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_telemetry_health_endpoint(client):
    mock_mgr = MagicMock(spec=TelemetryManager)
    mock_mgr.is_healthy.return_value = True
    mock_mgr.is_binary_available.return_value = True
    mock_mgr.base_url = "http://127.0.0.1:8428"

    app.dependency_overrides[get_telemetry_manager] = lambda: mock_mgr

    resp = client.get("/api/v1/telemetry/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["healthy"] is True
    assert data["binary_installed"] is True
    assert data["base_url"] == "http://127.0.0.1:8428"


def test_telemetry_query_endpoint(client):
    mock_mgr = MagicMock(spec=TelemetryManager)
    mock_mgr.query_instant.return_value = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{"metric": {"node": "node-01"}, "value": [1700000000, "15.0"]}],
        }
    }
    app.dependency_overrides[get_telemetry_manager] = lambda: mock_mgr

    resp = client.get("/api/v1/telemetry/query?query=system_cpu_usage_percent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    mock_mgr.query_instant.assert_called_once_with("system_cpu_usage_percent", timestamp=None)


def test_telemetry_collect_endpoint(client):
    mock_collector = MagicMock(spec=TelemetryCollector)
    mock_collector.collect_and_push.return_value = (True, 12)
    app.dependency_overrides[get_telemetry_collector] = lambda: mock_collector

    resp = client.post("/api/v1/telemetry/collect")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "samples_collected": 12}


def test_alerts_endpoints(client):
    mock_alert_mgr = MagicMock(spec=AlertManager)
    fake_alert = ActiveAlert(
        id="disk_critical:node-01",
        rule_id="disk_critical",
        title="Disk Usage Critical",
        message="Disk is 94% full",
        severity="critical",
        node_id="node-01",
        state="firing",
        value=94.0,
        fired_at="2026-10-03T17:00:00Z",
    )
    mock_alert_mgr.get_active_alerts.return_value = [fake_alert]
    mock_alert_mgr.get_alert_history.return_value = [fake_alert]
    mock_alert_mgr.rules = []
    mock_alert_mgr.acknowledge_alert.return_value = True
    mock_alert_mgr.evaluate_rules.return_value = [fake_alert]

    set_alert_manager(mock_alert_mgr)

    # Active alerts
    resp = client.get("/api/v1/alerts/active")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "disk_critical:node-01"

    # History
    resp = client.get("/api/v1/alerts/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Acknowledge
    resp = client.post("/api/v1/alerts/disk_critical:node-01/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Evaluate
    resp = client.post("/api/v1/alerts/evaluate")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
