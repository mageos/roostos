"""Ephemeral domain-filtering proxy and network policy for RoostOS build sandbox."""

import os
import re
import socket
import asyncio
import threading
from typing import List, Set, Optional, Tuple, Dict, Any


def is_endpoint_allowed(requested_host: str, allowed_endpoints: List[str]) -> bool:
    """Checks if requested host matches any approved endpoint or wildcard domain."""
    if not requested_host or not allowed_endpoints:
        return False

    norm_host = requested_host.split(":")[0].strip().lower()

    for pattern in allowed_endpoints:
        norm_pat = pattern.strip().lower()
        if not norm_pat:
            continue
        if norm_pat.startswith("*."):
            suffix = norm_pat[1:]  # e.g. .github.com
            if norm_host.endswith(suffix) or norm_host == norm_pat[2:]:
                return True
        elif norm_host == norm_pat or norm_host.endswith(f".{norm_pat}"):
            return True

    return False


async def _pipe_streams(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while not reader.at_eof():
            data = await reader.read(8192)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


class SandboxDomainProxy:
    """Lightweight HTTP/HTTPS domain-filtering proxy for the build sandbox."""

    def __init__(self, allowed_endpoints: List[str], bind_host: str = "0.0.0.0"):
        self.allowed_endpoints = [e.strip().lower() for e in allowed_endpoints if e.strip()]
        self.bind_host = bind_host
        self.port = 0
        self.server: Optional[asyncio.Server] = None
        self.blocked_attempts: List[str] = []
        self.allowed_attempts: List[str] = []

    async def handle_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await client_reader.readline()
            if not request_line:
                client_writer.close()
                return

            line_str = request_line.decode("utf-8", errors="replace").strip()
            parts = line_str.split()
            if len(parts) < 2:
                client_writer.close()
                return

            method, target = parts[0].upper(), parts[1]

            # Parse host and port
            if method == "CONNECT":
                host_port = target.split(":")
                target_host = host_port[0]
                target_port = int(host_port[1]) if len(host_port) > 1 else 443
            else:
                m = re.match(r"^https?://([^/]+)", target, re.IGNORECASE)
                if m:
                    host_port = m.group(1).split(":")
                    target_host = host_port[0]
                    target_port = int(host_port[1]) if len(host_port) > 1 else 80
                else:
                    client_writer.close()
                    return

            # Validate against approved endpoints
            if not is_endpoint_allowed(target_host, self.allowed_endpoints):
                self.blocked_attempts.append(target_host)
                resp = (
                    b"HTTP/1.1 403 Forbidden\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Connection: close\r\n\r\n"
                    b"Blocked by RoostOS Build Sandbox: destination not in approved allowlist\r\n"
                )
                client_writer.write(resp)
                await client_writer.drain()
                client_writer.close()
                return

            self.allowed_attempts.append(target_host)

            # Establish upstream connection
            upstream_reader, upstream_writer = await asyncio.open_connection(target_host, target_port)

            if method == "CONNECT":
                # Consume remaining headers
                while True:
                    hdr = await client_reader.readline()
                    if not hdr or hdr in (b"\r\n", b"\n", b""):
                        break
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await client_writer.drain()
            else:
                upstream_writer.write(request_line)
                await upstream_writer.drain()

            await asyncio.gather(
                _pipe_streams(client_reader, upstream_writer),
                _pipe_streams(upstream_reader, client_writer),
            )
        except Exception:
            try:
                client_writer.close()
            except Exception:
                pass

    async def start(self) -> int:
        self.server = await asyncio.start_server(self.handle_client, self.bind_host, 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()


class SandboxNetworkFilter:
    """Manages lifecycle of sandbox proxy server in a background thread."""

    def __init__(self, allowed_endpoints: List[str], bind_host: str = "0.0.0.0"):
        self.allowed_endpoints = allowed_endpoints
        self.bind_host = bind_host
        self.proxy = SandboxDomainProxy(allowed_endpoints, bind_host=bind_host)
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.port: int = 0

    def start(self) -> Tuple[str, int]:
        started_event = threading.Event()

        def _run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.port = self.loop.run_until_complete(self.proxy.start())
            started_event.set()
            self.loop.run_forever()

        self.thread = threading.Thread(target=_run_loop, daemon=True)
        self.thread.start()
        started_event.wait(timeout=5.0)

        # Detect host IP accessible from container
        host_ip = "host.docker.internal"
        return host_ip, self.port

    def get_proxy_env(self, host_override: Optional[str] = None) -> Dict[str, str]:
        host = host_override or "host.docker.internal"
        proxy_url = f"http://{host}:{self.port}"
        return {
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
            "http_proxy": proxy_url,
            "https_proxy": proxy_url,
            "NO_PROXY": "localhost,127.0.0.1",
            "no_proxy": "localhost,127.0.0.1",
        }

    def stop(self) -> None:
        if self.loop and self.proxy:
            try:
                fut = asyncio.run_coroutine_threadsafe(self.proxy.stop(), self.loop)
                fut.result(timeout=2.0)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
