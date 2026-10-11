"""Comprehensive system diagnostic and troubleshooting bundle collector for RoostOS."""

import json
import os
import re
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import click
from pydantic import BaseModel, Field


def _run_cmd(args: List[str], timeout: float = 3.0) -> str:
    """Executes a command safely, returning stripped stdout or empty string."""
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip() if res.returncode == 0 else (res.stderr.strip() or f"Error: code {res.returncode}")
    except Exception as e:
        return f"Unavailable: {e}"


def _redact_text(text: str) -> str:
    """Masks private keys, tokens, and secrets from configuration strings."""
    redacted = re.sub(r"(PrivateKey\s*=\s*)[^\n\r]+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    redacted = re.sub(r"(PresharedKey\s*=\s*)[^\n\r]+", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(password:\s*)[^\n\r]+", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(secret_key:\s*)[^\n\r]+", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    return re.sub(r"(token:\s*)[^\n\r]+", r"\1[REDACTED]", redacted, flags=re.IGNORECASE)


class DiagnosticReport(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    system: Dict[str, Any] = Field(default_factory=dict)
    network: Dict[str, Any] = Field(default_factory=dict)
    wireguard: Dict[str, Any] = Field(default_factory=dict)
    configs: Dict[str, Any] = Field(default_factory=dict)
    services: Dict[str, Any] = Field(default_factory=dict)
    logs: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticCollector:
    """Collects system telemetry, interfaces, WireGuard state, and configs for diagnosis."""

    def __init__(self, config_dir: str = "/etc/roostos"):
        self.config_dir = config_dir

    def collect(self) -> DiagnosticReport:
        report = DiagnosticReport()
        report.system = self._collect_system()
        report.network = self._collect_network()
        report.wireguard = self._collect_wireguard()
        report.configs = self._collect_configs()
        report.services = self._collect_services()
        report.logs = self._collect_logs()
        return report

    def _collect_system(self) -> Dict[str, Any]:
        uname = os.uname()
        os_release = {}
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            os_release[k] = v.strip('"')
            except Exception:
                pass

        return {
            "hostname": socket.gethostname(),
            "kernel": f"{uname.sysname} {uname.release}",
            "arch": uname.machine,
            "os_name": os_release.get("PRETTY_NAME", os_release.get("NAME", "Linux")),
            "systemd_version": _run_cmd(["systemctl", "--version"]).split("\n")[0],
            "uid": os.getuid(),
            "is_root": os.getuid() == 0,
        }

    def _collect_network(self) -> Dict[str, Any]:
        return {
            "links": _run_cmd(["ip", "-br", "link"]),
            "addresses": _run_cmd(["ip", "-br", "addr"]),
            "routes": _run_cmd(["ip", "route"]),
            "networkctl_list": _run_cmd(["networkctl", "list", "--no-pager"]),
            "networkctl_status": _run_cmd(["networkctl", "status", "--no-pager"]),
            "wg_edge_status": _run_cmd(["networkctl", "status", "wg-edge", "--no-pager"]),
        }

    def _collect_wireguard(self) -> Dict[str, Any]:
        has_module = os.path.exists("/sys/module/wireguard")
        wg_show_all = _run_cmd(["wg", "show", "all"])
        wg_show = _run_cmd(["wg", "show"])
        return {
            "kernel_module_loaded": has_module,
            "wg_version": _run_cmd(["wg", "--version"]),
            "wg_show_all": _redact_text(wg_show_all),
            "wg_show": _redact_text(wg_show),
        }

    def _collect_configs(self) -> Dict[str, Any]:
        configs: Dict[str, str] = {}
        # Collect /etc/roostos configs
        if os.path.exists(self.config_dir):
            for fname in os.listdir(self.config_dir):
                if fname.endswith((".yaml", ".yml")):
                    fpath = os.path.join(self.config_dir, fname)
                    try:
                        with open(fpath, "r") as f:
                            configs[f"roostos/{fname}"] = _redact_text(f.read())
                    except Exception as e:
                        configs[f"roostos/{fname}"] = f"Error reading: {e}"

        # Collect /etc/systemd/network WireGuard configs
        net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
        if os.path.exists(net_dir):
            for fname in os.listdir(net_dir):
                if "wg" in fname or fname.endswith((".netdev", ".network")):
                    fpath = os.path.join(net_dir, fname)
                    try:
                        with open(fpath, "r") as f:
                            configs[f"networkd/{fname}"] = _redact_text(f.read())
                    except Exception as e:
                        configs[f"networkd/{fname}"] = f"Error reading: {e}"

        return configs

    def _collect_services(self) -> Dict[str, Any]:
        svcs = ["roostos-node", "roostos-engine", "roostos-web", "systemd-networkd"]
        res = {}
        for s in svcs:
            active = _run_cmd(["systemctl", "is-active", s])
            status_text = _run_cmd(["systemctl", "status", s, "-n", "5", "--no-pager"])
            res[s] = {"active": active == "active", "state": active, "detail": status_text}
        return res

    def _collect_logs(self) -> Dict[str, str]:
        return {
            "systemd_networkd": _run_cmd(["journalctl", "-u", "systemd-networkd", "-n", "30", "--no-pager"]),
            "roostos_web": _run_cmd(["journalctl", "-u", "roostos-web", "-n", "30", "--no-pager"]),
            "roostos_engine": _run_cmd(["journalctl", "-u", "roostos-engine", "-n", "30", "--no-pager"]),
        }


def _render_terminal_summary(report: DiagnosticReport) -> None:
    """Renders formatted diagnostic overview to terminal."""
    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("           RoostOS Diagnostic Report              ", fg="cyan", bold=True)
    click.secho(f"Generated: {report.timestamp}", fg="cyan")
    click.secho("==================================================", fg="cyan", bold=True)

    sys_info = report.system
    click.secho("\n[System & Host]", bold=True)
    click.echo(f"  Hostname:  {sys_info.get('hostname')}")
    click.echo(f"  OS:        {sys_info.get('os_name')} ({sys_info.get('kernel')} - {sys_info.get('arch')})")
    priv_str = "root (UID 0)" if sys_info.get("is_root") else f"non-root (UID {sys_info.get('uid')})"
    click.echo(f"  Privilege: {priv_str}")

    click.secho("\n[RoostOS Services]", bold=True)
    for s_name, s_data in report.services.items():
        color = "green" if s_data.get("active") else "yellow"
        click.secho(f"  • {s_name}: ", nl=False)
        click.secho(s_data.get("state", "unknown"), fg=color, bold=True)

    click.secho("\n[WireGuard Subsystem]", bold=True)
    wg = report.wireguard
    click.echo(f"  Kernel Module Loaded: {'Yes' if wg.get('kernel_module_loaded') else 'No'}")
    wg_show = wg.get("wg_show", "").strip()
    if wg_show and not wg_show.startswith("Unavailable") and not wg_show.startswith("Error"):
        click.secho("  Active Tunnels:\n", fg="green")
        for line in wg_show.split("\n"):
            click.echo(f"    {line}")
    else:
        click.secho("  No active WireGuard interfaces found in 'wg show'.", fg="yellow")

    click.secho("\n[Network Interfaces]", bold=True)
    addrs = report.network.get("addresses", "").strip()
    if addrs:
        for line in addrs.split("\n"):
            click.echo(f"  {line}")

    click.secho("\n[Configuration Files Found]", bold=True)
    for c_path in sorted(report.configs.keys()):
        click.echo(f"  • {c_path}")


def _export_report(report: DiagnosticReport, export_path: str) -> None:
    """Writes diagnostic bundle to target file."""
    if export_path.endswith(".json"):
        with open(export_path, "w") as f:
            f.write(report.model_dump_json(indent=2))
    else:
        with open(export_path, "w") as f:
            f.write(f"# RoostOS Diagnostic Report\n# Timestamp: {report.timestamp}\n\n")
            f.write("## 1. System Information\n")
            f.write(json.dumps(report.system, indent=2) + "\n\n")
            f.write("## 2. WireGuard Status\n")
            f.write(f"Kernel Module: {report.wireguard.get('kernel_module_loaded')}\n")
            f.write(report.wireguard.get("wg_show", "None") + "\n\n")
            f.write("## 3. Network Interfaces & Routes\n")
            f.write(f"### Interfaces:\n{report.network.get('addresses', '')}\n")
            f.write(f"### Routes:\n{report.network.get('routes', '')}\n")
            f.write(f"### networkctl status wg-edge:\n{report.network.get('wg_edge_status', '')}\n\n")
            f.write("## 4. Configurations (Redacted)\n")
            for name, val in report.configs.items():
                f.write(f"### {name}:\n```\n{val}\n```\n\n")
            f.write("## 5. Recent Journal Logs\n")
            for sname, logs in report.logs.items():
                f.write(f"### Service: {sname}\n```\n{logs}\n```\n\n")


@click.command(name="diagnose")
@click.option("--export", "-o", "export_file", default=None, help="Export diagnostic bundle to file (e.g. diag.json or diag.txt)")
@click.option("--json", "json_format", is_flag=True, help="Output diagnostic report in JSON format to stdout")
@click.option("--config-dir", default="/etc/roostos", help="Path to RoostOS config directory")
def diagnose_cmd(export_file: Optional[str], json_format: bool, config_dir: str) -> None:
    """Collects detailed system, WireGuard, network, and service diagnostics for troubleshooting."""
    collector = DiagnosticCollector(config_dir=config_dir)
    report = collector.collect()

    if json_format:
        click.echo(report.model_dump_json(indent=2))
    else:
        _render_terminal_summary(report)

    if export_file:
        _export_report(report, export_file)
        click.echo("")
        click.secho(f"✓ Diagnostic report exported to: {export_file}", fg="green", bold=True)
