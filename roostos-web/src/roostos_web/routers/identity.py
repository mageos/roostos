"""FastAPI Router for Central Identity & Active Directory Management."""

from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import PlainTextResponse

from roostos_engine.models.identity import (
    DomainUser,
    DomainUserCreate,
    DomainUserUpdate,
    DomainPasswordReset,
    DomainStatus,
    WorkstationEnrollmentInfo,
)
from roostos_engine.repository import ConfigRepository
from roostos_engine.identity_manager import IdentityManager
from roostos_web.di import Injected
from roostos_web.auth import get_current_admin, UserSession


router = APIRouter(prefix="/api/v1/identity", tags=["identity"])

# Shared IdentityManager singleton for web worker
_identity_mgr: IdentityManager | None = None


def get_identity_manager(repo: ConfigRepository = Injected(ConfigRepository)) -> IdentityManager:
    """Provides or initializes the IdentityManager instance."""
    global _identity_mgr
    if _identity_mgr is None:
        config = repo.get_config()
        realm = getattr(config.system, "realm", "ROOSTOS.LOCAL")
        workgroup = "ROOSTOS"
        if config.system.identity_server and config.system.identity_server.workgroup:
            workgroup = config.system.identity_server.workgroup
        _identity_mgr = IdentityManager(repo=repo, realm=realm, workgroup=workgroup)
    return _identity_mgr


@router.get("/status", response_model=DomainStatus)
async def get_domain_status(
    mgr: IdentityManager = Depends(get_identity_manager)
) -> DomainStatus:
    """Returns the operational status of the central domain directory."""
    return mgr.get_status()


@router.get("/users", response_model=List[DomainUser])
async def list_domain_users(
    mgr: IdentityManager = Depends(get_identity_manager)
) -> List[DomainUser]:
    """Lists all centralized domain accounts."""
    return mgr.list_users()


@router.post("/users", response_model=DomainUser, status_code=201)
async def create_domain_user(
    payload: DomainUserCreate,
    mgr: IdentityManager = Depends(get_identity_manager)
) -> DomainUser:
    """Provisions a new domain user account."""
    try:
        return mgr.create_user(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{username}", response_model=DomainUser)
async def update_domain_user(
    username: str,
    payload: DomainUserUpdate,
    mgr: IdentityManager = Depends(get_identity_manager)
) -> DomainUser:
    """Updates an existing domain user account."""
    try:
        return mgr.update_user(username, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/users/{username}")
async def delete_domain_user(
    username: str,
    mgr: IdentityManager = Depends(get_identity_manager)
) -> dict:
    """Deletes a domain account from the directory."""
    try:
        success = mgr.delete_user(username)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "success", "deleted": username}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{username}/password")
async def reset_domain_user_password(
    username: str,
    payload: DomainPasswordReset,
    mgr: IdentityManager = Depends(get_identity_manager)
) -> dict:
    """Resets the domain password for a user account."""
    try:
        mgr.reset_password(username, payload.new_password)
        return {"status": "success", "username": username}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/enrollment-info", response_model=WorkstationEnrollmentInfo)
async def get_enrollment_info(
    request: Request,
    mgr: IdentityManager = Depends(get_identity_manager)
) -> WorkstationEnrollmentInfo:
    """Returns workstation enrollment metadata and instructions."""
    host_ip = request.headers.get("host", "192.168.1.1").split(":")[0]
    return mgr.get_enrollment_info(router_ip=host_ip)


@router.get("/join.sh", response_class=PlainTextResponse)
async def get_join_script(
    request: Request,
    mgr: IdentityManager = Depends(get_identity_manager)
) -> str:
    """Serves the automated workstation enrollment bash script."""
    status = mgr.get_status()
    host_ip = request.headers.get("host", "192.168.1.1").split(":")[0]

    script = f"""#!/usr/bin/env bash
# RoostOS Workstation Automatic Enrollment Script
# Domain: {status.realm} | DC: {host_ip}
set -euo pipefail

REALM="{status.realm}"
WORKGROUP="{status.workgroup}"
DC_IP="{host_ip}"

echo "================================================="
echo "  RoostOS Centralized Identity Workstation Setup"
echo "  Joining Realm: $REALM"
echo "================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

# Detect Package Manager & Install SSSD + Realm Tools
if command -v apt-get >/dev/null 2>&1; then
    echo "[1/4] Installing SSSD & Active Directory packages (apt)..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq sssd-ad sssd-tools realmd adcli packagekit libpam-sss libnss-sss oddjob-mkhomedir
elif command -v pacman >/dev/null 2>&1; then
    echo "[1/4] Installing SSSD & Active Directory packages (pacman)..."
    pacman -Sy --noconfirm sssd adcli realmd krb5
elif command -v dnf >/dev/null 2>&1; then
    echo "[1/4] Installing SSSD & Active Directory packages (dnf)..."
    dnf install -y -q sssd realmd adcli oddjob-mkhomedir krb5-workstation
fi

echo "[2/4] Discovering Realm $REALM..."
realm discover "$REALM" || echo "Note: Realm discover finished."

echo "[3/4] Configuring PAM Automatic Home Directory Creation..."
if command -v pam-auth-update >/dev/null 2>&1; then
    pam-auth-update --enable mkhomedir
elif command -v authselect >/dev/null 2>&1; then
    authselect select sssd with-mkhomedir --force || true
fi

echo "[4/4] Joining $REALM with adcli / realm..."
echo "Please enter the Domain Administrator password (default: RoostOS!Admin2026):"
realm join --user=Administrator "$REALM" || true

systemctl restart sssd || true
echo "================================================="
echo "  Success! Workstation is now joined to $REALM."
echo "  Users can now log in with their domain credentials."
echo "================================================="
"""
    return script
