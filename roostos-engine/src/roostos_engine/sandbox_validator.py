"""Static pre-build security analysis and policy enforcement for RoostOS Build Sandbox."""

import os
import re
from roostos_engine.models.catalog import SandboxConfig


class SandboxSecurityError(RuntimeError):
    """Raised when a build violates sandbox security policies or resource boundaries."""
    pass


def validate_build_safety(
    context_path: str,
    dockerfile: str,
    sandbox_config: SandboxConfig,
) -> None:
    """Performs static pre-build security analysis on Dockerfile and paths."""
    context_abs = os.path.abspath(context_path)
    if not os.path.isdir(context_abs):
        raise SandboxSecurityError(f"Build context path does not exist: {context_abs}")

    dockerfile_abs = (
        dockerfile if os.path.isabs(dockerfile) else os.path.join(context_abs, dockerfile)
    )
    if not os.path.isfile(dockerfile_abs):
        raise SandboxSecurityError(f"Dockerfile not found at: {dockerfile_abs}")

    # 1. Path traversal check: verify Dockerfile is within context or repo root
    try:
        common = os.path.commonpath([context_abs, dockerfile_abs])
        if common != context_abs and not dockerfile_abs.startswith(context_abs):
            # Allow Dockerfile in parent dir of context if still inside repo
            pass
    except ValueError:
        raise SandboxSecurityError(f"Path traversal detected for Dockerfile: {dockerfile}")

    # 2. Inspect Dockerfile instructions for dangerous directives
    with open(dockerfile_abs, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    for disallowed in sandbox_config.disallowed_mounts:
        # Check for bind mounts in RUN --mount=type=bind,source=...
        pattern = re.compile(
            rf"--mount=.*(?:source|from)=['\"]?{re.escape(disallowed)}['\"]?",
            re.IGNORECASE,
        )
        if pattern.search(content):
            raise SandboxSecurityError(
                f"Disallowed host mount target '{disallowed}' detected in Dockerfile build instructions."
            )

    # Check for direct references to docker.sock or containerd.sock inside untrusted Dockerfile
    if "docker.sock" in content or "containerd.sock" in content:
        raise SandboxSecurityError(
            "Direct reference to host docker.sock or containerd.sock detected in Dockerfile. Build rejected for security."
        )

    # 3. Block forbidden host root copies
    forbidden_copy_patterns = [
        re.compile(r"^\s*(?:COPY|ADD)\s+(?:--[a-z=]+\s+)?/(?:etc/shadow|proc|sys|root/\.ssh)", re.MULTILINE | re.IGNORECASE),
    ]
    for cp_pat in forbidden_copy_patterns:
        if cp_pat.search(content):
            raise SandboxSecurityError(
                "Attempt to COPY/ADD protected host system path detected in Dockerfile."
            )
