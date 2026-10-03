"""BuildSandbox for safely building containers within isolated resource and security boundaries."""

import os
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from roostos_engine.models.catalog import SandboxConfig
from roostos_engine.sandbox_network import SandboxNetworkFilter
from roostos_engine.sandbox_validator import SandboxSecurityError, validate_build_safety


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
    if not allow_net:
        network_mode = "none"
    elif sandbox_config.restricted_network:
        network_mode = sandbox_config.isolated_network_name
    else:
        network_mode = "bridge"

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
        network_mode,
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
    output_dir: Optional[str] = None,
) -> List[str]:
    """Constructs command to run build inside isolated build container without root socket."""
    allow_net = bool(
        sandbox_config.network_required
        and sandbox_config.user_approved
        and sandbox_config.allow_network
    )
    if not allow_net:
        network_mode = "none"
    elif sandbox_config.restricted_network:
        network_mode = sandbox_config.isolated_network_name
    else:
        network_mode = "bridge"

    rel_dockerfile = (
        os.path.relpath(dockerfile, context_path)
        if os.path.isabs(dockerfile)
        else dockerfile
    )
    cmd = [
        "docker",
        "run",
        "--rm",
    ]

    if sandbox_config.rootless_build:
        if output_dir:
            cmd.extend(["-v", f"{os.path.abspath(output_dir)}:/output:rw"])
    else:
        sock = sandbox_config.containerd_socket
        if not os.path.exists(sock) and os.path.exists("/var/run/docker.sock"):
            sock = "/var/run/docker.sock"
        cmd.extend(["-v", f"{sock}:/run/containerd/containerd.sock"])

    cmd.extend([
        "-v",
        f"{os.path.abspath(context_path)}:/workspace:ro",
        "--memory",
        f"{sandbox_config.max_memory_mb}m",
        "--cpus",
        str(sandbox_config.max_cpu_cores),
        "--security-opt",
        f"no-new-privileges:{'true' if sandbox_config.no_new_privileges else 'false'}",
        "--network",
        network_mode,
    ])

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

    if sandbox_config.rootless_build and output_dir:
        cmd.extend(["--output-tar", "/output/image.tar"])

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
        if cfg.restricted_network:
            net_filter.ensure_restricted_network(cfg.isolated_network_name)

    try:
        # Build Container strategy (rootless by default)
        if builder in ("container", "sandbox-container") or (cfg.use_build_container and builder != "direct"):
            with tempfile.TemporaryDirectory() as output_dir:
                container_cmd = build_container_sandbox_command(
                    context_path=context_path,
                    dockerfile=dockerfile,
                    image_tag=image_tag,
                    build_args=build_args,
                    sandbox_config=cfg,
                    target_stage=target_stage,
                    proxy_env=proxy_env,
                    output_dir=output_dir if cfg.rootless_build else None,
                )
                try:
                    res = subprocess.run(
                        container_cmd,
                        capture_output=True,
                        text=True,
                        timeout=cfg.timeout_seconds,
                    )
                    if res.returncode == 0:
                        tar_path = os.path.join(output_dir, "image.tar")
                        if cfg.rootless_build and os.path.exists(tar_path):
                            load_res = subprocess.run(
                                ["docker", "load", "-i", tar_path],
                                capture_output=True,
                                text=True,
                            )
                            if load_res.returncode != 0:
                                return False, f"Failed to load built image into daemon:\n{load_res.stderr}"
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
