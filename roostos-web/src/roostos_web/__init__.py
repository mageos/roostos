# RoostOS Web API Service Package
from __future__ import annotations

import importlib.metadata
from pathlib import Path


def _resolve_version() -> str:
    """Resolve RoostOS version from system, repository, or package metadata."""
    # 1. System installation (Debian package)
    sys_file = Path("/etc/roostos/version")
    if sys_file.is_file():
        try:
            ver = sys_file.read_text(encoding="utf-8").strip()
            if ver:
                return ver
        except OSError:
            pass

    # 2. Source tree VERSION file (development environment)
    for base in [Path(__file__).resolve().parent, Path.cwd()]:
        for candidate in [
            base / "VERSION",
            base.parent / "VERSION",
            base.parent.parent / "VERSION",
        ]:
            if candidate.is_file():
                try:
                    ver = candidate.read_text(encoding="utf-8").strip()
                    if ver:
                        return ver
                except OSError:
                    pass

    # 3. Package metadata (installed package)
    try:
        ver = importlib.metadata.version("roostos-web")
        if ver:
            return ver
    except importlib.metadata.PackageNotFoundError:
        pass

    return "0.1.0"


__version__: str = _resolve_version()

