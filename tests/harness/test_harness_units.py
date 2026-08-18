import pytest
from unittest.mock import MagicMock, patch
from tests.harness.models import CommandResult, SocketProbeResult, NodeInfo, ScenarioConfig
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


def test_command_result_success() -> None:
    """Verifies CommandResult success evaluation and properties."""
    res_ok = CommandResult(command="echo ok", exit_code=0, stdout="ok")
    assert res_ok.success is True

    res_fail = CommandResult(command="false", exit_code=1, stderr="error")
    assert res_fail.success is False


def test_socket_probe_result_creation() -> None:
    """Verifies SocketProbeResult schema."""
    probe = SocketProbeResult(
        host="172.30.1.100",
        port=80,
        protocol="tcp",
        connected=True,
        latency_ms=1.5,
    )
    assert probe.connected is True
    assert probe.port == 80


def test_node_executor_ping_command_construction() -> None:
    """Verifies NodeExecutor formats docker exec ping command correctly."""
    executor = NodeExecutor(container_name="client-lan")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="3 packets transmitted", stderr="")
        res = executor.ping("172.30.1.100", count=3)
        
        assert res.success is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["docker", "exec", "client-lan", "ping", "-c", "3", "-W", "5", "172.30.1.100"]


def test_router_api_token_header() -> None:
    """Verifies Router API client headers include bearer token."""
    api = RoostOSRouterAPI(base_url="http://localhost:8000")
    api.token = "test-bearer-token"
    headers = api._headers()
    assert headers["Authorization"] == "Bearer test-bearer-token"
    assert headers["Content-Type"] == "application/json"
