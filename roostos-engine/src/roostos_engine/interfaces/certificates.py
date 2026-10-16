"""Certificate Provider Protocol."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class CertificateProvider(Protocol):
    """Protocol for certificate management backends (standard X.509/ACME, mock, vault)."""

    def ensure_root_ca(self) -> Any:
        """Ensures the local Root CA exists."""
        ...

    def issue_server_cert(self, hostname: str = "roost-router", domain: str = "lan") -> Dict[str, str]:
        """Issues an HTTPS TLS server certificate."""
        ...

    def verify_client_cert(self, cert_pem: str) -> Dict[str, Any]:
        """Validates a client mTLS certificate."""
        ...

    def get_root_ca_pem(self) -> str:
        """Returns the Root CA certificate in PEM format."""
        ...

    def get_cert_status(self) -> Dict[str, Any]:
        """Returns summary status of active certificates."""
        ...
