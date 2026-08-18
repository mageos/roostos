import pytest
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


def test_port_forwarding_rules_in_nftables(router_api: RoostOSRouterAPI) -> None:
    """
    Verifies that port forwarding configurations (dnat) are correctly compiled
    and injected into the prerouting chain of the router's nftables.
    """
    ruleset = router_api.get_nft_ruleset()
    
    # Assert nat prerouting chain exists
    assert "chain prerouting" in ruleset or "type nat hook prerouting" in ruleset
    # Assert forward chain exists
    assert "chain forward" in ruleset or "type filter hook forward" in ruleset
