import json
import subprocess
import time
from typing import List, Optional
from tests.harness.models import CommandResult, SocketProbeResult


class NodeExecutor:
    """Executes network actions and commands inside a target container node."""

    def __init__(self, container_name: str, default_timeout: float = 10.0) -> None:
        self.container_name = container_name
        self.default_timeout = default_timeout

    def run_command(self, cmd: List[str], timeout: Optional[float] = None) -> CommandResult:
        """Runs an arbitrary command inside the container via docker exec."""
        exec_timeout = timeout or self.default_timeout
        docker_cmd = ["docker", "exec", self.container_name] + cmd
        start_time = time.time()

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=exec_timeout
            )
            duration_ms = (time.time() - start_time) * 1000.0
            return CommandResult(
                command=" ".join(cmd),
                exit_code=res.returncode,
                stdout=res.stdout.strip(),
                stderr=res.stderr.strip(),
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - start_time) * 1000.0
            return CommandResult(
                command=" ".join(cmd),
                exit_code=124,
                stdout="",
                stderr=f"Command timed out after {exec_timeout} seconds",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            return CommandResult(
                command=" ".join(cmd),
                exit_code=1,
                stdout="",
                stderr=f"Failed to execute command: {e}",
                duration_ms=duration_ms,
            )

    def ping(self, target_host: str, count: int = 3, timeout: float = 5.0) -> CommandResult:
        """Pings a target host/IP from within the container."""
        cmd = ["ping", "-c", str(count), "-W", str(int(timeout)), target_host]
        return self.run_command(cmd, timeout=timeout + 2.0)

    def http_get(self, url: str, timeout: float = 5.0, headers: Optional[List[str]] = None) -> CommandResult:
        """Performs an HTTP GET request using curl."""
        cmd = ["curl", "-sSL", "-i", "--max-time", str(timeout)]
        if headers:
            for h in headers:
                cmd.extend(["-H", h])
        cmd.append(url)
        return self.run_command(cmd, timeout=timeout + 2.0)

    def dns_query(self, domain: str, server: Optional[str] = None, timeout: float = 5.0) -> CommandResult:
        """Performs a DNS query using dig."""
        cmd = ["dig", "+short", f"+time={int(timeout)}", "+tries=1"]
        if server:
            cmd.append(f"@{server}")
        cmd.append(domain)
        return self.run_command(cmd, timeout=timeout + 2.0)

    def probe_tcp_socket(self, host: str, port: int, timeout: float = 3.0) -> SocketProbeResult:
        """Probes a TCP socket connection using Python inside the container."""
        py_script = (
            f"import socket, time\n"
            f"s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            f"s.settimeout({timeout})\n"
            f"t0 = time.time()\n"
            f"try:\n"
            f"    s.connect(('{host}', {port}))\n"
            f"    s.close()\n"
            f"    print('CONNECTED:' + str((time.time()-t0)*1000))\n"
            f"except Exception as e:\n"
            f"    print('ERROR:' + str(e))\n"
        )
        res = self.run_command(["python3", "-c", py_script], timeout=timeout + 2.0)
        
        if res.success and "CONNECTED:" in res.stdout:
            parts = res.stdout.split("CONNECTED:")
            latency = float(parts[1].split()[0]) if len(parts) > 1 else 0.0
            return SocketProbeResult(
                host=host,
                port=port,
                protocol="tcp",
                connected=True,
                latency_ms=latency,
            )
        else:
            err = res.stdout.replace("ERROR:", "").strip() if "ERROR:" in res.stdout else res.stderr
            return SocketProbeResult(
                host=host,
                port=port,
                protocol="tcp",
                connected=False,
                error_message=err or "Connection failed",
            )

    def get_ip_address(self, iface: str = "eth0") -> str:
        """Retrieves the IPv4 address assigned to a specific interface."""
        res = self.run_command(["ip", "-j", "-4", "addr", "show", iface])
        if res.success and res.stdout:
            try:
                data = json.loads(res.stdout)
                for addr_info in data[0].get("addr_info", []):
                    return addr_info.get("local", "")
            except Exception:
                pass
        return ""

    def get_mac_address(self, iface: str = "eth0") -> str:
        """Retrieves the MAC address assigned to a specific interface."""
        res = self.run_command(["cat", f"/sys/class/net/{iface}/address"])
        return res.stdout.strip() if res.success else ""
