import json
import time
import pytest
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


def test_firewall_dynamic_mac_schedule_blocking(
    router_api: RoostOSRouterAPI,
    lan_client: NodeExecutor,
    wan_host: str,
) -> None:
    """
    Validates live firewall dynamic MAC blocking:
    1. LAN client accesses WAN web server -> socket connection succeeds.
    2. Test adds client's MAC address to blocked_clients dynamic set via API.
    3. LAN client attempts connection again -> receives socket error / timeout.
    4. Test removes client's MAC address from blocked set via API.
    5. LAN client attempts connection again -> succeeds immediately.
    """
    client_mac = "02:42:ac:1e:02:32"

    # Step 1: Initial connectivity check - should succeed
    initial_probe = lan_client.probe_tcp_socket(host=wan_host, port=80, timeout=3.0)
    assert initial_probe.connected is True, f"Initial connection failed: {initial_probe.error_message}"

    # Step 2: Block client MAC dynamically
    block_success = router_api.block_mac_address(client_mac)
    assert block_success is True, "Failed to execute MAC block on router"

    # Verify MAC appears in active dynamic set
    blocked_list = router_api.get_blocked_clients()
    assert client_mac.lower() in [m.lower() for m in blocked_list], f"MAC {client_mac} not found in blocked_clients set"

    # Allow firewall state table brief settling time
    time.sleep(0.5)

    # Step 3: Connection attempt while blocked - must FAIL with socket timeout or drop
    blocked_probe = lan_client.probe_tcp_socket(host=wan_host, port=80, timeout=2.0)
    assert blocked_probe.connected is False, "Client was able to connect despite active MAC block"
    assert (
        "timed out" in (blocked_probe.error_message or "").lower()
        or "refused" in (blocked_probe.error_message or "").lower()
        or "failed" in (blocked_probe.error_message or "").lower()
    )

    # Step 4: Unblock client MAC
    unblock_success = router_api.unblock_mac_address(client_mac)
    assert unblock_success is True, "Failed to remove MAC block on router"

    time.sleep(0.5)

    # Step 5: Connection attempt after unblocking - should SUCCEED
    restored_probe = lan_client.probe_tcp_socket(host=wan_host, port=80, timeout=3.0)
    assert restored_probe.connected is True, f"Connection did not restore after unblocking: {restored_probe.error_message}"


def test_firewall_custom_input_rule_drop(
    router_api: RoostOSRouterAPI,
    lan_client: NodeExecutor,
) -> None:
    """
    Validates custom input rules on the router:
    Attempting to access non-allowed closed or dropped ports on the router yields connection refusal or drop.
    """
    router_lan_ip = "172.30.2.1"

    # Web console port 8000 is allowed on LAN bridge
    web_probe = lan_client.probe_tcp_socket(host=router_lan_ip, port=8000, timeout=3.0)
    assert web_probe.connected is True, f"Web console port 8000 not reachable: {web_probe.error_message}"

    # Unopened port (e.g. 9999) should not connect
    closed_probe = lan_client.probe_tcp_socket(host=router_lan_ip, port=9999, timeout=2.0)
    assert closed_probe.connected is False, "Unopened port 9999 connected unexpectedly"
