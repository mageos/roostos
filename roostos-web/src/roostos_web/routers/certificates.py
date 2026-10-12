"""FastAPI Router for Certificate Management & Automated ACME Let's Encrypt Issuance."""

import os
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from roostos_engine.acme_service import HTTP_CHALLENGES
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.models.certificates import (
    ACMESettings,
    CertificateRenewResponse,
    DomainCertificate,
    OrderCertificateRequest,
)
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/v1/system/certificates", tags=["Certificates"])
acme_challenge_router = APIRouter(tags=["ACME"])


@acme_challenge_router.get("/.well-known/acme-challenge/{token}", response_class=PlainTextResponse)
async def get_acme_http_challenge(token: str) -> str:
    """Public ACME HTTP-01 challenge responder for Let's Encrypt validation."""
    if token in HTTP_CHALLENGES:
        return HTTP_CHALLENGES[token]
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ACME challenge token not found.")


class IssueCertRequest(BaseModel):
    entity_type: str  # "service" or "plugin"
    entity_id: str
    scopes: List[str] = []


class VerifyCertRequest(BaseModel):
    cert_pem: str


@router.get("", response_model=Dict[str, Any])
async def get_certificates_status(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns status of Root CA, Web Console HTTPS TLS certificate, service certs, and managed domain certs."""
    try:
        return cert_mgr.get_cert_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch certificate status: {e}",
        )


@router.get("/ca.crt")
async def download_root_ca(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user),
) -> Response:
    """Downloads the RoostOS Root CA certificate for installing on LAN devices."""
    try:
        pem_data = cert_mgr.get_root_ca_pem()
        return Response(
            content=pem_data,
            media_type="application/x-x509-ca-cert",
            headers={"Content-Disposition": 'attachment; filename="roostos-root-ca.crt"'},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export Root CA: {e}",
        )


@router.get("/acme/settings", response_model=Dict[str, Any])
async def get_acme_settings(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetches ACME configuration (email, staging, DNS provider credentials)."""
    return cert_mgr.acme.get_settings()


@router.put("/acme/settings", response_model=Dict[str, str])
async def update_acme_settings(
    payload: ACMESettings,
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, str]:
    """Updates ACME configuration settings."""
    try:
        cert_mgr.acme.save_settings(payload.model_dump())
        return {"status": "success", "message": "ACME settings saved successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save ACME settings: {e}",
        )


@router.get("/domains", response_model=List[DomainCertificate])
async def list_domain_certificates(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user),
) -> List[DomainCertificate]:
    """Lists all automated domain certificates managed by RoostOS."""
    return cert_mgr.acme.list_certificates()


@router.post("/domains", response_model=DomainCertificate)
async def request_domain_certificate(
    payload: OrderCertificateRequest,
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_admin),
) -> DomainCertificate:
    """Orders a new SSL certificate via Let's Encrypt (DNS-01 or HTTP-01)."""
    try:
        settings = cert_mgr.acme.get_settings()
        creds = payload.dns_credentials or {}
        if not creds and payload.dns_provider:
            prov_key = str(payload.dns_provider.value if hasattr(payload.dns_provider, "value") else payload.dns_provider)
            creds = settings.get("dns_providers", {}).get(prov_key, {})

        return cert_mgr.acme.request_certificate(
            domain=payload.domain,
            sans=payload.sans,
            challenge_type=payload.challenge_type,
            dns_provider_type=payload.dns_provider,
            dns_credentials=creds,
            auto_renew=payload.auto_renew,
            staging=payload.staging or settings.get("staging", False),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Certificate request failed: {e}",
        )


@router.post("/domains/{domain}/renew", response_model=CertificateRenewResponse)
async def renew_domain_certificate(
    domain: str,
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_admin),
) -> CertificateRenewResponse:
    """Forces renewal of a managed domain certificate."""
    certs = cert_mgr.acme.list_certificates()
    target = next((c for c in certs if c.domain == domain.strip().lower()), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No certificate found for domain '{domain}'.",
        )

    try:
        settings = cert_mgr.acme.get_settings()
        prov_key = str(target.dns_provider.value if hasattr(target.dns_provider, "value") else target.dns_provider)
        creds = settings.get("dns_providers", {}).get(prov_key, {})

        renewed = cert_mgr.acme.request_certificate(
            domain=target.domain,
            sans=target.sans,
            challenge_type=target.challenge_type,
            dns_provider_type=target.dns_provider,
            dns_credentials=creds,
            auto_renew=target.auto_renew,
            staging=settings.get("staging", False),
        )
        return CertificateRenewResponse(
            status="success",
            domain=domain,
            message=f"Certificate for '{domain}' renewed successfully.",
            expires_at=renewed.expires_at,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Renewal failed for '{domain}': {e}",
        )


@router.delete("/domains/{domain}", response_model=Dict[str, str])
async def delete_domain_certificate(
    domain: str,
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, str]:
    """Deletes a managed domain certificate bundle."""
    deleted = cert_mgr.acme.delete_certificate(domain)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate for '{domain}' not found.",
        )
    return {"status": "success", "message": f"Certificate for '{domain}' deleted."}


@router.post("/renew", response_model=Dict[str, Any])
async def renew_server_certificate(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Triggers server HTTPS TLS certificate renewal."""
    try:
        cert_mgr.issue_server_cert()
        return {"status": "success", "message": "Server TLS certificate renewed successfully.", "expires_in_days": 365}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Certificate renewal failed: {e}",
        )


@router.post("/issue", response_model=Dict[str, str])
async def issue_certificate(
    payload: IssueCertRequest,
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, str]:
    """Issues an X.509 client certificate for a system service or plugin."""
    try:
        if payload.entity_type == "service":
            return cert_mgr.issue_service_cert(payload.entity_id, payload.scopes)
        elif payload.entity_type == "plugin":
            return cert_mgr.issue_plugin_cert(payload.entity_id, payload.scopes)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported entity_type: '{payload.entity_type}'. Must be 'service' or 'plugin'.",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Certificate issuance failed: {e}",
        )


@router.post("/verify", response_model=Dict[str, Any])
async def verify_certificate(
    payload: VerifyCertRequest,
    cert_mgr: CertificateManager = Injected(CertificateManager),
) -> Dict[str, Any]:
    """Verifies a client certificate against Root CA and returns parsed claims/scopes."""
    try:
        return cert_mgr.verify_client_cert(payload.cert_pem)
    except Exception as e:
        return {"valid": False, "error": str(e)}
