"""
Unit tests for ACME Service, DNS Providers, and automated certificate management.
"""

import json
from unittest.mock import MagicMock, patch

from roostos_engine.acme_service import ACMEService, HTTP_CHALLENGES
from roostos_engine.dns_providers import (
    CloudflareDNSProvider,
    DNSProviderError,
    DuckDNSProvider,
    RFC2136WebhookDNSProvider,
    get_dns_provider,
)
from roostos_engine.models.certificates import (
    CertificateStatus,
    ChallengeType,
    DNSProviderType,
)


def test_duckdns_provider():
    provider = DuckDNSProvider(token="test-token-123")
    assert provider._extract_subdomain("_acme-challenge.myrouter.duckdns.org") == "myrouter"

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"OK"
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        provider.create_txt_record("_acme-challenge.myrouter.duckdns.org", "test-txt-hash")
        assert mock_urlopen.called
        call_url = mock_urlopen.call_args[0][0].full_url
        assert "domains=myrouter" in call_url
        assert "txt=test-txt-hash" in call_url

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        provider.delete_txt_record("_acme-challenge.myrouter.duckdns.org", "test-txt-hash")
        assert mock_urlopen.called
        call_url = mock_urlopen.call_args[0][0].full_url
        assert "clear=true" in call_url


def test_cloudflare_provider():
    provider = CloudflareDNSProvider(api_token="cf-token-abc")

    # Mock zone lookup & record creation
    zone_resp = MagicMock()
    zone_resp.read.return_value = json.dumps({
        "success": True,
        "result": [{"id": "zone-12345"}]
    }).encode("utf-8")
    zone_resp.__enter__.return_value = zone_resp

    rec_resp = MagicMock()
    rec_resp.read.return_value = json.dumps({
        "success": True,
        "result": {"id": "rec-67890"}
    }).encode("utf-8")
    rec_resp.__enter__.return_value = rec_resp

    del_resp = MagicMock()
    del_resp.read.return_value = json.dumps({"success": True}).encode("utf-8")
    del_resp.__enter__.return_value = del_resp

    with patch("urllib.request.urlopen", side_effect=[zone_resp, rec_resp, del_resp]):
        provider.create_txt_record("_acme-challenge.router.example.com", "hash-val")
        assert provider._record_ids.get("_acme-challenge.router.example.com:hash-val") == "rec-67890"

        provider.delete_txt_record("_acme-challenge.router.example.com", "hash-val")
        assert "_acme-challenge.router.example.com:hash-val" not in provider._record_ids


def test_get_dns_provider_factory():
    cf = get_dns_provider("cloudflare", {"api_token": "abc"})
    assert isinstance(cf, CloudflareDNSProvider)

    duck = get_dns_provider("duckdns", {"token": "xyz"})
    assert isinstance(duck, DuckDNSProvider)

    webhook = get_dns_provider("webhook", {"webhook_url": "https://example.com/acme"})
    assert isinstance(webhook, RFC2136WebhookDNSProvider)


def test_acme_service_request_dns01(tmp_path):
    cert_dir = str(tmp_path / "certs")
    acme = ACMEService(cert_dir=cert_dir)

    mock_duck = MagicMock()
    with patch("roostos_engine.acme_service.get_dns_provider", return_value=mock_duck):
        cert = acme.request_certificate(
            domain="router.duckdns.org",
            sans=["*.router.duckdns.org"],
            challenge_type=ChallengeType.DNS_01,
            dns_provider_type=DNSProviderType.DUCKDNS,
            dns_credentials={"token": "fake-token"},
            auto_renew=True,
        )

        assert cert.domain == "router.duckdns.org"
        assert cert.status == CertificateStatus.VALID
        assert cert.auto_renew is True
        assert mock_duck.create_txt_record.called
        assert mock_duck.delete_txt_record.called

    # Verify listing
    certs = acme.list_certificates()
    assert len(certs) == 1
    assert certs[0].domain == "router.duckdns.org"

    # Verify deletion
    assert acme.delete_certificate("router.duckdns.org") is True
    assert len(acme.list_certificates()) == 0


def test_acme_service_request_http01(tmp_path):
    cert_dir = str(tmp_path / "certs")
    acme = ACMEService(cert_dir=cert_dir)

    cert = acme.request_certificate(
        domain="edge.myhome.org",
        challenge_type=ChallengeType.HTTP_01,
        auto_renew=False,
        staging=True,
    )

    assert cert.domain == "edge.myhome.org"
    assert "Staging" in cert.issuer
    assert cert.status == CertificateStatus.VALID
    # Verify cleanup of HTTP challenge
    assert len(HTTP_CHALLENGES) == 0
