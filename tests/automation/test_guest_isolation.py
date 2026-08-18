import pytest
from tests.harness.client import NodeExecutor


def test_guest_reaches_wan(guest_client: NodeExecutor, wan_host: str) -> None:
    """Verifies that guest devices have working outbound internet connectivity."""
    probe = guest_client.probe_tcp_socket(host=wan_host, port=80, timeout=3.0)
    assert probe.connected is True, f"Guest client could not reach WAN web service: {probe.error_message}"


def test_guest_isolated_from_lan_clients(guest_client: NodeExecutor) -> None:
    """
    Verifies network isolation: Guest devices cannot communicate with
    private devices on the primary LAN subnet (172.30.2.0/24).
    """
    lan_client_ip = "172.30.2.50"
    probe = guest_client.probe_tcp_socket(host=lan_client_ip, port=80, timeout=2.0)
    assert probe.connected is False, f"Guest client breached isolation and reached LAN device at {lan_client_ip}"


def test_guest_restricted_from_router_admin(guest_client: NodeExecutor) -> None:
    """
    Verifies that Guest clients cannot access router administration interfaces
    (e.g., port 8000 Web UI / 9090 Cockpit / 22 SSH).
    """
    router_guest_ip = "172.30.3.1"
    
    # Port 8000 Web Admin should be blocked/restricted for guest network
    probe_admin = guest_client.probe_tcp_socket(host=router_guest_ip, port=8000, timeout=2.0)
    assert probe_admin.connected is False, "Guest client was able to connect to Web Admin console"

    # Port 22 SSH should also be inaccessible
    probe_ssh = guest_client.probe_tcp_socket(host=router_guest_ip, port=22, timeout=2.0)
    assert probe_ssh.connected is False, "Guest client was able to connect to SSH port"
