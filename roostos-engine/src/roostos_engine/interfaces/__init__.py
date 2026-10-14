"""Pluggable Provider Protocols and Base Interfaces for RoostOS Container."""

from roostos_engine.repository import ConfigRepository
from roostos_engine.interfaces.firewall import FirewallProvider, MockFirewallProvider
from roostos_engine.interfaces.dhcp import DHCPProvider, MockDHCPProvider
from roostos_engine.interfaces.dns import DNSResolverProvider, MockDNSResolverProvider
from roostos_engine.interfaces.certificates import CertificateProvider
from roostos_engine.interfaces.network import NetworkProvider, MockNetworkProvider

__all__ = [
    "ConfigRepository",
    "FirewallProvider",
    "MockFirewallProvider",
    "DHCPProvider",
    "MockDHCPProvider",
    "DNSResolverProvider",
    "MockDNSResolverProvider",
    "CertificateProvider",
    "NetworkProvider",
    "MockNetworkProvider",
]
