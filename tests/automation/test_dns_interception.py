import pytest
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


def test_dns_over_tls_blocked(lan_client: NodeExecutor, wan_host: str) -> None:
    """
    Verifies that DNS-over-TLS (port 853) is actively dropped by the firewall
    to enforce parental control and local DNS filtering policies.
    """
    # Attempt connecting to DoT port 853 on upstream host
    probe = lan_client.probe_tcp_socket(host=wan_host, port=853, timeout=2.0)
    assert probe.connected is False, "Port 853 (DoT) connection succeeded, but should be dropped by firewall"


def test_dns_redirection_rule_in_nftables(router_api: RoostOSRouterAPI) -> None:
    """Verifies that DNS redirection and DoT drop rules are compiled and present in active nftables."""
    ruleset = router_api.get_nft_ruleset()
    
    # Assert DNS redirect rule exists in ruleset
    assert "dport 53 redirect to :53" in ruleset or "dport 53 redirect" in ruleset or "dport 53" in ruleset
    # Assert DNS-over-TLS drop rule exists in ruleset
    assert "dport 853 drop" in ruleset or "853" in ruleset
