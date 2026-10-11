"""Unit tests for roostos diagnose / diag command and collector."""

import json
import os
from click.testing import CliRunner
from roostos_cli.main import cli
from roostos_cli.diagnose import _redact_text, DiagnosticCollector


def test_redact_sensitive_strings():
    raw = (
        "PrivateKey = aabbccddeeff11223344556677889900\n"
        "PresharedKey = 00112233445566778899aabbccddeeff\n"
        "password: supersecretpassword\n"
        "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\n"
        "AllowedIPs = 10.42.0.0/24\n"
    )
    redacted = _redact_text(raw)
    assert "[REDACTED]" in redacted
    assert "supersecretpassword" not in redacted
    assert "aabbccddeeff" not in redacted
    assert "AllowedIPs = 10.42.0.0/24" in redacted


def test_diagnose_cli_terminal_summary():
    runner = CliRunner()
    result = runner.invoke(cli, ["diagnose"])
    assert result.exit_code == 0
    assert "RoostOS Diagnostic Report" in result.output
    assert "[System & Host]" in result.output
    assert "[RoostOS Services]" in result.output
    assert "[WireGuard Subsystem]" in result.output


def test_diagnose_cli_json_mode():
    runner = CliRunner()
    result = runner.invoke(cli, ["diagnose", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "system" in data
    assert "hostname" in data["system"]
    assert "network" in data
    assert "wireguard" in data
    assert "configs" in data
    assert "services" in data
    assert "logs" in data


def test_diagnose_cli_alias_diag():
    runner = CliRunner()
    result = runner.invoke(cli, ["diag", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "system" in data


def test_diagnose_cli_export(tmp_path):
    export_json = str(tmp_path / "export_diag.json")
    export_txt = str(tmp_path / "export_diag.txt")
    runner = CliRunner()

    res_json = runner.invoke(cli, ["diagnose", "--export", export_json])
    assert res_json.exit_code == 0
    assert os.path.exists(export_json)
    with open(export_json, "r") as f:
        data = json.load(f)
    assert "timestamp" in data

    res_txt = runner.invoke(cli, ["diagnose", "-o", export_txt])
    assert res_txt.exit_code == 0
    assert os.path.exists(export_txt)
    with open(export_txt, "r") as f:
        txt = f.read()
    assert "# RoostOS Diagnostic Report" in txt
