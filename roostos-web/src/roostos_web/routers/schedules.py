from fastapi import APIRouter, Depends, Body, HTTPException

from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_user, get_current_parent, get_current_admin, UserSession
from roostos_web.services import get_repository, get_dbus_client

router = APIRouter(tags=["schedules"])

@router.get("/api/schedules")
async def get_schedules(
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Depends(get_repository)
):
    """Returns configured schedules and firewall port forwards."""
    config = repo.get_config()
    return config.firewall.model_dump(exclude_none=True)

@router.post("/api/schedules/bypass")
async def grant_bypass(
    mac: str = Body(...),
    duration_minutes: int = Body(...),
    current_user: UserSession = Depends(get_current_parent),
    dbus: RoostClient = Depends(get_dbus_client)
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
    dbus: RoostClient = Depends(get_dbus_client)
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
    dbus: RoostClient = Depends(get_dbus_client)
):
    """Triggers configuration backup creation and returns output archive path."""
    backup_path = await dbus.create_backup(passphrase)
    return {"status": "success", "backup_path": backup_path}

@router.post("/api/backups/restore")
async def restore_backup(
    backup_path: str = Body(...),
    passphrase: str = Body(...),
    current_user: UserSession = Depends(get_current_admin),
    dbus: RoostClient = Depends(get_dbus_client)
):
    """Decrypts and restores configurations from backup package."""
    success = await dbus.restore_backup(backup_path, passphrase)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to restore backup. Verify manifest and password.")
    return {"status": "success", "message": "Backup restored successfully."}
