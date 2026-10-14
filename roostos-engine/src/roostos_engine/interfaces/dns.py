"""DNS Resolver and Ad-Blocking Provider Protocol."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from roostos_engine.config import RoostConfig


@runtime_checkable
class DNSResolverProvider(Protocol):
    """Protocol for pluggable DNS server and ad-blocking providers (technitium, local, dnsmasq, mock)."""

    def get_status(self) -> Dict[str, Any]:
        """Returns the current DNS resolver and ad-blocking status."""
        ...

    def set_forwarders(self, forwarders: List[str]) -> bool:
        """Updates upstream DNS forwarders."""
        ...

    def set_ad_blocking(self, enabled: bool) -> bool:
        """Enables or disables DNS-level ad blocking."""
        ...


class MockDNSResolverProvider:
    """In-memory mock DNS provider."""

    def __init__(self, config: Optional[RoostConfig] = None):
        self.config = config
        self.forwarders: List[str] = ["1.1.1.1", "8.8.8.8"]
        self.ad_blocking_enabled: bool = True

    def get_status(self) -> Dict[str, Any]:
        return {
            "subsystem": "mock",
            "forwarders": list(self.forwarders),
            "ad_blocking_enabled": self.ad_blocking_enabled,
            "queries_blocked_today": 1284,
            "blocked_domains_count": 89400,
        }

    def set_forwarders(self, forwarders: List[str]) -> bool:
        self.forwarders = list(forwarders)
        return True

    def set_ad_blocking(self, enabled: bool) -> bool:
        self.ad_blocking_enabled = enabled
        return True
