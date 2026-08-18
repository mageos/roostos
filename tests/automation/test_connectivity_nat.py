import json
import pytest
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


def test_lan_to_wan_ping_connectivity(lan_client: NodeExecutor, wan_host: str) -> None:
    """Verifies that LAN clients can send ICMP echo packets to external WAN hosts."""
    res = lan_client.ping(target_host=wan_host, count=3, timeout=5.0)
    assert res.success is True, f"Ping from LAN to WAN failed: {res.stderr or res.stdout}"
    assert "0% packet loss" in res.stdout or " 0% packet loss" in res.stdout


def test_lan_to_wan_nat_masquerading(lan_client: NodeExecutor, wan_host: str) -> None:
    """
    Verifies that NAT / IPMasquerade on the WAN interface correctly rewrites
    the source IP of outgoing LAN client packets to the router's WAN address (172.30.1.2).
    """
    res = lan_client.http_get(url=f"http://{wan_host}/test-nat", timeout=5.0)
    assert res.success is True, f"HTTP GET to WAN host failed: {res.stderr or res.stdout}"
    
    # Extract JSON body from response
    lines = res.stdout.split("\r\n\r\n")
    if len(lines) < 2:
        lines = res.stdout.split("\n\n")
    
    body = lines[-1].strip()
    data = json.loads(body)
    
    assert data.get("status") == "online"
    # The upstream server should see the Router's WAN IP (172.30.1.2), NOT the LAN client IP (172.30.2.50)
    seen_ip = data.get("client_ip")
    assert seen_ip == "172.30.1.2", f"Expected masqueraded WAN IP 172.30.1.2, but server saw {seen_ip}"
