"""Unit tests for RoostOS version resolution and scripts/version.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from roostos_cli import _resolve_version, __version__
from roostos_cli.main import cli

# Import version module directly from repo scripts
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import version as version_script  # type: ignore


def test_get_major_version(tmp_path: Path) -> None:
    """Test reading major version from MAJOR_VERSION file."""
    assert version_script.get_major_version(tmp_path) == 0

    (tmp_path / "MAJOR_VERSION").write_text("1\n", encoding="utf-8")
    assert version_script.get_major_version(tmp_path) == 1

    (tmp_path / "MAJOR_VERSION").write_text("invalid", encoding="utf-8")
    assert version_script.get_major_version(tmp_path) == 0


def test_compute_version_override(monkeypatch) -> None:
    """Test ROOSTOS_VERSION explicit environment override."""
    monkeypatch.setenv("ROOSTOS_VERSION", "2.5.0-custom")
    ver = version_script.compute_version(REPO_ROOT)
    assert ver == "2.5.0-custom"


def test_compute_version_tag(monkeypatch) -> None:
    """Test version resolution from GitHub tag release ref."""
    monkeypatch.setenv("GITHUB_REF", "refs/tags/v1.0.5")
    ver = version_script.compute_version(REPO_ROOT)
    assert ver == "1.0.5"


def test_compute_version_on_main(monkeypatch) -> None:
    """Test simulated build on main branch generates {major}.{count}."""
    monkeypatch.delenv("ROOSTOS_VERSION", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    ver = version_script.compute_version(REPO_ROOT)
    assert ver.startswith("0.")
    assert "a" not in ver
    minor_part = ver.split(".")[1]
    assert minor_part.isdigit()
    assert int(minor_part) >= 12


def test_compute_version_on_feature_branch(monkeypatch) -> None:
    """Test simulated build on feature branch generates {major}.{next_main}a{alpha}."""
    monkeypatch.delenv("ROOSTOS_VERSION", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    monkeypatch.setenv("GITHUB_REF_NAME", "feature/awesome-upgrade")

    ver = version_script.compute_version(REPO_ROOT)
    assert ver.startswith("0.")
    assert "a" in ver
    base, alpha = ver.split("a")
    next_minor = base.split(".")[1]
    assert next_minor.isdigit()
    assert int(next_minor) >= 13
    assert alpha.isdigit()
    assert int(alpha) >= 1


def test_version_script_cli_invocation(tmp_path: Path) -> None:
    """Test version.py CLI arguments --major and --write."""
    # Test --major
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "version.py"), "--major"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert res.stdout.strip() == "0"

    # Test output
    res_ver = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "version.py")],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert res_ver.stdout.strip().startswith("0.")


def test_resolve_version_from_system(tmp_path: Path, monkeypatch) -> None:
    """Test _resolve_version prioritizes /etc/roostos/version when present."""
    fake_sys_file = tmp_path / "version"
    fake_sys_file.write_text("9.9.9", encoding="utf-8")

    with patch("roostos_cli.Path") as mock_path:
        def path_side_effect(p):
            if str(p) == "/etc/roostos/version":
                return fake_sys_file
            return Path(p)

        mock_path.side_effect = path_side_effect
        ver = _resolve_version()
        assert ver == "9.9.9"


def test_cli_version_matches_resolved(monkeypatch) -> None:
    """Test roostos --version command includes resolved version string."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_compute_version_on_release_branch(monkeypatch) -> None:
    """Test release branch calculates major and minor from branch name."""
    monkeypatch.delenv("ROOSTOS_VERSION", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    monkeypatch.setenv("GITHUB_REF_NAME", "release/1.0")

    ver = version_script.compute_version(REPO_ROOT)
    assert ver.startswith("1.0.")
    patch_part = ver.split(".")[2]
    assert patch_part.isdigit()

    monkeypatch.setenv("GITHUB_REF_NAME", "release/2.5")
    ver2 = version_script.compute_version(REPO_ROOT)
    assert ver2.startswith("2.5.")


def test_compute_version_run_attempt_collision_prevention(monkeypatch) -> None:
    """Test re-running failed builds appends .postN suffix to prevent collisions."""
    monkeypatch.delenv("ROOSTOS_VERSION", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")

    ver_main = version_script.compute_version(REPO_ROOT)
    assert ver_main.endswith(".post1")

    monkeypatch.setenv("GITHUB_REF_NAME", "feature/my-test")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")
    ver_feat = version_script.compute_version(REPO_ROOT)
    assert ver_feat.endswith(".post2")

