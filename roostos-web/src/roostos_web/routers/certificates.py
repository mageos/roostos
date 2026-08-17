"""FastAPI Router for Certificate Management & ACME Status."""

import os
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from roostos_engine.cert_manager import CertificateManager
from roostos_web.auth import get_current_user, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/v1/system/certificates", tags=["Certificates"])

class IssueCertRequest(BaseModel):
    entity_type: str  # "service" or "plugin"
    entity_id: str
    scopes: List[str] = []

class VerifyCertRequest(BaseModel):
    cert_pem: str

@router.get("", response_model=Dict[str, Any])
async def get_certificates_status(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user)
) -> Dict[str, Any]:
    """Returns status of Root CA, Web Console HTTPS TLS certificate, service certs, and sidecar plugin mTLS certificates."""
    try:
        return cert_mgr.get_cert_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch certificate status: {e}"
        )

@router.post("/renew", response_model=Dict[str, Any])
async def renew_server_certificate(
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user)
) -> Dict[str, Any]:
    """Triggers server HTTPS TLS certificate renewal."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for certificate renewal."
        )
    try:
        res = cert_mgr.issue_server_cert()
        return {"status": "success", "message": "Server TLS certificate renewed successfully.", "expires_in_days": 365}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Certificate renewal failed: {e}"
        )

@router.post("/issue", response_model=Dict[str, str])
async def issue_certificate(
    payload: IssueCertRequest,
    cert_mgr: CertificateManager = Injected(CertificateManager),
    current_user: UserSession = Depends(get_current_user)
) -> Dict[str, str]:
    """Issues an X.509 client certificate for a system service or plugin (Admin restricted)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to issue certificates."
        )
    try:
        if payload.entity_type == "service":
            return cert_mgr.issue_service_cert(payload.entity_id, payload.scopes)
        elif payload.entity_type == "plugin":
            return cert_mgr.issue_plugin_cert(payload.entity_id, payload.scopes)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported entity_type: '{payload.entity_type}'. Must be 'service' or 'plugin'."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Certificate issuance failed: {e}"
        )

@router.post("/verify", response_model=Dict[str, Any])
async def verify_certificate(
    payload: VerifyCertRequest,
    cert_mgr: CertificateManager = Injected(CertificateManager)
) -> Dict[str, Any]:
    """Verifies a client certificate against Root CA and returns parsed claims/scopes."""
    try:
        return cert_mgr.verify_client_cert(payload.cert_pem)
    except Exception as e:
        return {"valid": False, "error": str(e)}
