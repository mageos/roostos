"""BuildSandbox for safely building containers within isolated resource and security boundaries."""

import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from roostos_engine.models.catalog import SandboxConfig
from roostos_engine.sandbox_network import SandboxNetworkFilter


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


def build_sandboxed_command(
    context_path: str,
    dockerfile: str,
    image_tag: str,
    build_args: Dict[str, str],
    sandbox_config: SandboxConfig,
    target_stage: Optional[str] = None,
    proxy_env: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Constructs hardened docker build command applying sandbox resource and security flags."""
    allow_net = bool(
        sandbox_config.network_required
        and sandbox_config.user_approved
        and sandbox_config.allow_network
    )
    cmd = [
        "docker",
        "build",
        "-t",
        image_tag,
        "-f",
        dockerfile,
        "--memory",
        f"{sandbox_config.max_memory_mb}m",
        "--memory-swap",
        f"{sandbox_config.max_memory_mb}m",
        "--cpus",
        str(sandbox_config.max_cpu_cores),
        "--security-opt",
        f"no-new-privileges:{'true' if sandbox_config.no_new_privileges else 'false'}",
        "--ulimit",
        "nofile=1024:2048",
        "--ulimit",
        "nproc=512:1024",
        "--network",
        "bridge" if allow_net else "none",
    ]

    if proxy_env:
        for k, v in proxy_env.items():
            cmd.extend(["--build-arg", f"{k}={v}"])

    for k, v in build_args.items():
        cmd.extend(["--build-arg", f"{k}={v}"])

    if target_stage:
        cmd.extend(["--target", target_stage])

    cmd.append(context_path)
    return cmd


def build_container_sandbox_command(
    context_path: str,
    dockerfile: str,
    image_tag: str,
    build_args: Dict[str, str],
    sandbox_config: SandboxConfig,
    target_stage: Optional[str] = None,
    proxy_env: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Constructs command to run build inside isolated build container with containerd socket."""
    sock = sandbox_config.containerd_socket
    if not os.path.exists(sock) and os.path.exists("/var/run/docker.sock"):
        sock = "/var/run/docker.sock"

    allow_net = bool(
        sandbox_config.network_required
        and sandbox_config.user_approved
        and sandbox_config.allow_network
    )
    rel_dockerfile = (
        os.path.relpath(dockerfile, context_path)
        if os.path.isabs(dockerfile)
        else dockerfile
    )
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{sock}:/run/containerd/containerd.sock",
        "-v",
        f"{os.path.abspath(context_path)}:/workspace:ro",
        "--memory",
        f"{sandbox_config.max_memory_mb}m",
        "--cpus",
        str(sandbox_config.max_cpu_cores),
        "--security-opt",
        f"no-new-privileges:{'true' if sandbox_config.no_new_privileges else 'false'}",
        "--network",
        "bridge" if allow_net else "none",
    ]

    if proxy_env:
        cmd.extend(["--add-host", "host.docker.internal:host-gateway"])
        for k, v in proxy_env.items():
            cmd.extend(["-e", f"{k}={v}", "--build-arg", f"{k}={v}"])

    cmd.extend([
        sandbox_config.builder_image,
        "--tag",
        image_tag,
        "--dockerfile",
        rel_dockerfile,
        "--context",
        "/workspace",
    ])

    for k, v in build_args.items():
        cmd.extend(["--build-arg", f"{k}={v}"])
    if target_stage:
        cmd.extend(["--target", target_stage])
    return cmd


def execute_sandboxed_build(
    context_path: str,
    dockerfile: str,
    image_tag: str,
    build_args: Dict[str, str],
    sandbox_config: Optional[SandboxConfig] = None,
    target_stage: Optional[str] = None,
    builder: str = "dockerfile",
) -> Tuple[bool, str]:
    """Validates security boundaries and executes container build within the configured sandbox."""
    cfg = sandbox_config or SandboxConfig()

    try:
        validate_build_safety(context_path, dockerfile, cfg)
    except SandboxSecurityError as sec_err:
        return False, f"Sandbox Security Rejection: {sec_err}"

    # Enforce network requirement declaration & user approval
    net_filter: Optional[SandboxNetworkFilter] = None
    proxy_env: Optional[Dict[str, str]] = None
    if cfg.network_required:
        if not cfg.user_approved:
            return (
                False,
                f"Sandbox Security Rejection: Build explicitly requires network access to "
                f"{cfg.allowed_endpoints} ('{cfg.network_justification}'), but network access "
                f"has not been approved by the user.",
            )
        active_endpoints = cfg.approved_endpoints or cfg.allowed_endpoints
        net_filter = SandboxNetworkFilter(active_endpoints)
        host_ip, _ = net_filter.start()
        proxy_env = net_filter.get_proxy_env(host_ip)

    try:
        # Build Container with containerd socket (primary strategy)
        if builder in ("container", "sandbox-container") or (cfg.use_build_container and builder != "direct"):
            container_cmd = build_container_sandbox_command(
                context_path=context_path,
                dockerfile=dockerfile,
                image_tag=image_tag,
                build_args=build_args,
                sandbox_config=cfg,
                target_stage=target_stage,
                proxy_env=proxy_env,
            )
            try:
                res = subprocess.run(
                    container_cmd,
                    capture_output=True,
                    text=True,
                    timeout=cfg.timeout_seconds,
                )
                if res.returncode == 0:
                    return True, f"Successfully built {image_tag} in build container.\n{res.stdout}"
                if not ("Unable to find image" in res.stderr or "image not found" in res.stderr):
                    return False, f"Build container failed (exit {res.returncode}):\n{res.stderr}\n{res.stdout}"
            except subprocess.TimeoutExpired:
                return False, f"Build aborted: exceeded sandbox execution timeout of {cfg.timeout_seconds} seconds."
            except Exception:
                pass

        # Direct hardened daemon sandbox execution (fallback or direct)
        cmd = build_sandboxed_command(
            context_path=context_path,
            dockerfile=dockerfile,
            image_tag=image_tag,
            build_args=build_args,
            sandbox_config=cfg,
            target_stage=target_stage,
            proxy_env=proxy_env,
        )

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=cfg.timeout_seconds,
            )
            if res.returncode == 0:
                return True, f"Successfully built {image_tag} in sandbox.\n{res.stdout}"
            return False, f"Sandboxed build failed (exit code {res.returncode}):\n{res.stderr}\n{res.stdout}"
        except subprocess.TimeoutExpired:
            return False, f"Build aborted: exceeded sandbox execution timeout of {cfg.timeout_seconds} seconds."
        except Exception as e:
            return False, f"Error executing sandboxed build process: {e}"
    finally:
        if net_filter:
            net_filter.stop()
