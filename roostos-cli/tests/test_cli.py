"""Unit tests for the RoostOS Click CLI commands."""

from click.testing import CliRunner
from roostos_cli.main import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "roostos" in result.output


def test_cli_status():
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "RoostOS Node Status" in result.output
    assert "Architecture:" in result.output


def test_cli_setup_non_interactive(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "setup",
        "--role", "gateway",
        "--wan", "eth0",
        "--lan", "eth1",
        "--subnet", "192.168.10.0/24",
        "--config-dir", str(tmp_path),
        "--mock",
        "--non-interactive",
    ])
    assert result.exit_code == 0
    assert "Gateway Router successfully configured" in result.output
    assert (tmp_path / "network.yaml").exists()
