"""
RoostOS Certificate & ACME Data Transfer Objects (DTOs).
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ChallengeType(str, Enum):
    DNS_01 = "dns-01"
    HTTP_01 = "http-01"
    INTERNAL_CA = "internal-ca"


class DNSProviderType(str, Enum):
    CLOUDFLARE = "cloudflare"
    DUCKDNS = "duckdns"
    ROUTE53 = "route53"
    RFC2136 = "rfc2136"
    MANUAL = "manual"


class CertificateStatus(str, Enum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    PENDING = "pending"
    ERROR = "error"


class ACMESettings(BaseModel):
    email: str = ""
    staging: bool = False
    default_challenge: ChallengeType = ChallengeType.DNS_01
    dns_providers: Dict[str, Dict[str, str]] = Field(default_factory=dict)


class DomainCertificate(BaseModel):
    domain: str
    sans: List[str] = Field(default_factory=list)
    issuer: str = "Let's Encrypt"
    status: CertificateStatus = CertificateStatus.VALID
    challenge_type: ChallengeType = ChallengeType.DNS_01
    dns_provider: Optional[DNSProviderType] = None
    created_at: str = ""
    expires_at: str = ""
    auto_renew: bool = True
    cert_path: str = ""
    key_path: str = ""
    error_message: Optional[str] = None


class OrderCertificateRequest(BaseModel):
    domain: str
    sans: List[str] = Field(default_factory=list)
    challenge_type: ChallengeType = ChallengeType.DNS_01
    dns_provider: Optional[DNSProviderType] = None
    dns_credentials: Dict[str, str] = Field(default_factory=dict)
    email: Optional[str] = None
    staging: bool = False
    auto_renew: bool = True


class CertificateRenewResponse(BaseModel):
    status: str
    domain: str
    message: str
    expires_at: Optional[str] = None
