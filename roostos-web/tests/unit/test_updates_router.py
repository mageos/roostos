"""Unit tests for system updates FastAPI router."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from roostos_web.main import app
from roostos_web.auth import get_current_admin, UserSession
from roostos_engine.models.system import SystemUpdatesConfig, SystemUpdatesRebootWindow
from roostos_engine.update_manager import UpdateManager, UpdateCheckResult, UpdateInstallResult, AvailableUpdate
from roostos_web.routers.updates import get_update_manager, set_update_manager
from roostos_web.services.base import get_repository


@pytest.fixture
def client():
    # Override auth dependency to simulate authenticated admin user
    app.dependency_overrides[get_current_admin] = lambda: UserSession(username="admin", role="admin")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_updates_status(client):
    mock_mgr = MagicMock(spec=UpdateManager)
    mock_mgr.check_updates.return_value = UpdateCheckResult(
        updates_available=2,
        security_updates=1,
        packages=[
            AvailableUpdate(package_name="curl", current_version="7.88", new_version="7.89", is_security=True)
        ],
        reboot_required=False,
        last_check_time="2026-10-03T17:00:00Z",
    )
    set_update_manager(mock_mgr)

    resp = client.get("/api/v1/system/updates/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["updates_available"] == 2
    assert data["security_updates"] == 1
    assert data["packages"][0]["package_name"] == "curl"


def test_check_updates_forces_refresh(client):
    mock_mgr = MagicMock(spec=UpdateManager)
    mock_mgr.check_updates.return_value = UpdateCheckResult(
        updates_available=0,
        security_updates=0,
        packages=[],
        reboot_required=False,
        last_check_time="2026-10-03T17:30:00Z",
    )
    set_update_manager(mock_mgr)

    with patch("roostos_web.services.events.event_publisher.publish") as mock_publish:
        resp = client.post("/api/v1/system/updates/check")
        assert resp.status_code == 200
        mock_mgr.check_updates.assert_called_once_with(refresh_cache=True)
        mock_publish.assert_called_once()


def test_install_updates(client):
    mock_mgr = MagicMock(spec=UpdateManager)
    mock_mgr.install_updates.return_value = UpdateInstallResult(
        success=True,
        packages_updated=3,
        reboot_required=True,
        reboot_scheduled_for="Sun at 03:00 UTC",
        backup_path="/var/lib/roostos/backups/test.tar.gz",
        output="Done",
    )
    set_update_manager(mock_mgr)

    with patch("roostos_web.services.events.event_publisher.publish") as mock_publish:
        resp = client.post("/api/v1/system/updates/install?security_only=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["packages_updated"] == 3
        assert data["reboot_required"] is True
        mock_publish.assert_called_once()


def test_updates_config_get_and_put(client):
    mock_mgr = MagicMock(spec=UpdateManager)
    initial_cfg = SystemUpdatesConfig(
        auto_install=True,
        auto_reboot=False,
        reboot_window=SystemUpdatesRebootWindow(days=["Sun"], time="04:00"),
    )
    mock_mgr.config = initial_cfg
    set_update_manager(mock_mgr)

    # GET config
    resp = client.get("/api/v1/system/updates/config")
    assert resp.status_code == 200
    assert resp.json()["auto_reboot"] is False

    # PUT config
    mock_repo = MagicMock()
    mock_conf = MagicMock()
    mock_repo.get_config.return_value = mock_conf

    with patch("roostos_web.routers.updates.get_repository", return_value=mock_repo):
        new_payload = {
            "auto_install": True,
            "auto_reboot": True,
            "security_only": True,
            "reboot_window": {"days": ["Sun", "Wed"], "time": "02:00"},
        }
        resp = client.put("/api/v1/system/updates/config", json=new_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_reboot"] is True
        assert data["security_only"] is True
        assert data["reboot_window"]["days"] == ["Sun", "Wed"]
