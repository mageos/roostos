"""Unit tests for RoostOS Build Sandbox domain-filtering proxy and network policy."""

import asyncio
import urllib.request
import urllib.error
import pytest

from roostos_engine.sandbox_network import (
    is_endpoint_allowed,
    SandboxDomainProxy,
    SandboxNetworkFilter,
)


def test_is_endpoint_allowed():
    allowed = ["registry.npmjs.org", "pypi.org", "*.github.com"]

    assert is_endpoint_allowed("registry.npmjs.org", allowed) is True
    assert is_endpoint_allowed("registry.npmjs.org:443", allowed) is True
    assert is_endpoint_allowed("pypi.org", allowed) is True
    assert is_endpoint_allowed("codeload.github.com", allowed) is True
    assert is_endpoint_allowed("github.com", allowed) is True

    # Disallowed domains
    assert is_endpoint_allowed("evil.com", allowed) is False
    assert is_endpoint_allowed("attacker.site:8080", allowed) is False
    assert is_endpoint_allowed("notgithub.com", allowed) is False
    assert is_endpoint_allowed("", allowed) is False


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
