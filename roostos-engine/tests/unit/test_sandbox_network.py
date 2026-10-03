"""Unit tests for RoostOS Build Sandbox domain-filtering proxy and network policy."""

import asyncio
import subprocess
from unittest.mock import patch
import pytest

from roostos_engine.sandbox_network import (
    is_endpoint_allowed,
    SandboxDomainProxy,
    SandboxNetworkFilter,
)


def test_is_endpoint_allowed():
    allowed = ["registry.npmjs.org", "pypi.org", "*.github.com", "custom-git.org:8443"]

    assert is_endpoint_allowed("registry.npmjs.org", allowed) is True
    assert is_endpoint_allowed("registry.npmjs.org:443", allowed, target_port=443) is True
    assert is_endpoint_allowed("pypi.org", allowed, target_port=80) is True
    assert is_endpoint_allowed("codeload.github.com", allowed) is True
    assert is_endpoint_allowed("github.com", allowed) is True
    assert is_endpoint_allowed("custom-git.org", allowed, target_port=8443) is True

    # Disallowed domains
    assert is_endpoint_allowed("evil.com", allowed) is False
    assert is_endpoint_allowed("attacker.site:8080", allowed, target_port=8080) is False
    assert is_endpoint_allowed("notgithub.com", allowed) is False
    assert is_endpoint_allowed("", allowed) is False

    # Blocked raw IPs and cloud metadata
    assert is_endpoint_allowed("127.0.0.1", allowed) is False
    assert is_endpoint_allowed("localhost", allowed) is False
    assert is_endpoint_allowed("169.254.169.254", allowed) is False
    assert is_endpoint_allowed("192.168.1.1", allowed) is False


@pytest.mark.asyncio
async def test_sandbox_domain_proxy_blocks_unauthorized_domain():
    proxy = SandboxDomainProxy(allowed_endpoints=["trusted.org"], bind_host="127.0.0.1")
    port = await proxy.start()

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        # Attempt CONNECT to untrusted domain
        writer.write(b"CONNECT untrusted-malicious.org:443 HTTP/1.1\r\nHost: untrusted-malicious.org\r\n\r\n")
        await writer.drain()

        response = await reader.read(1024)
        assert b"403 Forbidden" in response
        assert b"Blocked by RoostOS Build Sandbox" in response
        assert "untrusted-malicious.org" in proxy.blocked_attempts
        writer.close()
        await writer.wait_closed()
    finally:
        await proxy.stop()


@pytest.mark.asyncio
async def test_sandbox_domain_proxy_blocks_non_standard_port():
    proxy = SandboxDomainProxy(allowed_endpoints=["trusted.org"], bind_host="127.0.0.1")
    port = await proxy.start()

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        # Attempt reverse shell port (e.g., 4444)
        writer.write(b"CONNECT trusted.org:4444 HTTP/1.1\r\nHost: trusted.org\r\n\r\n")
        await writer.drain()

        response = await reader.read(1024)
        assert b"403 Forbidden" in response
        assert b"non-standard port not allowed" in response
        writer.close()
        await writer.wait_closed()
    finally:
        await proxy.stop()


def test_sandbox_network_filter_lifecycle():
    net_filter = SandboxNetworkFilter(allowed_endpoints=["registry.npmjs.org"], bind_host="127.0.0.1")
    host_ip, port = net_filter.start()

    assert port > 0
    assert host_ip == "host.docker.internal"

    env = net_filter.get_proxy_env("127.0.0.1")
    assert f"http://127.0.0.1:{port}" in env["HTTP_PROXY"]
    assert f"http://127.0.0.1:{port}" in env["HTTPS_PROXY"]
    assert "NO_PROXY" in env

    net_filter.stop()


def test_ensure_restricted_network():
    with patch("subprocess.run") as mock_run:
        # Simulate network does not exist, so inspect returns code 1, create returns 0
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="not found"),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]
        net_name = SandboxNetworkFilter.ensure_restricted_network("test-build-net")
        assert net_name == "test-build-net"
        assert mock_run.call_count == 2
        # Verify --internal was passed
        create_args = mock_run.call_args_list[1][0][0]
        assert "--internal" in create_args
        assert "test-build-net" in create_args
