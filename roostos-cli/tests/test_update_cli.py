"""Unit tests for roostos update CLI commands."""

from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from roostos_cli.main import cli
from roostos_engine.update_manager import UpdateCheckResult, UpdateInstallResult, AvailableUpdate


def test_cli_update_status():
    runner = CliRunner()
    fake_result = UpdateCheckResult(
        updates_available=3,
        security_updates=1,
        packages=[
            AvailableUpdate(package_name="openssh-server", current_version="1:9.2", new_version="1:9.3", is_security=True)
        ],
        reboot_required=True,
        last_check_time="2026-10-03T17:00:00Z",
    )

    with patch("roostos_cli.update_cmd.UpdateManager") as mock_cls:
        mock_mgr = MagicMock()
        mock_mgr.check_updates.return_value = fake_result
        mock_mgr.detect_package_manager.return_value = "apt"
        mock_mgr.get_next_reboot_window_time.return_value = "Sun at 03:00 UTC"
        mock_cls.return_value = mock_mgr

        res = runner.invoke(cli, ["update", "status"])
        assert res.exit_code == 0
        assert "RoostOS System Updates" in res.output
        assert "Updates Available: 3" in res.output
        assert "Security Updates:  1" in res.output
        assert "YES (System reboot pending)" in res.output
        assert "openssh-server" in res.output


def test_cli_update_check():
    runner = CliRunner()
    fake_result = UpdateCheckResult(updates_available=0, security_updates=0)

    with patch("roostos_cli.update_cmd.UpdateManager") as mock_cls:
        mock_mgr = MagicMock()
        mock_mgr.check_updates.return_value = fake_result
        mock_cls.return_value = mock_mgr

        res = runner.invoke(cli, ["update", "check"])
        assert res.exit_code == 0
        assert "System is up to date" in res.output


def test_cli_update_install():
    runner = CliRunner()
    fake_result = UpdateInstallResult(
        success=True,
        packages_updated=2,
        reboot_required=True,
        reboot_scheduled_for="Sun at 03:00 UTC",
        backup_path="/var/lib/roostos/backups/test.tar.gz",
    )

    with patch("roostos_cli.update_cmd.UpdateManager") as mock_cls:
        mock_mgr = MagicMock()
        mock_mgr.install_updates.return_value = fake_result
        mock_cls.return_value = mock_mgr

        res = runner.invoke(cli, ["update", "install"])
        assert res.exit_code == 0
        assert "Successfully installed updates" in res.output
        assert "Pre-update backup saved to" in res.output
        assert "Reboot scheduled for: Sun at 03:00 UTC" in res.output
