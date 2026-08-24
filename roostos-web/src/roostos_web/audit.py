"""Structured Journald / Syslog Audit Logging for RoostOS Web."""

import logging
from typing import Optional, List
from fastapi import Request

# Dedicated logger for security and administrative audit events
audit_logger = logging.getLogger("roostos.audit")


def extract_client_ip(request: Optional[Request] = None) -> str:
    """Extracts client IP address respecting reverse proxy headers."""
    if request is None:
        return "internal"

    try:
        if hasattr(request, "headers") and request.headers:
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for and isinstance(forwarded_for, str):
                return forwarded_for.split(",")[0].strip()

            real_ip = request.headers.get("x-real-ip")
            if real_ip and isinstance(real_ip, str):
                return real_ip.strip()

        if hasattr(request, "client") and request.client and getattr(request.client, "host", None):
            return str(request.client.host)
    except Exception:
        pass

    return "unknown"


def log_auth_success(
    username: str,
    authority: str,
    role: str,
    request: Optional[Request] = None,
    method: str = "password"
) -> None:
    """Emits an audit record for successful user authentication."""
    ip = extract_client_ip(request)
    audit_logger.info(
        f'[AUDIT:AUTH_SUCCESS] user="{username}" authority="{authority}" role="{role}" method="{method}" ip="{ip}"'
    )


def log_auth_failure(
    username: str,
    authority: str,
    reason: str,
    request: Optional[Request] = None,
    method: str = "password"
) -> None:
    """Emits an audit record for failed user authentication."""
    ip = extract_client_ip(request)
    audit_logger.warning(
        f'[AUDIT:AUTH_FAILED] user="{username}" authority="{authority}" reason="{reason}" method="{method}" ip="{ip}"'
    )


def log_cert_auth(
    service_id: str,
    subject_cn: str,
    scopes: List[str],
    request: Optional[Request] = None
) -> None:
    """Emits an audit record for successful X.509 client certificate authentication."""
    ip = extract_client_ip(request)
    scopes_str = ",".join(scopes)
    audit_logger.info(
        f'[AUDIT:AUTH_CERT] service="{service_id}" subject="{subject_cn}" scopes="{scopes_str}" ip="{ip}"'
    )


def log_config_change(
    username: str,
    section: str,
    action: str,
    request: Optional[Request] = None,
    details: Optional[str] = None
) -> None:
    """Emits an audit record for configuration changes."""
    ip = extract_client_ip(request)
    details_str = f' details="{details}"' if details else ""
    audit_logger.info(
        f'[AUDIT:CONFIG_CHANGE] user="{username}" section="{section}" action="{action}" ip="{ip}"{details_str}'
    )


def log_system_action(
    username: str,
    action: str,
    request: Optional[Request] = None,
    details: Optional[str] = None
) -> None:
    """Emits an audit record for sensitive system actions (e.g. backup, restore, reboot)."""
    ip = extract_client_ip(request)
    details_str = f' details="{details}"' if details else ""
    audit_logger.info(
        f'[AUDIT:SYSTEM_ACTION] user="{username}" action="{action}" ip="{ip}"{details_str}'
    )
