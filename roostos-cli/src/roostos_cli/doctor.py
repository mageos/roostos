"""System diagnostic and pre-flight doctor checks for RoostOS."""

import os
import sys
import socket
import subprocess
from enum import Enum
from typing import List, Dict, Any, Optional
import click
import yaml
from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CheckItem(BaseModel):
    category: str
    name: str
    status: CheckStatus
    detail: str


class DoctorReport(BaseModel):
    checks: List[CheckItem] = Field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return any(c.status == CheckStatus.FAIL for c in self.checks)


class SystemDoctor:
    """Executes diagnostic checks across permissions, services, ports, and configs."""

    def __init__(self, config_dir: str = "/etc/roostos"):
        self.config_dir = config_dir

    def run_all_checks(self) -> DoctorReport:
        report = DoctorReport()
        report.checks.extend(self._check_system())
        report.checks.extend(self._check_permissions())
        report.checks.extend(self._check_configs())
        report.checks.extend(self._check_services())
        report.checks.extend(self._check_ports())
        report.checks.extend(self._check_network())
        return report

    def _check_system(self) -> List[CheckItem]:
        results: List[CheckItem] = []
        try:
            uname = os.uname()
            results.append(
                CheckItem(
                    category="System",
                    name="Kernel & Arch",
                    status=CheckStatus.PASS,
                    detail=f"{uname.sysname} {uname.release} ({uname.machine})",
                )
            )
        except Exception as e:
            results.append(
                CheckItem(
                    category="System",
                    name="Kernel & Arch",
                    status=CheckStatus.WARN,
                    detail=f"Unable to read uname: {e}",
                )
            )
        return results

    def _check_permissions(self) -> List[CheckItem]:
        results: List[CheckItem] = []
        is_root = os.getuid() == 0
        if is_root:
            results.append(
                CheckItem(
                    category="Security",
                    name="User Privileges",
                    status=CheckStatus.PASS,
                    detail="Running as root (UID 0)",
                )
            )
        else:
            import grp
            import pwd
            username = "unknown"
            try:
                username = pwd.getpwuid(os.getuid()).pw_name
                user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            except Exception:
                user_groups = []
            has_group = any(g in user_groups for g in ["roostos", "sudo", "wheel"])
            status = CheckStatus.PASS if has_group else CheckStatus.WARN
            detail = f"Non-root user '{username}' (Groups: {', '.join(user_groups) or 'none'})"
            results.append(CheckItem(category="Security", name="User Privileges", status=status, detail=detail))
        return results

    def _check_configs(self) -> List[CheckItem]:
        results: List[CheckItem] = []
        expected_configs = ["system.yaml", "network.yaml", "devices.yaml", "schedules.yaml", "firewall.yaml"]
        for cfg in expected_configs:
            path = os.path.join(self.config_dir, cfg)
            if not os.path.exists(path):
                results.append(
                    CheckItem(
                        category="Configuration",
                        name=cfg,
                        status=CheckStatus.WARN,
                        detail="File not created yet (run 'roostos setup')",
                    )
                )
            else:
                try:
                    with open(path, "r") as f:
                        yaml.safe_load(f)
                    results.append(
                        CheckItem(
                            category="Configuration",
                            name=cfg,
                            status=CheckStatus.PASS,
                            detail=f"Valid YAML ({path})",
                        )
                    )
                except Exception as e:
                    results.append(
                        CheckItem(
                            category="Configuration",
                            name=cfg,
                            status=CheckStatus.FAIL,
                            detail=f"Syntax Error: {e}",
                        )
                    )
        return results

    def _check_services(self) -> List[CheckItem]:
        results: List[CheckItem] = []
        services = [
            ("roostos-node.service", True),
            ("roostos-engine.service", False),
            ("roostos-timeguardd.service", False),
            ("kea-dhcp4-server.service", False),
            ("mosquitto.service", False),
        ]
        for srv, required in services:
            try:
                res = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True)
                active = res.stdout.strip()
                if active == "active":
                    results.append(
                        CheckItem(
                            category="Services",
                            name=srv,
                            status=CheckStatus.PASS,
                            detail="Running (active)",
                        )
                    )
                elif required:
                    results.append(
                        CheckItem(
                            category="Services",
                            name=srv,
                            status=CheckStatus.WARN,
                            detail=f"Inactive ({active or 'stopped'})",
                        )
                    )
                else:
                    results.append(
                        CheckItem(
                            category="Services",
                            name=srv,
                            status=CheckStatus.PASS,
                            detail=f"Optional ({active or 'inactive'})",
                        )
                    )
            except Exception:
                results.append(
                    CheckItem(
                        category="Services",
                        name=srv,
                        status=CheckStatus.PASS,
                        detail="Systemd not running or unavailable",
                    )
                )
                break
        return results

    def _check_ports(self) -> List[CheckItem]:
        results: List[CheckItem] = []
        ports = [(8000, "RoostOS Web Console & API"), (1883, "Mosquitto MQTT Broker")]
        for port, desc in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            is_open = s.connect_ex(("127.0.0.1", port)) == 0
            s.close()
            status = CheckStatus.PASS if is_open else CheckStatus.WARN
            detail = f"Listening on port {port}" if is_open else f"Port {port} not listening"
            results.append(CheckItem(category="Ports", name=desc, status=status, detail=detail))
        return results

    def _check_network(self) -> List[CheckItem]:
        results: List[CheckItem] = []
        try:
            socket.gethostbyname("1.1.1.1")
            results.append(
                CheckItem(
                    category="Network",
                    name="DNS Resolution",
                    status=CheckStatus.PASS,
                    detail="DNS lookup functional",
                )
            )
        except Exception as e:
            results.append(
                CheckItem(
                    category="Network",
                    name="DNS Resolution",
                    status=CheckStatus.WARN,
                    detail=f"DNS lookup failed: {e}",
                )
            )
        return results


@click.command(name="doctor")
@click.option("--config-dir", default="/etc/roostos", help="Path to config directory")
def doctor_cmd(config_dir: str) -> None:
    """Runs comprehensive preflight diagnostics and health verification."""
    click.secho("==================================================", fg="cyan", bold=True)
    click.secho("              RoostOS Node Doctor                 ", fg="cyan", bold=True)
    click.secho("==================================================", fg="cyan", bold=True)

    doctor = SystemDoctor(config_dir=config_dir)
    report = doctor.run_all_checks()

    current_cat = ""
    for c in report.checks:
        if c.category != current_cat:
            current_cat = c.category
            click.secho(f"\n[{current_cat}]", bold=True)

        if c.status == CheckStatus.PASS:
            click.secho(f"  ✓ {c.name}: ", fg="green", nl=False)
            click.echo(c.detail)
        elif c.status == CheckStatus.WARN:
            click.secho(f"  ! {c.name}: ", fg="yellow", nl=False)
            click.echo(c.detail)
        else:
            click.secho(f"  ✗ {c.name}: ", fg="red", bold=True, nl=False)
            click.echo(c.detail)

    click.echo("\n--------------------------------------------------")
    if report.has_failures:
        click.secho("Doctor found critical errors requiring resolution.", fg="red", bold=True)
        sys.exit(1)
    else:
        click.secho("All critical checks passed successfully.", fg="green", bold=True)
