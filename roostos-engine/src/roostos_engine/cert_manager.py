"""
RoostOS Certificate Management Service (CertificateManager)

Handles X.509 Root CA generation, mTLS client certificate issuance for sidecar plugins
with embedded X.509 SAN scopes, HTTPS server TLS certificate generation, and certificate validation.
"""

import os
import datetime
import ipaddress
from typing import List, Dict, Any, Tuple, Optional
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

class CertificateManager:
    def __init__(self, cert_dir: str = "/etc/roostos/certs"):
        self.cert_dir = cert_dir
        self.ca_cert_path = os.path.join(cert_dir, "ca.crt")
        self.ca_key_path = os.path.join(cert_dir, "ca.key")
        self.plugins_cert_dir = os.path.join(cert_dir, "plugins")
        self.services_cert_dir = os.path.join(cert_dir, "services")
        self.server_cert_dir = os.path.join(cert_dir, "server")

        try:
            os.makedirs(self.cert_dir, exist_ok=True)
            os.makedirs(self.plugins_cert_dir, exist_ok=True)
            os.makedirs(self.services_cert_dir, exist_ok=True)
            os.makedirs(self.server_cert_dir, exist_ok=True)
        except PermissionError:
            pass

    def ensure_root_ca(self) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generates or loads the local RoostOS Root CA certificate and private key."""
        if os.path.exists(self.ca_cert_path) and os.path.exists(self.ca_key_path):
            with open(self.ca_key_path, "rb") as f:
                ca_key = serialization.load_pem_private_key(f.read(), password=None)
            with open(self.ca_cert_path, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read())
            return ca_cert, ca_key

        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "RoostOS Root Certificate Authority"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RoostOS Router Infrastructure"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(ca_key, hashes.SHA256())
        )

        with open(self.ca_key_path, "wb") as f:
            f.write(ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        with open(self.ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

        return ca_cert, ca_key

    def _issue_entity_cert(
        self,
        common_name: str,
        organization: str,
        dns_names: List[str],
        requested_scopes: List[str],
        dest_dir: str
    ) -> Dict[str, str]:
        """Helper to issue and save an X.509 client certificate."""
        ca_cert, ca_key = self.ensure_root_ca()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
        ])

        scopes_str = ",".join(requested_scopes) if requested_scopes else "none"
        san_list: List[x509.GeneralName] = [x509.DNSName(name) for name in dns_names]
        san_list.append(x509.UniformResourceIdentifier(f"roostos:scopes:{scopes_str}"))

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256())
        )

        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, "client.crt"), "w") as f:
            f.write(cert_pem)
        with open(os.path.join(dest_dir, "client.key"), "w") as f:
            f.write(key_pem)

        return {"cert_pem": cert_pem, "key_pem": key_pem, "ca_pem": ca_pem}

    def issue_plugin_cert(self, plugin_id: str, requested_scopes: List[str]) -> Dict[str, str]:
        """Issues an mTLS X.509 client certificate for a sidecar plugin."""
        dest_dir = os.path.join(self.plugins_cert_dir, plugin_id)
        dns_names = [f"{plugin_id}.roost.local", plugin_id]
        return self._issue_entity_cert(
            common_name=f"plugin-{plugin_id}",
            organization="RoostOS Plugins",
            dns_names=dns_names,
            requested_scopes=requested_scopes,
            dest_dir=dest_dir
        )

    def issue_service_cert(self, service_name: str, requested_scopes: List[str]) -> Dict[str, str]:
        """Issues an mTLS X.509 client certificate for an internal component/service."""
        dest_dir = os.path.join(self.services_cert_dir, service_name)
        dns_names = [f"{service_name}.roost.local", service_name, "localhost"]
        return self._issue_entity_cert(
            common_name=f"service-{service_name}",
            organization="RoostOS Services",
            dns_names=dns_names,
            requested_scopes=requested_scopes,
            dest_dir=dest_dir
        )

    def issue_server_cert(self, hostname: str = "roost-router", domain: str = "lan") -> Dict[str, str]:
        """Issues an HTTPS server TLS certificate for the Web Console."""
        ca_cert, ca_key = self.ensure_root_ca()
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, f"{hostname}.{domain}"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RoostOS Router"),
        ])

        san_list = [
            x509.DNSName(hostname),
            x509.DNSName(f"{hostname}.{domain}"),
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256())
        )

        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        key_pem = server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        with open(os.path.join(self.server_cert_dir, "server.crt"), "w") as f:
            f.write(cert_pem)
        with open(os.path.join(self.server_cert_dir, "server.key"), "w") as f:
            f.write(key_pem)

        return {"cert_pem": cert_pem, "key_pem": key_pem}

    def verify_client_cert(self, cert_pem: str) -> Dict[str, Any]:
        """Cryptographically verifies a client certificate against Root CA and extracts authorized scopes."""
        try:
            ca_cert, _ = self.ensure_root_ca()
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))

            # 1. Verify cryptographic signature using Root CA public key
            ca_cert.public_key().verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm
            )

            # 2. Check validity dates
            now = datetime.datetime.now(datetime.timezone.utc)
            if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
                return {"valid": False, "error": "Certificate is expired or not yet valid."}

            common_name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value

            scopes = []
            try:
                san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                for name in san_ext.value:
                    if isinstance(name, x509.UniformResourceIdentifier) and name.value.startswith("roostos:scopes:"):
                        scopes_raw = name.value.replace("roostos:scopes:", "")
                        scopes = [s.strip() for s in scopes_raw.split(",") if s.strip() and s.strip() != "none"]
            except Exception:
                pass

            return {
                "valid": True,
                "subject_cn": common_name,
                "scopes": scopes,
                "expires_at": cert.not_valid_after_utc.isoformat(),
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def get_cert_status(self) -> Dict[str, Any]:
        """Returns status of Root CA, HTTPS server cert, service certs, and plugin certs."""
        ca_cert, _ = self.ensure_root_ca()
        status: Dict[str, Any] = {
            "root_ca": {
                "issuer": ca_cert.issuer.rfc4514_string(),
                "expires_at": ca_cert.not_valid_after_utc.isoformat(),
                "valid": True,
            },
            "server_cert": None,
            "services": [],
            "plugins": []
        }

        server_crt_path = os.path.join(self.server_cert_dir, "server.crt")
        if os.path.exists(server_crt_path):
            with open(server_crt_path, "rb") as f:
                srv_cert = x509.load_pem_x509_certificate(f.read())
            status["server_cert"] = {
                "cn": srv_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                "expires_at": srv_cert.not_valid_after_utc.isoformat(),
            }

        if os.path.exists(self.services_cert_dir):
            for sid in os.listdir(self.services_cert_dir):
                svc_crt = os.path.join(self.services_cert_dir, sid, "client.crt")
                if os.path.exists(svc_crt):
                    with open(svc_crt, "r") as f:
                        v = self.verify_client_cert(f.read())
                        if v.get("valid"):
                            status["services"].append({
                                "service_id": sid,
                                "subject_cn": v.get("subject_cn"),
                                "scopes": v.get("scopes", []),
                                "expires_at": v.get("expires_at")
                            })

        if os.path.exists(self.plugins_cert_dir):
            for pid in os.listdir(self.plugins_cert_dir):
                plugin_crt = os.path.join(self.plugins_cert_dir, pid, "client.crt")
                if os.path.exists(plugin_crt):
                    with open(plugin_crt, "r") as f:
                        v = self.verify_client_cert(f.read())
                        if v.get("valid"):
                            status["plugins"].append({
                                "plugin_id": pid,
                                "subject_cn": v.get("subject_cn"),
                                "scopes": v.get("scopes", []),
                                "expires_at": v.get("expires_at")
                            })

        return status
