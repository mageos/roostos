"""OS detection and dependency report generation utilities."""

import os
import shutil
from typing import Dict, List, Optional

from roostos_engine.pkg_manager.base import BasePackageManager
from roostos_engine.pkg_manager.apt import AptPackageManager
from roostos_engine.pkg_manager.dnf import DnfPackageManager
from roostos_engine.pkg_manager.models import (
    DependencyReport,
    SystemDependenciesSummary,
)

FEATURE_DEPENDENCIES: Dict[str, List[str]] = {
    "gateway": ["nftables", "kea-dhcp4-server", "wireguard"],
    "dns_local": ["nftables"],
    "dns_technitium": ["docker.io"],
    "controller": ["mosquitto"],
    "workstation": ["sssd", "realmd", "adcli", "oddjob-mkhomedir"],
}


def detect_package_manager(mock: bool = False) -> BasePackageManager:
    """Detects host operating system and instantiates the matching package manager."""
    if mock or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
        return AptPackageManager(mock=True)

    os_release = "/etc/os-release"
    if os.path.exists(os_release):
        try:
            with open(os_release, "r") as f:
                content = f.read().lower()
            if any(k in content for k in ("id=fedora", "id=rhel", "id=centos", "id=rocky", "id_like=rhel", "id_like=fedora")):
                return DnfPackageManager(mock=False)
            if any(k in content for k in ("id=debian", "id=ubuntu", "id_like=debian", "id_like=ubuntu")):
                return AptPackageManager(mock=False)
        except Exception:
            pass

    if shutil.which("apt-get") or shutil.which("dpkg"):
        return AptPackageManager(mock=False)
    if shutil.which("dnf") or shutil.which("yum"):
        return DnfPackageManager(mock=False)

    return AptPackageManager(mock=False)


def get_feature_dependencies(feature: str) -> List[str]:
    """Retrieves required packages for a specific feature key."""
    return FEATURE_DEPENDENCIES.get(feature, [])


def check_feature_dependencies(feature: str, pkg_mgr: Optional[BasePackageManager] = None) -> DependencyReport:
    """Generates a dependency report for a single feature."""
    mgr = pkg_mgr or detect_package_manager()
    packages = get_feature_dependencies(feature)
    statuses = mgr.check_dependencies(packages)
    satisfied = all(s.installed for s in statuses) if statuses else True
    return DependencyReport(feature=feature, satisfied=satisfied, packages=statuses)


def check_all_dependencies(pkg_mgr: Optional[BasePackageManager] = None) -> SystemDependenciesSummary:
    """Evaluates all RoostOS feature dependencies and aggregates system status."""
    mgr = pkg_mgr or detect_package_manager()
    reports = [check_feature_dependencies(f, mgr) for f in FEATURE_DEPENDENCIES]
    all_sat = all(r.satisfied for r in reports)
    return SystemDependenciesSummary(
        os_family=mgr.os_family,
        manager_name=mgr.name,
        reports=reports,
        all_satisfied=all_sat,
    )
