"""Unit tests for RoostOS rootless build execution and image archive loading."""

import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from roostos_engine.models.catalog import SandboxConfig
from roostos_engine.build_sandbox import (
    build_sandboxed_command,
    execute_sandboxed_build,
)
from roostos_engine.sandbox_network import SandboxNetworkFilter


def test_build_sandboxed_command_uses_restricted_network():
    cfg = SandboxConfig(
        allow_network=True,
        network_required=True,
        user_approved=True,
        restricted_network=True,
        isolated_network_name="roostos-build-net",
    )
    cmd = build_sandboxed_command(
        context_path="/workspace",
        dockerfile="/workspace/Dockerfile",
        image_tag="roostos-local/restricted:1.0",
        build_args={},
        sandbox_config=cfg,
    )
    assert "--network" in cmd
    assert cmd[cmd.index("--network") + 1] == "roostos-build-net"


def test_execute_sandboxed_build_rootless_loads_tar(tmp_path):
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text("FROM alpine:3.19\nCMD echo hello\n")

    cfg = SandboxConfig(
        use_build_container=True,
        rootless_build=True,
    )

    def fake_subprocess_run(cmd, *args, **kwargs):
        if "run" in cmd:
            # Simulate builder container creating image.tar in the mounted output dir
            # Find the output mount in cmd
            for arg in cmd:
                if ":/output:rw" in arg:
                    out_dir = arg.split(":/output:rw")[0]
                    tar_file = os.path.join(out_dir, "image.tar")
                    with open(tar_file, "wb") as f:
                        f.write(b"fake-tar-bytes")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Build complete", stderr="")
        if "load" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Loaded image", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run) as mock_run:
        success, logs = execute_sandboxed_build(
            context_path=str(tmp_path),
            dockerfile=str(dockerfile_path),
            image_tag="roostos-local/rootless-test:1.0",
            build_args={},
            sandbox_config=cfg,
            builder="container",
        )
        assert success is True
        assert "Successfully built roostos-local/rootless-test:1.0 in build container" in logs

        # Verify docker load was invoked with the tar
        load_calls = [c for c in mock_run.call_args_list if "load" in c[0][0]]
        assert len(load_calls) == 1
        assert load_calls[0][0][0][0:2] == ["docker", "load"]


def test_execute_sandboxed_build_rootless_handles_load_error(tmp_path):
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text("FROM alpine:3.19\nCMD echo hello\n")

    cfg = SandboxConfig(
        use_build_container=True,
        rootless_build=True,
    )

    def fake_subprocess_run(cmd, *args, **kwargs):
        if "run" in cmd:
            for arg in cmd:
                if ":/output:rw" in arg:
                    out_dir = arg.split(":/output:rw")[0]
                    with open(os.path.join(out_dir, "image.tar"), "wb") as f:
                        f.write(b"corrupt")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        if "load" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="Corrupt tar archive")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        success, logs = execute_sandboxed_build(
            context_path=str(tmp_path),
            dockerfile=str(dockerfile_path),
            image_tag="roostos-local/corrupt-test:1.0",
            build_args={},
            sandbox_config=cfg,
            builder="container",
        )
        assert success is False
        assert "Failed to load built image into daemon" in logs
        assert "Corrupt tar archive" in logs
