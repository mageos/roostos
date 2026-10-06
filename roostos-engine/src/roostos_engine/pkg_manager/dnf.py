"""Red Hat Enterprise Linux and Fedora DNF/YUM package manager implementation."""

import os
import shutil
import subprocess
from typing import List

from roostos_engine.pkg_manager.base import BasePackageManager
from roostos_engine.pkg_manager.models import PackageStatus, InstallResult


class DnfPackageManager(BasePackageManager):
    """Package manager implementation utilizing rpm and dnf on Red Hat/Fedora systems."""

    @property
    def name(self) -> str:
        return "dnf"

    @property
    def os_family(self) -> str:
        return "redhat"

    def is_available(self) -> bool:
        return shutil.which("dnf") is not None or shutil.which("yum") is not None

    def is_installed(self, package: str) -> bool:
        if self.mock or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
            return True
        try:
            return subprocess.run(["rpm", "-q", package], capture_output=True).returncode == 0
        except Exception:
            return False

    def get_package_status(self, package: str) -> PackageStatus:
        if self.mock or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
            return PackageStatus(name=package, installed=True, version="1.0.0-mock")
        try:
            res = subprocess.run(["rpm", "-q", "--queryformat", "%{VERSION}-%{RELEASE}", package], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return PackageStatus(name=package, installed=True, version=res.stdout.strip())
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
        binary = "dnf" if shutil.which("dnf") else "yum"
        try:
            res = subprocess.run([binary, "install", "-y"] + needed, capture_output=True, text=True, timeout=300)
            if res.returncode == 0:
                return InstallResult(success=True, installed=needed, message=f"Successfully installed: {', '.join(needed)}")
            return InstallResult(success=False, failed=needed, message=f"{binary} install failed: {res.stderr.strip()}")
        except Exception as e:
            return InstallResult(success=False, failed=needed, message=f"Error executing {binary}: {e}")
