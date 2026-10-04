"""Automated OS and security update manager for Debian (apt) and Arch (pacman)."""

import os
import re
import shutil
import tarfile
import subprocess
import datetime
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

from roostos_engine.models.system import SystemUpdatesConfig
from roostos_engine.notifications import NotificationDispatcher, NotificationPayload


class AvailableUpdate(BaseModel):
    """Details of a single package update available on the system."""
    package_name: str
    current_version: str
    new_version: str
    is_security: bool = False


class UpdateCheckResult(BaseModel):
    """Summary of available system and security updates."""
    updates_available: int = 0
    security_updates: int = 0
    packages: List[AvailableUpdate] = Field(default_factory=list)
    reboot_required: bool = False
    last_check_time: str = ""


class UpdateInstallResult(BaseModel):
    """Result of an update installation operation."""
    success: bool
    packages_updated: int = 0
    reboot_required: bool = False
    reboot_scheduled_for: Optional[str] = None
    backup_path: Optional[str] = None
    output: str = ""
    error: Optional[str] = None


DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class UpdateManager:
    """Manages system package updates, security patches, backups, and reboot windows."""

    def __init__(
        self,
        config: Optional[SystemUpdatesConfig] = None,
        config_dir: str = "/etc/roostos",
        dispatcher: Optional[NotificationDispatcher] = None,
    ) -> None:
        self.config = config or SystemUpdatesConfig()
        self.config_dir = config_dir
        self.dispatcher = dispatcher

    def detect_package_manager(self) -> str:
        """Detects whether host uses apt, pacman, or mock mode."""
        if shutil.which("apt-get") or os.path.exists("/etc/debian_version"):
            return "apt"
        elif shutil.which("pacman") or os.path.exists("/etc/arch-release"):
            return "pacman"
        return "mock"

    def is_reboot_required(self) -> bool:
        """Checks if kernel or system libc updates require a host reboot."""
        return os.path.exists("/var/run/reboot-required")

    def create_pre_update_backup(self) -> Optional[str]:
        """Creates a timestamped tar archive backup of config_dir prior to updates."""
        try:
            backup_dir = "/var/lib/roostos/backups"
            try:
                os.makedirs(backup_dir, exist_ok=True)
            except Exception:
                backup_dir = os.path.join(self.config_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)

            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"roostos-pre-update-{now_str}.tar.gz")

            with tarfile.open(backup_file, "w:gz") as tar:
                for item in os.listdir(self.config_dir):
                    if item.endswith(".yaml") or item.endswith(".json"):
                        tar.add(os.path.join(self.config_dir, item), arcname=item)

            return backup_file
        except Exception:
            return None

    def is_within_reboot_window(self, now: Optional[datetime.datetime] = None) -> bool:
        """Determines if the current system time falls within the configured reboot window."""
        t = now or datetime.datetime.now(datetime.timezone.utc)
        current_day = DAY_ABBR[t.weekday()]
        if current_day not in self.config.reboot_window.days:
            return False

        try:
            win_parts = self.config.reboot_window.time.split(":")
            win_hour = int(win_parts[0])
            return t.hour == win_hour
        except Exception:
            return False

    def get_next_reboot_window_time(self, now: Optional[datetime.datetime] = None) -> str:
        """Returns the formatted description of the next reboot window occurrence."""
        days = ", ".join(self.config.reboot_window.days)
        return f"{days} at {self.config.reboot_window.time} UTC"

    def check_updates(self, refresh_cache: bool = True) -> UpdateCheckResult:
        """Queries the native package manager for available updates."""
        pkg_mgr = self.detect_package_manager()
        packages: List[AvailableUpdate] = []
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if pkg_mgr == "apt":
            if refresh_cache:
                try:
                    subprocess.run(["apt-get", "update"], capture_output=True, timeout=60)
                except Exception:
                    pass

            try:
                res = subprocess.run(
                    ["apt-get", "-s", "dist-upgrade"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                # Parse: Inst package [current] (new ...)
                for line in res.stdout.splitlines():
                    if line.startswith("Inst "):
                        parts = line.split()
                        pkg_name = parts[1]
                        cur_ver = parts[2].strip("[]") if len(parts) > 2 else "installed"
                        new_ver = parts[3].strip("()") if len(parts) > 3 else "unknown"
                        is_sec = "-security" in line or "security" in line.lower()
                        packages.append(AvailableUpdate(
                            package_name=pkg_name,
                            current_version=cur_ver,
                            new_version=new_ver,
                            is_security=is_sec,
                        ))
            except Exception:
                pass
        elif pkg_mgr == "pacman":
            try:
                res = subprocess.run(["checkupdates"], capture_output=True, text=True, timeout=30)
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        packages.append(AvailableUpdate(
                            package_name=parts[0],
                            current_version=parts[1],
                            new_version=parts[3] if len(parts) > 3 else parts[2],
                            is_security=False,
                        ))
            except Exception:
                pass

        sec_count = sum(1 for p in packages if p.is_security)
        self.config.last_check_time = now_iso
        return UpdateCheckResult(
            updates_available=len(packages),
            security_updates=sec_count,
            packages=packages,
            reboot_required=self.is_reboot_required(),
            last_check_time=now_iso,
        )

    def install_updates(self, security_only: bool = False) -> UpdateInstallResult:
        """Applies available package updates with automated pre-backup and reboot scheduling."""
        pkg_mgr = self.detect_package_manager()
        backup_path = self.create_pre_update_backup()

        if pkg_mgr == "mock":
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.config.last_install_time = now_iso
            return UpdateInstallResult(
                success=True,
                packages_updated=2,
                reboot_required=False,
                backup_path=backup_path,
                output="Mock package updates installed successfully.",
            )

        cmd: List[str] = []
        env = dict(os.environ)
        if pkg_mgr == "apt":
            env["DEBIAN_FRONTEND"] = "noninteractive"
            cmd = ["apt-get", "dist-upgrade", "-y", "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold"]
        elif pkg_mgr == "pacman":
            cmd = ["pacman", "-Syu", "--noconfirm"]

        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=900)
            if res.returncode != 0:
                if self.dispatcher:
                    self.dispatcher.dispatch(NotificationPayload(
                        alert_id="update_failure:system",
                        rule_id="update_failure",
                        title="Automatic Update Failed",
                        message=f"Package upgrade failed with exit code {res.returncode}:\n{res.stderr[:200]}",
                        severity="critical",
                        state="firing",
                    ))
                return UpdateInstallResult(
                    success=False,
                    backup_path=backup_path,
                    output=res.stdout,
                    error=res.stderr,
                )

            reboot_req = self.is_reboot_required()
            scheduled_reboot = None
            if reboot_req and self.config.auto_reboot:
                if self.is_within_reboot_window():
                    subprocess.Popen(["systemctl", "reboot"])
                else:
                    scheduled_reboot = self.get_next_reboot_window_time()

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.config.last_install_time = now_iso

            if self.dispatcher and (scheduled_reboot or reboot_req):
                self.dispatcher.dispatch(NotificationPayload(
                    alert_id="update_success:reboot",
                    rule_id="update_reboot",
                    title="System Updates Installed",
                    message=f"Updates applied. Reboot scheduled for {scheduled_reboot}" if scheduled_reboot else "Updates applied. System reboot required.",
                    severity="info",
                    state="firing",
                ))

            return UpdateInstallResult(
                success=True,
                packages_updated=1,
                reboot_required=reboot_req,
                reboot_scheduled_for=scheduled_reboot,
                backup_path=backup_path,
                output=res.stdout,
            )
        except Exception as e:
            return UpdateInstallResult(
                success=False,
                backup_path=backup_path,
                error=str(e),
            )
