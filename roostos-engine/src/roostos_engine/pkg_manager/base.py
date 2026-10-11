"""Abstract base class for OS-agnostic package and dependency managers."""

from abc import ABC, abstractmethod
from typing import List
from roostos_engine.pkg_manager.models import PackageStatus, InstallResult


class BasePackageManager(ABC):
    """Abstract contract for operating-system package managers (apt, dnf, pacman)."""

    def __init__(self, mock: bool = False):
        self.mock = mock

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the package manager (e.g. 'apt', 'dnf')."""
        pass

    @property
    @abstractmethod
    def os_family(self) -> str:
        """Target operating system family (e.g. 'debian', 'redhat')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying package manager tools exist on the system."""
        pass

    @abstractmethod
    def is_installed(self, package: str) -> bool:
        """Returns True if the specified package or its primary binary is installed."""
        pass

    @abstractmethod
    def get_package_status(self, package: str) -> PackageStatus:
        """Retrieves installed status and version for a given package."""
        pass

    def check_dependencies(self, packages: List[str]) -> List[PackageStatus]:
        """Evaluates installation status for a list of required packages."""
        return [self.get_package_status(pkg) for pkg in packages]

    @abstractmethod
    def install_packages(self, packages: List[str]) -> InstallResult:
        """Installs the requested packages using system package manager."""
        pass
