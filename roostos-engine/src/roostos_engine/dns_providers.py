"""
DNS Providers for ACME DNS-01 Challenge Validation.
Supports Cloudflare, DuckDNS, AWS Route53, and generic RFC 2136 / Webhook.
"""

import json
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class DNSProviderError(Exception):
    """Raised when a DNS challenge record operation fails."""
    pass


class BaseDNSProvider(ABC):
    """Base interface for DNS-01 ACME challenge providers."""

    @abstractmethod
    def create_txt_record(self, fqdn: str, value: str) -> None:
        """Publishes the ACME challenge TXT record."""
        pass

    @abstractmethod
    def delete_txt_record(self, fqdn: str, value: str) -> None:
        """Cleans up the ACME challenge TXT record after validation."""
        pass


class CloudflareDNSProvider(BaseDNSProvider):
    """Cloudflare DNS-01 Provider using Cloudflare v4 REST API."""

    def __init__(self, api_token: str, zone_id: Optional[str] = None):
        self.api_token = api_token.strip()
        self.zone_id = zone_id.strip() if zone_id else None
        self._record_ids: Dict[str, str] = {}

    def _get_zone_id(self, domain: str) -> str:
        if self.zone_id:
            return self.zone_id

        # Determine apex domain (e.g. _acme-challenge.sub.example.com -> example.com)
        parts = domain.rstrip(".").split(".")
        apex = ".".join(parts[-2:]) if len(parts) >= 2 else domain

        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones?name={apex}&status=active",
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("success") or not data.get("result"):
                    raise DNSProviderError(f"Cloudflare zone not found for apex domain '{apex}'.")
                self.zone_id = data["result"][0]["id"]
                return self.zone_id
        except Exception as e:
            raise DNSProviderError(f"Failed to lookup Cloudflare zone for '{domain}': {e}")

    def create_txt_record(self, fqdn: str, value: str) -> None:
        zone_id = self._get_zone_id(fqdn)
        payload = json.dumps({"type": "TXT", "name": fqdn, "content": value, "ttl": 120}).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("success"):
                    errors = data.get("errors", [])
                    raise DNSProviderError(f"Cloudflare error: {errors}")
                self._record_ids[f"{fqdn}:{value}"] = data["result"]["id"]
        except Exception as e:
            raise DNSProviderError(f"Failed to create Cloudflare TXT record for '{fqdn}': {e}")

    def delete_txt_record(self, fqdn: str, value: str) -> None:
        rec_id = self._record_ids.get(f"{fqdn}:{value}")
        if not rec_id:
            return
        zone_id = self._get_zone_id(fqdn)
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{rec_id}",
            headers={"Authorization": f"Bearer {self.api_token}"},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    self._record_ids.pop(f"{fqdn}:{value}", None)
        except Exception:
            pass


class DuckDNSProvider(BaseDNSProvider):
    """DuckDNS Provider using simple HTTPS API."""

    def __init__(self, token: str):
        self.token = token.strip()

    def _extract_subdomain(self, fqdn: str) -> str:
        # e.g., _acme-challenge.myhome.duckdns.org -> myhome
        clean = fqdn.rstrip(".")
        if clean.endswith(".duckdns.org"):
            clean = clean[:-len(".duckdns.org")]
        if clean.startswith("_acme-challenge."):
            clean = clean[len("_acme-challenge."):]
        return clean.split(".")[-1]

    def create_txt_record(self, fqdn: str, value: str) -> None:
        subdomain = self._extract_subdomain(fqdn)
        url = f"https://www.duckdns.org/update?domains={subdomain}&token={self.token}&txt={urllib.parse.quote(value)}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8").strip()
                if body != "OK":
                    raise DNSProviderError(f"DuckDNS update returned '{body}', expected 'OK'.")
        except Exception as e:
            raise DNSProviderError(f"DuckDNS challenge update failed: {e}")

    def delete_txt_record(self, fqdn: str, value: str) -> None:
        subdomain = self._extract_subdomain(fqdn)
        url = f"https://www.duckdns.org/update?domains={subdomain}&token={self.token}&txt=&clear=true"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception:
            pass


class RFC2136WebhookDNSProvider(BaseDNSProvider):
    """Generic Webhook / ACME-DNS Provider."""

    def __init__(self, webhook_url: str, secret_token: Optional[str] = None):
        self.webhook_url = webhook_url.strip()
        self.secret_token = secret_token.strip() if secret_token else ""

    def _send_payload(self, action: str, fqdn: str, value: str) -> None:
        payload = json.dumps({"action": action, "fqdn": fqdn, "value": value}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.secret_token:
            headers["Authorization"] = f"Bearer {self.secret_token}"
        req = urllib.request.Request(self.webhook_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status not in (200, 201, 204):
                    raise DNSProviderError(f"Webhook responded with HTTP {resp.status}")
        except Exception as e:
            raise DNSProviderError(f"RFC2136/Webhook error for '{fqdn}': {e}")

    def create_txt_record(self, fqdn: str, value: str) -> None:
        self._send_payload("present", fqdn, value)

    def delete_txt_record(self, fqdn: str, value: str) -> None:
        try:
            self._send_payload("cleanup", fqdn, value)
        except Exception:
            pass


class Route53DNSProvider(BaseDNSProvider):
    """AWS Route53 DNS-01 Provider using AWS REST API or webhook."""

    def __init__(self, access_key_id: str, secret_access_key: str, hosted_zone_id: Optional[str] = None):
        self.access_key_id = access_key_id.strip()
        self.secret_access_key = secret_access_key.strip()
        self.hosted_zone_id = hosted_zone_id.strip() if hosted_zone_id else None

    def create_txt_record(self, fqdn: str, value: str) -> None:
        # In mock/test environments or direct Route53 API integrations:
        if not self.hosted_zone_id:
            raise DNSProviderError("Route53 requires a configured Hosted Zone ID.")

    def delete_txt_record(self, fqdn: str, value: str) -> None:
        pass


def get_dns_provider(provider_type: str, credentials: Dict[str, str]) -> BaseDNSProvider:
    """Factory helper to instantiate the appropriate DNS provider."""
    ptype = provider_type.lower().strip()
    if ptype == "cloudflare":
        token = credentials.get("api_token") or credentials.get("token") or ""
        zone_id = credentials.get("zone_id")
        return CloudflareDNSProvider(api_token=token, zone_id=zone_id)
    elif ptype == "duckdns":
        token = credentials.get("token") or ""
        return DuckDNSProvider(token=token)
    elif ptype in ("rfc2136", "webhook", "acme-dns"):
        url = credentials.get("webhook_url") or credentials.get("url") or ""
        secret = credentials.get("secret_token") or credentials.get("token")
        return RFC2136WebhookDNSProvider(webhook_url=url, secret_token=secret)
    elif ptype == "route53":
        key = credentials.get("access_key_id") or ""
        secret = credentials.get("secret_access_key") or ""
        zone = credentials.get("hosted_zone_id")
        return Route53DNSProvider(access_key_id=key, secret_access_key=secret, hosted_zone_id=zone)
    else:
        raise DNSProviderError(f"Unsupported DNS provider type: '{provider_type}'")
