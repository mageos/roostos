"""Unit tests for extended RoostOS CLI commands."""

import yaml
from pathlib import Path
from click.testing import CliRunner
from roostos_cli.main import cli


def test_cli_doctor(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "RoostOS Node Doctor" in result.output
    assert "[System]" in result.output
    assert "[Security]" in result.output


def test_cli_service_list() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["service", "list"])
    assert result.exit_code == 0
    assert "roostos-node.service" in result.output
    assert "SERVICE" in result.output


def test_cli_net_list(tmp_path: Path) -> None:
    net_yaml = tmp_path / "network.yaml"
    net_yaml.write_text(
        yaml.dump({
            "network": {
                "interfaces": [{"name": "eth0", "role": "wan"}],
                "bridges": [{"name": "br0", "ip": "192.168.1.1/24"}],
            }
        })
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["net", "list", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "INTERFACE" in result.output


def test_cli_dhcp_reserve(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [
        "dhcp", "reserve",
        "aa:bb:cc:dd:ee:ff",
        "192.168.1.150",
        "--name", "Office-Printer",
        "--config-dir", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "Static reservation saved" in result.output

    dev_file = tmp_path / "devices.yaml"
    assert dev_file.exists()
    data = yaml.safe_load(dev_file.read_text())
    assert any(d["mac"] == "aa:bb:cc:dd:ee:ff" and d["static_ip"] == "192.168.1.150" for d in data["devices"])


def test_cli_fw_forward(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [
        "fw", "forward",
        "8080", "192.168.1.50", "80",
        "--proto", "tcp",
        "--name", "Web-Forward",
        "--config-dir", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "Port forward rule saved" in result.output

    fw_file = tmp_path / "firewall.yaml"
    assert fw_file.exists()
    data = yaml.safe_load(fw_file.read_text())
    forwards = data["firewall"]["port_forwards"]
    assert any((f.get("wan_port") == 8080 or f.get("external_port") == 8080) and f.get("name") == "Web-Forward" for f in forwards)

    # Verify status command reads from firewall.yaml
    status_res = runner.invoke(cli, ["fw", "status", "--config-dir", str(tmp_path)])
    assert status_res.exit_code == 0
    assert "Web-Forward" in status_res.output


def test_cli_cluster_adopt_and_list(tmp_path: Path) -> None:
    runner = CliRunner()
    res_adopt = runner.invoke(cli, [
        "cluster", "adopt",
        "192.168.1.200",
        "--name", "Satellite-Node",
        "--role", "compute_node",
        "--config-dir", str(tmp_path),
    ])
    assert res_adopt.exit_code == 0
    assert "adopted into cluster" in res_adopt.output

    res_list = runner.invoke(cli, ["cluster", "list", "--config-dir", str(tmp_path)])
    assert res_list.exit_code == 0
    assert "Satellite-Node" in res_list.output
    assert "192.168.1.200" in res_list.output


def test_cli_devices_and_people(tmp_path: Path) -> None:
    dev_file = tmp_path / "devices.yaml"
    dev_file.write_text(
        yaml.dump({
            "devices": [
                {"id": "dev-01", "name": "Tablet", "mac": "11:22:33:44:55:66", "paused": False}
            ],
            "people": [
                {"id": "user-01", "name": "Charlie", "role": "child", "devices": ["dev-01"]}
            ]
        })
    )

    runner = CliRunner()
    res_dev = runner.invoke(cli, ["devices", "list", "--config-dir", str(tmp_path)])
    assert res_dev.exit_code == 0
    assert "Tablet" in res_dev.output

    res_pause = runner.invoke(cli, ["devices", "pause", "dev-01", "--config-dir", str(tmp_path)])
    assert res_pause.exit_code == 0
    assert "paused" in res_pause.output

    res_resume = runner.invoke(cli, ["devices", "resume", "dev-01", "--config-dir", str(tmp_path)])
    assert res_resume.exit_code == 0
    assert "resumed" in res_resume.output

    res_people = runner.invoke(cli, ["people", "list", "--config-dir", str(tmp_path)])
    assert res_people.exit_code == 0
    assert "Charlie" in res_people.output
