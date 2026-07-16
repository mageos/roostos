from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from roostos_engine.config import SystemConfig, UserConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_user, get_current_parent, get_current_admin, UserSession
from roostos_web.services import SystemService, AuthService, get_repository, get_dbus_client

router = APIRouter(tags=["system"])

class UserManagementSchema(BaseModel):
    username: str
    role: str
    person: Optional[str] = None

@router.get("/api/system")
async def get_system_config(
    current_user: UserSession = Depends(get_current_parent),
    system_service: SystemService = Depends()
):
    """Returns the system configuration settings namespace along with real-time stats."""
    return await system_service.get_system_config()

@router.post("/api/system")
async def update_system_config(
    current_user: UserSession = Depends(get_current_admin),
    hostname: str = Body(...),
    domain: str = Body(...),
    timezone: str = Body(...),
    docker_registry: Optional[str] = Body(""),
    system_service: SystemService = Depends()
):
    """Updates global system properties (hostname, domain name, timezone) and pushes changes to host."""
    await system_service.update_system_config(hostname, domain, timezone, docker_registry)
    return {"status": "success", "message": "System configurations updated successfully."}

@router.get("/api/system/health")
async def get_system_health(
    current_user: UserSession = Depends(get_current_user),
    system_service: SystemService = Depends()
):
    """Runs a series of system diagnostics checks to verify router network/firewall integrity."""
    return await system_service.run_diagnostics()

@router.post("/api/system/reboot")
async def reboot_router(
    current_user: UserSession = Depends(get_current_admin),
    system_service: SystemService = Depends()
):
    """Initiates a graceful reboot of the underlying hardware/hypervisor VM."""
    await system_service.reboot_router()
    return {"status": "success", "message": "Reboot instruction triggered successfully."}

@router.get("/api/users")
async def get_users_list(
    current_user: UserSession = Depends(get_current_parent),
    auth_service: AuthService = Depends()
):
    """Returns list of Web login users."""
    users = auth_service.get_users()
    return {"users": [{"username": u.username, "role": u.role, "person": u.person} for u in users]}

@router.post("/api/users")
async def save_user(
    user_data: UserManagementSchema,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Depends(get_repository),
    dbus: RoostClient = Depends(get_dbus_client)
):
    """Creates or updates a user operator profile in system.yaml."""
    if user_data.role not in ("admin", "parent", "member"):
        raise HTTPException(status_code=400, detail="Invalid user role. Role must be 'admin', 'parent', or 'member'.")
    
    config = repo.get_config()
    if user_data.person:
        people_ids = {p.id for p in config.people}
        if user_data.person not in people_ids:
            raise HTTPException(status_code=400, detail=f"Linked person profile '{user_data.person}' does not exist.")

    existing_users = [u.model_dump() for u in config.users]
    user_idx = next((i for i, u in enumerate(existing_users) if u["username"] == user_data.username), None)
    
    ssh_keys = []
    if user_idx is not None:
        ssh_keys = existing_users[user_idx].get("ssh_keys", [])
        
    new_user_dict = {
        "username": user_data.username,
        "role": user_data.role,
        "person": user_data.person if user_data.person else None,
        "ssh_keys": ssh_keys
    }
    
    if user_idx is not None:
        existing_users[user_idx] = new_user_dict
    else:
        existing_users.append(new_user_dict)
        
    system_config_obj = SystemConfig(
        system=config.system,
        users=existing_users
    )
    repo.save_system_config(system_config_obj)
    await dbus.get_config()
    return {"status": "success", "message": f"User {user_data.username} saved successfully."}

@router.delete("/api/users/{username}")
async def delete_user(
    username: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Depends(get_repository),
    dbus: RoostClient = Depends(get_dbus_client)
):
    """Deletes a user account from system.yaml."""
    config = repo.get_config()
    if current_user.username == username:
        raise HTTPException(status_code=400, detail="Self-deletion of currently logged-in administrator is not allowed.")
        
    admins = [u for u in config.users if u.role == "admin" and u.username != username]
    if not admins:
        raise HTTPException(status_code=400, detail="Cannot delete the last remaining administrator account.")
        
    existing_users = [u.model_dump() for u in config.users if u.username != username]
    
    system_config_obj = SystemConfig(
        system=config.system,
        users=existing_users
    )
    repo.save_system_config(system_config_obj)
    await dbus.get_config()
    return {"status": "success", "message": f"User {username} deleted successfully."}

@router.get("/api/system/services")
async def get_system_services(
    current_user: UserSession = Depends(get_current_parent),
    system_service: SystemService = Depends()
):
    """Returns active state and substate for core system services."""
    return await system_service.get_services_status()

