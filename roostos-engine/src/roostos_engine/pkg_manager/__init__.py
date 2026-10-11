"""OS-agnostic dependency and package manager abstraction for RoostOS."""

from roostos_engine.pkg_manager.models import (
    PackageStatus,
    DependencyReport,
    InstallResult,
    SystemDependenciesSummary,
)
from roostos_engine.pkg_manager.base import BasePackageManager
from roostos_engine.pkg_manager.apt import AptPackageManager
from roostos_engine.pkg_manager.dnf import DnfPackageManager
from roostos_engine.pkg_manager.detector import (
    FEATURE_DEPENDENCIES,
    detect_package_manager,
    get_feature_dependencies,
    check_feature_dependencies,
    check_all_dependencies,
)

__all__ = [
    "PackageStatus",
    "DependencyReport",
    "InstallResult",
    "SystemDependenciesSummary",
    "BasePackageManager",
    "AptPackageManager",
    "DnfPackageManager",
    "FEATURE_DEPENDENCIES",
    "detect_package_manager",
    "get_feature_dependencies",
    "check_feature_dependencies",
    "check_all_dependencies",
]
