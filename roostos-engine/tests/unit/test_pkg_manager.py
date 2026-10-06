"""Unit tests for the OS package manager abstraction."""

from roostos_engine.pkg_manager.models import PackageStatus, InstallResult
from roostos_engine.pkg_manager.apt import AptPackageManager
from roostos_engine.pkg_manager.dnf import DnfPackageManager
from roostos_engine.pkg_manager.detector import (
    detect_package_manager,
    check_feature_dependencies,
    check_all_dependencies,
)


def test_apt_package_manager_mock():
    mgr = AptPackageManager(mock=True)
    assert mgr.name == "apt"
    assert mgr.os_family == "debian"
    assert mgr.is_installed("kea-dhcp4-server") is True

    status = mgr.get_package_status("docker.io")
    assert status.installed is True
    assert status.version == "1.0.0-mock"

    res = mgr.install_packages(["docker.io"])
    assert res.success is True
    assert "docker.io" in res.installed


def test_dnf_package_manager_mock():
    mgr = DnfPackageManager(mock=True)
    assert mgr.name == "dnf"
    assert mgr.os_family == "redhat"
    assert mgr.is_installed("nftables") is True

    status = mgr.get_package_status("nftables")
    assert status.installed is True
    assert status.version == "1.0.0-mock"

    res = mgr.install_packages(["nftables"])
    assert res.success is True


def test_detect_package_manager_mock():
    mgr = detect_package_manager(mock=True)
    assert mgr.mock is True
    assert mgr.os_family in ("debian", "redhat")


def test_check_feature_dependencies():
    mgr = AptPackageManager(mock=True)
    report = check_feature_dependencies("dns_technitium", pkg_mgr=mgr)
    assert report.feature == "dns_technitium"
    assert report.satisfied is True
    assert any(p.name == "docker.io" for p in report.packages)


def test_check_all_dependencies():
    mgr = AptPackageManager(mock=True)
    summary = check_all_dependencies(pkg_mgr=mgr)
    assert summary.all_satisfied is True
    assert len(summary.reports) >= 4
    feature_names = [r.feature for r in summary.reports]
    assert "gateway" in feature_names
    assert "dns_local" in feature_names
    assert "dns_technitium" in feature_names
