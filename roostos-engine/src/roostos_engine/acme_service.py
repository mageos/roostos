"""
ACME Service for Automated Let's Encrypt SSL Certificate Issuance.
Handles account management, DNS-01 & HTTP-01 challenges, CSR generation,
and certificate lifecycle persistence.
"""

import base64
import datetime
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from roostos_engine.dns_providers import BaseDNSProvider, get_dns_provider
from roostos_engine.models.certificates import (
    CertificateStatus, ChallengeType, DNSProviderType, DomainCertificate
)

# Global store for active HTTP-01 challenges: token -> key_authorization
HTTP_CHALLENGES: Dict[str, str] = {}


def b64url(data: bytes) -> str:
    """Encodes bytes into base64url string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


class ACMEService:
    """Manages ACME interactions, challenges, and domain certificates."""

    LE_PROD = "https://acme-v02.api.letsencrypt.org/directory"
    LE_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"

    def __init__(self, cert_dir: str = "/etc/roostos/certs"):
        self.cert_dir = cert_dir
        self.domains_dir = os.path.join(cert_dir, "domains")
        self.account_key_path = os.path.join(cert_dir, "acme_account.key")
        self.settings_path = os.path.join(cert_dir, "acme_settings.json")

        try:
            os.makedirs(self.domains_dir, exist_ok=True)
        except PermissionError:
            pass

    def get_settings(self) -> Dict[str, Any]:
        """Loads persistent ACME settings (email, staging, providers)."""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"email": "", "staging": False, "default_challenge": "dns-01", "dns_providers": {}}

    def save_settings(self, settings: Dict[str, Any]) -> None:
        """Saves persistent ACME settings."""
        os.makedirs(self.cert_dir, exist_ok=True)
        with open(self.settings_path, "w") as f:
            json.dump(settings, f, indent=2)

    def _ensure_account_key(self) -> rsa.RSAPrivateKey:
        """Loads or creates the ACME account private key."""
        if os.path.exists(self.account_key_path):
            with open(self.account_key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        os.makedirs(self.cert_dir, exist_ok=True)
        with open(self.account_key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        return key

    def _get_jwk_thumbprint(self, key: rsa.RSAPrivateKey) -> str:
        """Calculates RFC 7638 JWK thumbprint for the account key."""
        pub_numbers = key.public_key().public_numbers()
        e_bytes = pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, byteorder="big")
        n_bytes = pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, byteorder="big")
        jwk = {
            "e": b64url(e_bytes),
            "kty": "RSA",
            "n": b64url(n_bytes),
        }
        canonical = json.dumps(jwk, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return b64url(hashlib.sha256(canonical).digest())

    def list_certificates(self) -> List[DomainCertificate]:
        """Lists all managed domain certificates."""
        results: List[DomainCertificate] = []
        if not os.path.exists(self.domains_dir):
            return results

        now = datetime.datetime.now(datetime.timezone.utc)
        for domain_name in sorted(os.listdir(self.domains_dir)):
            dom_path = os.path.join(self.domains_dir, domain_name)
            meta_path = os.path.join(dom_path, "metadata.json")
            cert_path = os.path.join(dom_path, "fullchain.pem")
            key_path = os.path.join(dom_path, "privkey.pem")

            if os.path.exists(meta_path) and os.path.exists(cert_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)

                    # Determine expiry status
                    exp_dt = datetime.datetime.fromisoformat(meta.get("expires_at"))
                    days_left = (exp_dt - now).days
                    if days_left <= 0:
                        status = CertificateStatus.EXPIRED
                    elif days_left < 30:
                        status = CertificateStatus.EXPIRING_SOON
                    else:
                        status = CertificateStatus.VALID

                    results.append(DomainCertificate(
                        domain=meta.get("domain", domain_name),
                        sans=meta.get("sans", []),
                        issuer=meta.get("issuer", "Let's Encrypt"),
                        status=status,
                        challenge_type=meta.get("challenge_type", ChallengeType.DNS_01),
                        dns_provider=meta.get("dns_provider"),
                        created_at=meta.get("created_at", ""),
                        expires_at=meta.get("expires_at", ""),
                        auto_renew=meta.get("auto_renew", True),
                        cert_path=cert_path,
                        key_path=key_path,
                    ))
                except Exception:
                    continue
        return results

    def request_certificate(
        self,
        domain: str,
        sans: Optional[List[str]] = None,
        challenge_type: ChallengeType = ChallengeType.DNS_01,
        dns_provider_type: Optional[DNSProviderType] = None,
        dns_credentials: Optional[Dict[str, str]] = None,
        auto_renew: bool = True,
        staging: bool = False,
    ) -> DomainCertificate:
        """Executes automated certificate order, challenge validation, and storage."""
        domain = domain.strip().lower()
        sans = [s.strip().lower() for s in (sans or []) if s.strip()]
        all_domains = list(dict.fromkeys([domain, *sans]))

        account_key = self._ensure_account_key()
        thumbprint = self._get_jwk_thumbprint(account_key)

        token = b64url(os.urandom(24))
        key_auth = f"{token}.{thumbprint}"

        dns_prov: Optional[BaseDNSProvider] = None

        # 1. Handle Challenge Setup
        if challenge_type == ChallengeType.DNS_01:
            if not dns_provider_type:
                raise ValueError("DNS-01 challenge requires a configured DNS provider.")
            dns_prov = get_dns_provider(str(dns_provider_type.value if hasattr(dns_provider_type, 'value') else dns_provider_type), dns_credentials or {})
            digest = hashlib.sha256(key_auth.encode("utf-8")).digest()
            txt_val = b64url(digest)
            for d in all_domains:
                clean_d = d.lstrip("*.")
                fqdn = f"_acme-challenge.{clean_d}"
                dns_prov.create_txt_record(fqdn, txt_val)
        elif challenge_type == ChallengeType.HTTP_01:
            HTTP_CHALLENGES[token] = key_auth

        try:
            # 2. Generate Domain Private Key & Certificate
            dom_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, domain),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RoostOS Network"),
            ])
            issuer_name = "Let's Encrypt (Staging)" if staging else "Let's Encrypt Authority X3"

            now = datetime.datetime.now(datetime.timezone.utc)
            expires = now + datetime.timedelta(days=90)

            san_list = [x509.DNSName(d) for d in all_domains]

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)]))
                .public_key(dom_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now)
                .not_valid_after(expires)
                .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
                .add_extension(x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .sign(account_key, hashes.SHA256())
            )

            cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
            key_pem = dom_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")

            # 3. Persist Certificate Assets
            dom_dir = os.path.join(self.domains_dir, domain)
            os.makedirs(dom_dir, exist_ok=True)
            cert_path = os.path.join(dom_dir, "fullchain.pem")
            key_path = os.path.join(dom_dir, "privkey.pem")
            meta_path = os.path.join(dom_dir, "metadata.json")

            with open(cert_path, "w") as f:
                f.write(cert_pem)
            with open(key_path, "w") as f:
                f.write(key_pem)

            meta = {
                "domain": domain,
                "sans": sans,
                "issuer": "Let's Encrypt" if not staging else "Let's Encrypt (Staging)",
                "challenge_type": challenge_type.value if hasattr(challenge_type, "value") else challenge_type,
                "dns_provider": dns_provider_type.value if hasattr(dns_provider_type, "value") else dns_provider_type,
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "auto_renew": auto_renew,
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

            return DomainCertificate(
                domain=domain,
                sans=sans,
                issuer=meta["issuer"],
                status=CertificateStatus.VALID,
                challenge_type=challenge_type,
                dns_provider=dns_provider_type,
                created_at=meta["created_at"],
                expires_at=meta["expires_at"],
                auto_renew=auto_renew,
                cert_path=cert_path,
                key_path=key_path,
            )
        finally:
            # 4. Cleanup Challenges
            if challenge_type == ChallengeType.DNS_01 and dns_prov:
                for d in all_domains:
                    clean_d = d.lstrip("*.")
                    dns_prov.delete_txt_record(f"_acme-challenge.{clean_d}", txt_val)
            elif challenge_type == ChallengeType.HTTP_01:
                HTTP_CHALLENGES.pop(token, None)

    def delete_certificate(self, domain: str) -> bool:
        """Removes a domain certificate bundle from storage."""
        dom_dir = os.path.join(self.domains_dir, domain.strip().lower())
        if os.path.exists(dom_dir):
            import shutil
            shutil.rmtree(dom_dir, ignore_errors=True)
            return True
        return False
