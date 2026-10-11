#!/usr/bin/env python3
"""RoostOS Dynamic Version Determination Script.

Computes the semver / PEP 440 version based on:
1. MAJOR_VERSION file at repository root.
2. Git commit history:
   - Builds on 'main' branch increment minor: {major}.{count} (e.g., 0.1, 0.2, ... 0.12).
   - Builds on feature branches increment the next main minor as alpha builds:
     {major}.{next_main}a{alpha_build} (e.g., 0.13a1, 0.13a2, ...).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stripped stdout or empty string on error."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def get_repo_root() -> Path:
    """Resolve repository root directory."""
    root_str = _run_git(["rev-parse", "--show-toplevel"])
    if root_str and Path(root_str).is_dir():
        return Path(root_str)
    return Path(__file__).resolve().parent.parent


def get_major_version(repo_root: Path) -> int:
    """Read the major version integer from MAJOR_VERSION file."""
    major_file = repo_root / "MAJOR_VERSION"
    if major_file.is_file():
        try:
            content = major_file.read_text(encoding="utf-8").strip()
            return int(content)
        except (ValueError, OSError):
            pass
    return 0


def _resolve_main_ref(repo_root: Path) -> str:
    """Find the canonical main branch ref in git (origin/main or main)."""
    for candidate in ["origin/main", "main", "origin/master", "master"]:
        if _run_git(["rev-parse", "--verify", candidate], cwd=repo_root):
            return candidate
    return "HEAD"


def _get_current_branch(repo_root: Path) -> str:
    """Detect current branch name from git or CI environment variables."""
    # Check GitHub Actions environment variables
    head_ref = os.environ.get("GITHUB_HEAD_REF", "").strip()
    if head_ref:
        return head_ref

    ref_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    if ref_name:
        return ref_name

    github_ref = os.environ.get("GITHUB_REF", "").strip()
    if github_ref.startswith("refs/heads/"):
        return github_ref.replace("refs/heads/", "")

    # Local git detection
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    return branch or "HEAD"


def _apply_run_attempt(ver: str) -> str:
    """Append post-release suffix on CI re-runs to avoid artifact and repository collision."""
    attempt_str = os.environ.get("GITHUB_RUN_ATTEMPT", "").strip()
    if attempt_str.isdigit():
        attempt = int(attempt_str)
        if attempt > 1:
            return f"{ver}.post{attempt - 1}"
    return ver


def compute_version(repo_root: Path) -> str:
    """Compute the RoostOS package version string."""
    # 1. Respect explicit override
    override = os.environ.get("ROOSTOS_VERSION", "").strip()
    if override:
        return override

    major = get_major_version(repo_root)

    # 2. Check for release tags
    github_ref = os.environ.get("GITHUB_REF", "").strip()
    if github_ref.startswith("refs/tags/v"):
        return github_ref.replace("refs/tags/v", "")

    current_tag = _run_git(["describe", "--tags", "--exact-match"], cwd=repo_root)
    if current_tag.startswith("v"):
        return current_tag[1:]

    # 3. Check if git repository is available
    if not (repo_root / ".git").exists() and not _run_git(["rev-parse", "--git-dir"], cwd=repo_root):
        fallback_file = repo_root / "VERSION"
        if fallback_file.is_file():
            return fallback_file.read_text(encoding="utf-8").strip()
        return f"{major}.1"

    main_ref = _resolve_main_ref(repo_root)
    branch = _get_current_branch(repo_root)
    is_main = branch in ["main", "origin/main", "master", "origin/master"]

    # 4. Check for release branches (e.g. release/1.0, release/2.0)
    if branch.startswith("release/"):
        rel_str = branch[len("release/") :].strip()
        merge_base = _run_git(["merge-base", "HEAD", main_ref], cwd=repo_root)
        if merge_base:
            rel_commits = _run_git(["rev-list", "--count", f"{merge_base}..HEAD"], cwd=repo_root)
            patch_count = int(rel_commits) if rel_commits.isdigit() else 0
        else:
            patch_count = 0

        if "." in rel_str:
            parts = rel_str.split(".")
            rel_major = int(parts[0]) if parts[0].isdigit() else major
            rel_minor = int(parts[1]) if parts[1].isdigit() else 0
            base_ver = f"{rel_major}.{rel_minor}.{patch_count}"
        else:
            rel_major = int(rel_str) if rel_str.isdigit() else major
            base_ver = f"{rel_major}.{max(1, patch_count)}"
        return _apply_run_attempt(base_ver)

    # 5. Count commits on main for the current major version
    if major == 0:
        root_commits = _run_git(["rev-list", "--max-parents=0", "HEAD"], cwd=repo_root).splitlines()
        root_commit = root_commits[-1] if root_commits else ""
        if root_commit:
            count_str = _run_git(
                ["rev-list", "--count", "--first-parent", f"{root_commit}..{main_ref}"],
                cwd=repo_root,
            )
            main_count = int(count_str) if count_str.isdigit() else 1
        else:
            main_count = 1
    else:
        # Find commit where MAJOR_VERSION was changed to this major
        base_commit = _run_git(
            ["log", "--reverse", "--format=%H", "-S", str(major), "--", "MAJOR_VERSION"],
            cwd=repo_root,
        ).splitlines()
        base = base_commit[0] if base_commit else ""
        if base:
            count_str = _run_git(
                ["rev-list", "--count", "--first-parent", f"{base}..{main_ref}"],
                cwd=repo_root,
            )
            main_count = (int(count_str) + 1) if count_str.isdigit() else 1
        else:
            main_count = 1

    if is_main:
        return _apply_run_attempt(f"{major}.{max(1, main_count)}")

    # 6. Feature branch: target next main release with alpha build counter
    next_main = main_count + 1
    merge_base = _run_git(["merge-base", "HEAD", main_ref], cwd=repo_root)
    if merge_base:
        alpha_str = _run_git(["rev-list", "--count", f"{merge_base}..HEAD"], cwd=repo_root)
        alpha_count = int(alpha_str) if alpha_str.isdigit() else 1
    else:
        alpha_count = 1

    alpha_count = max(1, alpha_count)
    return _apply_run_attempt(f"{major}.{next_main}a{alpha_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RoostOS Version Resolver")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write computed version to the root VERSION file",
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="Print only the major version integer",
    )
    args = parser.parse_args()

    root = get_repo_root()
    if args.major:
        print(get_major_version(root))
        return

    version = compute_version(root)
    if args.write:
        version_file = root / "VERSION"
        version_file.write_text(f"{version}\n", encoding="utf-8")
        print(f"Updated {version_file} -> {version}")
    else:
        print(version)


if __name__ == "__main__":
    main()
