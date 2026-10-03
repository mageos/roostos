"""Unit tests for RoostOS Build Sandbox and security validation."""

import os
import tempfile
import subprocess
from unittest.mock import patch, MagicMock
import pytest
import yaml

from roostos_engine.models.catalog import (
    SandboxConfig,
    BuildManifest,
    SourceBuildSpec,
    PackageManifest,
)
from roostos_engine.build_sandbox import (
    SandboxSecurityError,
    validate_build_safety,
    build_sandboxed_command,
    build_container_sandbox_command,
    execute_sandboxed_build,
)
from roostos_engine.source_builder import SourceBuilder


@pytest.fixture
def temp_sandbox_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_validate_build_safety_benign(temp_sandbox_workspace):
    dockerfile_path = os.path.join(temp_sandbox_workspace, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write("FROM alpine:3.19\nRUN apk add --no-cache curl\nCMD ['echo', 'secure']\n")

    cfg = SandboxConfig()
    # Should not raise
    validate_build_safety(temp_sandbox_workspace, "Dockerfile", cfg)


def test_validate_build_safety_rejects_docker_sock(temp_sandbox_workspace):
    dockerfile_path = os.path.join(temp_sandbox_workspace, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write("FROM alpine:3.19\nRUN --mount=type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock docker ps\n")

    cfg = SandboxConfig()
    with pytest.raises(SandboxSecurityError) as exc_info:
        validate_build_safety(temp_sandbox_workspace, "Dockerfile", cfg)
    assert "docker.sock" in str(exc_info.value)


def test_validate_build_safety_rejects_sensitive_host_copy(temp_sandbox_workspace):
    dockerfile_path = os.path.join(temp_sandbox_workspace, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write("FROM alpine:3.19\nCOPY /etc/shadow /stolen_shadow\n")

    cfg = SandboxConfig()
    with pytest.raises(SandboxSecurityError) as exc_info:
        validate_build_safety(temp_sandbox_workspace, "Dockerfile", cfg)
    assert "Attempt to COPY/ADD protected host" in str(exc_info.value)


def test_validate_build_safety_missing_dockerfile(temp_sandbox_workspace):
    cfg = SandboxConfig()
    with pytest.raises(SandboxSecurityError) as exc_info:
        validate_build_safety(temp_sandbox_workspace, "NonExistentDockerfile", cfg)
    assert "Dockerfile not found" in str(exc_info.value)


def test_build_sandboxed_command_flags():
    cfg = SandboxConfig(
        allow_network=False,
        max_memory_mb=1024,
        max_cpu_cores=1.5,
        no_new_privileges=True,
    )
    cmd = build_sandboxed_command(
        context_path="/workspace/app",
        dockerfile="/workspace/app/Dockerfile",
        image_tag="roostos-local/test:1.0",
        build_args={"ENV": "sandbox"},
        sandbox_config=cfg,
        target_stage="builder",
    )

    assert "docker" in cmd[0]
    assert "build" in cmd[1]
    assert "--memory" in cmd
    assert "1024m" in cmd
    assert "--cpus" in cmd
    assert "1.5" in cmd
    assert "--network" in cmd
    assert "none" in cmd  # Network isolated
    assert "no-new-privileges:true" in cmd[cmd.index("--security-opt") + 1]
    assert "--build-arg" in cmd
    assert "ENV=sandbox" in cmd
    assert "--target" in cmd
    assert "builder" in cmd
    assert cmd[-1] == "/workspace/app"


def test_execute_sandboxed_build_timeout(temp_sandbox_workspace):
    dockerfile_path = os.path.join(temp_sandbox_workspace, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write("FROM alpine:3.19\nCMD echo ok\n")

    cfg = SandboxConfig(timeout_seconds=1)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker build", timeout=1)):
        success, logs = execute_sandboxed_build(
            context_path=temp_sandbox_workspace,
            dockerfile=dockerfile_path,
            image_tag="roostos-local/timeout:1.0",
            build_args={},
            sandbox_config=cfg,
        )
        assert success is False
        assert "exceeded sandbox execution timeout" in logs


def test_execute_sandboxed_build_security_rejection(temp_sandbox_workspace):
    dockerfile_path = os.path.join(temp_sandbox_workspace, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write("FROM alpine:3.19\nRUN --mount=type=bind,source=/proc,target=/host_proc ls\n")

    success, logs = execute_sandboxed_build(
        context_path=temp_sandbox_workspace,
        dockerfile=dockerfile_path,
        image_tag="roostos-local/unsafe:1.0",
        build_args={},
    )
    assert success is False
    assert "Sandbox Security Rejection" in logs


def test_source_builder_discovers_roost_build_yaml(temp_sandbox_workspace):
    builder = SourceBuilder(sources_dir=temp_sandbox_workspace)
    app_dir = os.path.join(temp_sandbox_workspace, "hardened-app")
    os.makedirs(app_dir, exist_ok=True)

    build_yaml = {
        "schema_version": "1.0",
        "app_id": "hardened-app",
        "context_path": ".",
        "dockerfile": "Dockerfile.prod",
        "build_args": {"NODE_ENV": "production"},
        "sandbox": {
            "allow_network": False,
            "max_memory_mb": 4096,
            "max_cpu_cores": 4.0,
            "timeout_seconds": 900,
        },
    }
    with open(os.path.join(app_dir, "roost-build.yaml"), "w") as f:
        yaml.safe_dump(build_yaml, f)

    manifest = builder.load_manifest(app_dir)
    assert manifest is not None
    assert manifest.id == "hardened-app"
    assert manifest.build.dockerfile == "Dockerfile.prod"
    assert manifest.build.sandbox.allow_network is False
    assert manifest.build.sandbox.max_memory_mb == 4096
    assert manifest.build.sandbox.max_cpu_cores == 4.0
    assert manifest.build.sandbox.timeout_seconds == 900


def test_build_container_sandbox_command_rootless():
    cfg = SandboxConfig(
        allow_network=True,
        network_required=True,
        user_approved=True,
        max_memory_mb=2048,
        max_cpu_cores=2.0,
        rootless_build=True,
        restricted_network=True,
        isolated_network_name="roostos-build-net",
        builder_image="roostos-builder:latest",
    )
    cmd = build_container_sandbox_command(
        context_path="/home/user/app",
        dockerfile="/home/user/app/Dockerfile",
        image_tag="roostos-local/my-app:1.0.0",
        build_args={"KEY": "VAL"},
        sandbox_config=cfg,
        target_stage="prod",
        output_dir="/tmp/output_123",
    )

    assert "docker" in cmd[0]
    assert "run" in cmd[1]
    assert "--rm" in cmd
    # Socket must NOT be mounted in rootless mode
    sock_mount = [arg for arg in cmd if "containerd.sock" in arg or "docker.sock" in arg]
    assert len(sock_mount) == 0
    # Output tar dir and workspace must be mounted
    assert "/tmp/output_123:/output:rw" in cmd
    assert "/home/user/app:/workspace:ro" in cmd
    assert "--output-tar" in cmd
    assert "/output/image.tar" in cmd
    assert "--network" in cmd
    assert "roostos-build-net" in cmd
    assert "--memory" in cmd
    assert "2048m" in cmd
    assert "--cpus" in cmd
    assert "2.0" in cmd
    assert "roostos-builder:latest" in cmd
    assert "--tag" in cmd
    assert "roostos-local/my-app:1.0.0" in cmd
    assert "--context" in cmd
    assert "/workspace" in cmd
    assert "--build-arg" in cmd
    assert "KEY=VAL" in cmd
    assert "--target" in cmd
    assert "prod" in cmd


def test_build_container_sandbox_command_legacy_socket():
    cfg = SandboxConfig(
        rootless_build=False,
        containerd_socket="/run/containerd/containerd.sock",
    )
    cmd = build_container_sandbox_command(
        context_path="/home/user/app",
        dockerfile="/home/user/app/Dockerfile",
        image_tag="roostos-local/my-app:1.0.0",
        build_args={},
        sandbox_config=cfg,
    )
    sock_mount = [arg for arg in cmd if "/run/containerd/containerd.sock" in arg]
    assert len(sock_mount) > 0


def test_execute_sandboxed_build_rejects_unapproved_network(temp_sandbox_workspace):
    dockerfile_path = os.path.join(temp_sandbox_workspace, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write("FROM alpine:3.19\nRUN apk add --no-cache curl\n")

    cfg = SandboxConfig(
        network_required=True,
        allowed_endpoints=["registry.npmjs.org"],
        network_justification="Fetch npm packages",
        user_approved=False,
    )

    success, logs = execute_sandboxed_build(
        context_path=temp_sandbox_workspace,
        dockerfile=dockerfile_path,
        image_tag="roostos-local/unapproved:1.0",
        build_args={},
        sandbox_config=cfg,
    )
    assert success is False
    assert "Sandbox Security Rejection" in logs
    assert "registry.npmjs.org" in logs
    assert "has not been approved" in logs


def test_build_sandboxed_command_offline_when_network_not_required():
    cfg = SandboxConfig(network_required=False)
    cmd = build_sandboxed_command(
        context_path="/workspace",
        dockerfile="/workspace/Dockerfile",
        image_tag="roostos-local/offline:1.0",
        build_args={},
        sandbox_config=cfg,
    )
    assert "--network" in cmd
    assert cmd[cmd.index("--network") + 1] == "none"


