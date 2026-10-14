"""Mock CertificateManager and ACME service for testing and development environments."""

from typing import Dict, Any, List, Optional
from roostos_engine.cert_manager import CertificateManager


class MockAcmeService:
    """In-memory ACME certificate lifecycle simulator."""

    def __init__(self) -> None:
        self.settings: Dict[str, Any] = {
            "email": "admin@roost.lan",
            "staging": True,
            "default_challenge": "http-01",
            "dns_providers": {},
        }
        self.certificates: List[Dict[str, Any]] = [
            {
                "domain": "home.roost.lan",
                "expires": "2027-01-01T00:00:00Z",
                "staging": True,
                "challenge_type": "http-01",
            }
        ]

    def get_settings(self) -> Dict[str, Any]:
        return dict(self.settings)

    def save_settings(self, new_settings: Dict[str, Any]) -> bool:
        self.settings.update(new_settings)
        return True

    def list_certificates(self) -> List[Dict[str, Any]]:
        return list(self.certificates)

    def request_certificate(
        self,
        domain: str,
        email: Optional[str] = None,
        staging: bool = True,
        challenge_type: str = "http-01",
        dns_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = {
            "domain": domain,
            "expires": "2027-01-01T00:00:00Z",
            "staging": staging,
            "challenge_type": challenge_type,
            "dns_provider": dns_provider,
        }
        self.certificates = [c for c in self.certificates if c["domain"] != domain]
        self.certificates.append(record)
        return {"domain": domain, "status": "issued", "certificate": record}

    def delete_certificate(self, domain: str) -> bool:
        initial_len = len(self.certificates)
        self.certificates = [c for c in self.certificates if c["domain"] != domain]
        return len(self.certificates) < initial_len


class MockCertificateManager(CertificateManager):
    """Zero-filesystem CertificateManager simulator."""

    def __init__(self, cert_dir: str = "/tmp/mock-certs") -> None:
        self.cert_dir = cert_dir
        self.ca_cert_path = f"{cert_dir}/ca.crt"
        self.ca_key_path = f"{cert_dir}/ca.key"
        self.plugins_cert_dir = f"{cert_dir}/plugins"
        self.services_cert_dir = f"{cert_dir}/services"
        self.server_cert_dir = f"{cert_dir}/server"
        self.acme = MockAcmeService()

    def get_cert_status(self) -> Dict[str, Any]:
        return {
            "root_ca": {
                "valid": True,
                "subject": "CN=RoostOS Mock CA",
                "issuer": "CN=RoostOS Mock CA",
                "expires": "2036-01-01T00:00:00Z",
            },
            "server": {
                "valid": True,
                "subject": "CN=roost-router.lan",
                "expires": "2027-01-01T00:00:00Z",
            },
            "domains": {c["domain"]: c for c in self.acme.list_certificates()},
        }

    def get_root_ca_pem(self) -> str:
        return (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIBkTCB+wIBADANBgkqhkiG9w0BAQsFADAhMR8wHQYDVQQDDBZSb29zdE9TIE1v\n"
            "Y2sgUm9vdCBDQTAeFw0yNjEwMTQwMDAwMDBaFw0zNjEwMTQwMDAwMDBaMCExHzAd\n"
            "BgNVBAMMFlJvb3N0T1MgTW9jayBSb290IENBMFkwEwYHKoZIzj0CAQYIKoZIzj0D\n"
            "AQcDQgAE9z9z0MOCK=MOCK=MOCK=ROOT=CA=CERTIFICATE===\n"
            "-----END CERTIFICATE-----\n"
        )

    def issue_server_cert(
        self,
        hostname: str = "roost-router",
        domain: str = "lan",
        san_dns: Optional[List[str]] = None,
        san_ips: Optional[List[str]] = None
    ) -> Dict[str, str]:
        return {
            "cert_pem": self.get_root_ca_pem(),
            "key_pem": "MOCK_KEY_PEM",
            "cert_path": f"{self.server_cert_dir}/server.crt",
            "key_path": f"{self.server_cert_dir}/server.key",
        }

    def issue_service_cert(self, service_name: str, scopes: Optional[List[str]] = None) -> Dict[str, str]:
        return {"cert_pem": self.get_root_ca_pem(), "key_pem": "MOCK_KEY_PEM"}

    def issue_plugin_cert(self, plugin_id: str, scopes: Optional[List[str]] = None) -> Dict[str, str]:
        return {"cert_pem": self.get_root_ca_pem(), "key_pem": "MOCK_KEY_PEM"}

    def verify_client_cert(self, cert_pem: str) -> Dict[str, Any]:
        return {"valid": True, "entity_id": "mock_admin", "role": "admin", "scopes": ["admin", "root"]}
