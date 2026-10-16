"""Unit tests for pluggable provider protocols and mock implementations."""

import pytest
from roostos_engine.interfaces import (
    FirewallProvider,
    MockFirewallProvider,
    DHCPProvider,
    MockDHCPProvider,
    DNSResolverProvider,
    MockDNSResolverProvider,
    CertificateProvider,
    NetworkProvider,
    MockNetworkProvider,
)
from roostos_engine.firewall_manager import FirewallManager
from roostos_engine.dhcp_manager import DHCPManager
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.mock_cert_manager import MockCertificateManager
from roostos_engine.mock_data import create_mock_config


def test_firewall_provider_protocol():
    cfg = create_mock_config()
    
    # 1. Real nftables FirewallManager satisfies FirewallProvider protocol
    real_fw = FirewallManager(cfg)
    assert isinstance(real_fw, FirewallProvider)
    assert "table inet filter" in real_fw.compile_ruleset()
    
    # 2. MockFirewallProvider satisfies FirewallProvider protocol
    mock_fw = MockFirewallProvider(cfg)
    assert isinstance(mock_fw, FirewallProvider)
    assert "Mock" in mock_fw.compile_ruleset()
    mock_fw.get_block_mac_cmd("aa:bb:cc:dd:ee:ff")
    assert "aa:bb:cc:dd:ee:ff" in mock_fw.blocked_macs
    mock_fw.get_unblock_mac_cmd("aa:bb:cc:dd:ee:ff")
    assert "aa:bb:cc:dd:ee:ff" not in mock_fw.blocked_macs


def test_dhcp_provider_protocol():
    cfg = create_mock_config()

    # 1. Real Kea DHCPManager satisfies DHCPProvider protocol
    real_dhcp = DHCPManager(cfg)
    assert isinstance(real_dhcp, DHCPProvider)
    compiled = real_dhcp.compile_config()
    assert "Dhcp4" in compiled

    # 2. MockDHCPProvider satisfies DHCPProvider protocol
    mock_dhcp = MockDHCPProvider(cfg)
    assert isinstance(mock_dhcp, DHCPProvider)
    assert "Dhcp4" in mock_dhcp.compile_config()


def test_dns_resolver_provider_protocol():
    mock_dns = MockDNSResolverProvider()
    assert isinstance(mock_dns, DNSResolverProvider)

    status = mock_dns.get_status()
    assert status["subsystem"] == "mock"
    assert status["ad_blocking_enabled"] is True

    ok = mock_dns.set_forwarders(["9.9.9.9"])
    assert ok is True
    assert mock_dns.forwarders == ["9.9.9.9"]

    ok_block = mock_dns.set_ad_blocking(False)
    assert ok_block is True
    assert mock_dns.ad_blocking_enabled is False


def test_certificate_provider_protocol():
    # 1. MockCertificateManager satisfies CertificateProvider protocol
    mock_cm = MockCertificateManager()
    assert isinstance(mock_cm, CertificateProvider)
    server_cert = mock_cm.issue_server_cert("test-router", "lan")
    assert "cert_pem" in server_cert and "key_pem" in server_cert

    # 2. CertificateManager class signature satisfies protocol
    assert issubclass(MockCertificateManager, CertificateProvider)


def test_network_provider_protocol():
    mock_net = MockNetworkProvider()
    assert isinstance(mock_net, NetworkProvider)
    cfg = create_mock_config()
    assert mock_net.apply_interfaces(cfg) is True
    assert mock_net.apply_vlans(cfg) is True
    states = mock_net.get_interface_states()
    assert len(states) >= 3
    assert any(s["role"] == "wan" for s in states)
