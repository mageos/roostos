from fastapi import APIRouter, Depends, Body, HTTPException
from pydantic import BaseModel
from typing import Optional

from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_user, get_current_parent, get_current_admin, UserSession
from roostos_web.services import SystemService
from roostos_web.di import Injected

router = APIRouter(tags=["schedules"])

# ==========================================
# Firewall Input Rules
# ==========================================

class FirewallRuleSchema(BaseModel):
    name: str
    interface: str = "*"
    protocol: str = "tcp"
    port: int
    source: Optional[str] = None
    action: str = "accept"
    enabled: bool = True

@router.get("/api/firewall/rules")
async def get_firewall_rules(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Returns list of configured firewall input rules."""
    config = repo.get_config()
    return [r.model_dump() for r in config.firewall.rules]

@router.post("/api/firewall/rules")
async def update_firewall_rule(
    rule: FirewallRuleSchema,
    current_user: UserSession = Depends(get_current_admin),
    dbus: RoostClient = Injected(RoostClient)
):
    """Creates or updates a firewall input rule by name."""
    success = await dbus.update_firewall_rule(
        name=rule.name,
        interface=rule.interface,
        protocol=rule.protocol,
        port=rule.port,
        source=rule.source or "",
        action=rule.action,
        enabled=rule.enabled
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to save firewall rule.")
    return {"status": "success", "message": f"Firewall rule '{rule.name}' saved."}

@router.delete("/api/firewall/rules/{name}")
async def delete_firewall_rule(
    name: str,
    current_user: UserSession = Depends(get_current_admin),
    dbus: RoostClient = Injected(RoostClient)
):
    """Deletes a firewall input rule by name."""
    success = await dbus.delete_firewall_rule(name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete firewall rule.")
    return {"status": "success", "message": f"Firewall rule '{name}' deleted."}

# ==========================================
# Schedules & Bypasses
# ==========================================


@router.get("/api/schedules")
async def get_schedules(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Returns configured schedules and firewall port forwards."""
    config = repo.get_config()
    return config.firewall.model_dump(exclude_none=True)

@router.post("/api/schedules/bypass")
async def grant_bypass(
    mac: str = Body(...),
    duration_minutes: int = Body(...),
    current_user: UserSession = Depends(get_current_parent),
    dbus: RoostClient = Injected(RoostClient)
):
    """Grants a temporary schedule bypass extension to a device MAC."""
    success = await dbus.grant_time_extension(mac, duration_minutes * 60)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to grant bypass.")
    return {"status": "success"}

@router.delete("/api/schedules/bypass/{mac}")
async def revoke_bypass(
    mac: str,
    current_user: UserSession = Depends(get_current_parent),
    dbus: RoostClient = Injected(RoostClient)
):
    """Revokes any active schedule bypass extension from a device MAC."""
    success = await dbus.remove_time_extension(mac)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to revoke bypass.")
    return {"status": "success"}

@router.post("/api/backups")
async def create_backup(
    passphrase: str = Body(..., embed=True),
    current_user: UserSession = Depends(get_current_admin),
    dbus: RoostClient = Injected(RoostClient)
):
    """Triggers configuration backup creation and returns output archive path."""
    backup_path = await dbus.create_backup(passphrase)
    return {"status": "success", "backup_path": backup_path}

@router.post("/api/backups/restore")
async def restore_backup(
    backup_path: str = Body(...),
    passphrase: str = Body(...),
    current_user: UserSession = Depends(get_current_admin),
    dbus: RoostClient = Injected(RoostClient)
):
    """Decrypts and restores configurations from backup package."""
    success = await dbus.restore_backup(backup_path, passphrase)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to restore backup. Verify manifest and password.")
    return {"status": "success", "message": "Backup restored successfully."}

@router.get("/api/firewall/blocks")
async def get_firewall_blocks(
    limit: int = 50,
    current_user: UserSession = Depends(get_current_parent),
    system_service: SystemService = Injected(SystemService)
):
    """Returns recently blocked/dropped firewall packets parsing journalctl."""
    return await system_service.get_firewall_blocks(limit)

