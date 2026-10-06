"""Debian and Ubuntu APT package manager implementation."""

import os
import shutil
import subprocess
from typing import List, Optional, Dict

from roostos_engine.pkg_manager.base import BasePackageManager
from roostos_engine.pkg_manager.models import PackageStatus, InstallResult

BINARY_HINTS: Dict[str, List[str]] = {
    "kea-dhcp4-server": ["kea-dhcp4", "/usr/sbin/kea-dhcp4", "/usr/bin/kea-dhcp4"],
    "docker.io": ["docker", "/usr/bin/docker"],
    "nftables": ["nft", "/usr/sbin/nft", "/usr/bin/nft"],
    "wireguard": ["wg", "/usr/bin/wg"],
    "mosquitto": ["mosquitto", "/usr/sbin/mosquitto", "/usr/bin/mosquitto"],
}


class AptPackageManager(BasePackageManager):
    """Package manager implementation utilizing dpkg and apt-get on Debian/Ubuntu."""

    @property
    def name(self) -> str:
        return "apt"

    @property
    def os_family(self) -> str:
        return "debian"

    def is_available(self) -> bool:
        return shutil.which("dpkg") is not None or shutil.which("apt-get") is not None

    def is_installed(self, package: str) -> bool:
        if self.mock or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
            return True
        for hint in BINARY_HINTS.get(package, []):
            if "/" in hint and os.path.exists(hint):
                return True
            if "/" not in hint and shutil.which(hint):
                return True
        try:
            res = subprocess.run(["dpkg", "-s", package], capture_output=True, text=True)
            return res.returncode == 0 and "Status: install ok installed" in res.stdout
        except Exception:
            return False

    def get_package_status(self, package: str) -> PackageStatus:
        if self.mock or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
            return PackageStatus(name=package, installed=True, version="1.0.0-mock")
        for hint in BINARY_HINTS.get(package, []):
            if ("/" in hint and os.path.exists(hint)) or ("/" not in hint and shutil.which(hint)):
                return PackageStatus(name=package, installed=True, version="binary")
        try:
            res = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}|${Version}", package],
                capture_output=True, text=True, timeout=5,
            )
            if res.returncode == 0 and "|" in res.stdout:
                status, ver = res.stdout.split("|", 1)
                return PackageStatus(name=package, installed="install ok installed" in status, version=ver.strip() or None)
        except Exception:
            pass
        return PackageStatus(name=package, installed=False, version=None)

    def install_packages(self, packages: List[str]) -> InstallResult:
        if not packages:
            return InstallResult(success=True, message="No packages specified.")
        if self.mock or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
            return InstallResult(success=True, installed=packages, message="Mock packages installed.")
        needed = [p for p in packages if not self.is_installed(p)]
        if not needed:
            return InstallResult(success=True, installed=[], message="All requested packages are already installed.")
        if os.getuid() != 0:
            return InstallResult(success=False, failed=needed, message="Root privileges are required to install packages.")
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=False, timeout=60)
            res = subprocess.run(
                ["apt-get", "install", "-y", "--no-install-recommends"] + needed,
                capture_output=True, text=True, timeout=300,
            )
            if res.returncode == 0:
                return InstallResult(success=True, installed=needed, message=f"Successfully installed: {', '.join(needed)}")
            return InstallResult(success=False, failed=needed, message=f"apt-get install failed: {res.stderr.strip()}")
        except Exception as e:
            return InstallResult(success=False, failed=needed, message=f"Error executing apt-get: {e}")
