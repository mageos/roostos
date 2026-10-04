"""Unit tests for RoostOS UpdateManager."""

import os
import tarfile
import datetime
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from roostos_engine.models.system import SystemUpdatesConfig, SystemUpdatesRebootWindow
from roostos_engine.notifications import NotificationDispatcher
from roostos_engine.update_manager import UpdateManager, UpdateCheckResult, UpdateInstallResult


@pytest.fixture
def temp_config_dir(tmp_path):
    conf_dir = tmp_path / "roostos_conf"
    conf_dir.mkdir()
    (conf_dir / "system.yaml").write_text("system:\n  hostname: test\n")
    (conf_dir / "network.yaml").write_text("network:\n  interfaces: []\n")
    return str(conf_dir)


def test_update_manager_reboot_window_detection():
    cfg = SystemUpdatesConfig(
        reboot_window=SystemUpdatesRebootWindow(days=["Sun"], time="03:00")
    )
    mgr = UpdateManager(config=cfg)

    # 2026-10-04 is a Sunday
    matching_time = datetime.datetime(2026, 10, 4, 3, 15, tzinfo=datetime.timezone.utc)
    assert mgr.is_within_reboot_window(matching_time) is True

    # Same Sunday, wrong hour (14:00)
    wrong_hour = datetime.datetime(2026, 10, 4, 14, 0, tzinfo=datetime.timezone.utc)
    assert mgr.is_within_reboot_window(wrong_hour) is False

    # 2026-10-05 is a Monday
    wrong_day = datetime.datetime(2026, 10, 5, 3, 0, tzinfo=datetime.timezone.utc)
    assert mgr.is_within_reboot_window(wrong_day) is False


def test_update_manager_pre_update_backup(temp_config_dir):
    mgr = UpdateManager(config_dir=temp_config_dir)
    backup_path = mgr.create_pre_update_backup()

    assert backup_path is not None
    assert os.path.exists(backup_path)
    assert backup_path.endswith(".tar.gz")

    # Verify tar contents
    with tarfile.open(backup_path, "r:gz") as tar:
        names = tar.getnames()
        assert "system.yaml" in names
        assert "network.yaml" in names


def test_update_manager_reboot_required_detection():
    mgr = UpdateManager()
    with patch("os.path.exists") as mock_exists:
        mock_exists.side_effect = lambda p: p == "/var/run/reboot-required"
        assert mgr.is_reboot_required() is True

    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False
        assert mgr.is_reboot_required() is False


def test_update_manager_check_updates_apt():
    mgr = UpdateManager()

    fake_apt_output = (
        "Inst libc6 [2.36-9] (2.36-10 Debian:12/bookworm-updates [amd64])\n"
        "Inst linux-image-amd64 [6.1.1] (6.1.2 Debian-Security:12/bookworm-security [amd64])\n"
        "Conf libc6 (2.36-10 Debian:12/bookworm-updates [amd64])\n"
    )

    with patch.object(mgr, "detect_package_manager", return_value="apt"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=fake_apt_output, stderr=""
        )

        result = mgr.check_updates(refresh_cache=False)
        assert result.updates_available == 2
        assert result.security_updates == 1
        assert len(result.packages) == 2

        pkg_names = [p.package_name for p in result.packages]
        assert "libc6" in pkg_names
        assert "linux-image-amd64" in pkg_names

        sec_pkg = next(p for p in result.packages if p.package_name == "linux-image-amd64")
        assert sec_pkg.is_security is True


def test_update_manager_install_mock(temp_config_dir):
    mock_dispatcher = MagicMock(spec=NotificationDispatcher)
    mgr = UpdateManager(config_dir=temp_config_dir, dispatcher=mock_dispatcher)

    with patch.object(mgr, "detect_package_manager", return_value="mock"):
        result = mgr.install_updates()
        assert result.success is True
        assert result.packages_updated > 0
        assert result.backup_path is not None
        assert os.path.exists(result.backup_path)


def test_update_manager_install_failure():
    mock_dispatcher = MagicMock(spec=NotificationDispatcher)
    mgr = UpdateManager(dispatcher=mock_dispatcher)

    with patch.object(mgr, "detect_package_manager", return_value="apt"), \
         patch.object(mgr, "create_pre_update_backup", return_value="/tmp/test_backup.tar.gz"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=100, stdout="", stderr="DPKG lock error"
        )

        result = mgr.install_updates()
        assert result.success is False
        assert "DPKG lock error" in result.error
        assert mock_dispatcher.dispatch.call_count == 1
        payload = mock_dispatcher.dispatch.call_args[0][0]
        assert payload.severity == "critical"
        assert "Automatic Update Failed" in payload.title
