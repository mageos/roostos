from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from pydantic import BaseModel

from roostos_engine.pkg_manager import (
    detect_package_manager,
    check_all_dependencies,
    get_feature_dependencies,
)
from roostos_engine.config import SystemConfig, UserConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_user, get_current_parent, get_current_admin, UserSession
from roostos_web.services import SystemService, AuthService
from roostos_web.di import Injected
from roostos_web.audit import log_config_change, log_system_action

router = APIRouter(tags=["system"])

class UserManagementSchema(BaseModel):
    username: str
    role: str
    person: Optional[str] = None

@router.get("/api/system")
async def get_system_config(
    current_user: UserSession = Depends(get_current_parent),
    system_service: SystemService = Injected(SystemService)
):
    """Returns the system configuration settings namespace along with real-time stats."""
    return await system_service.get_system_config()

class SystemUpdatePayload(BaseModel):
    hostname: str
    domain: str
    timezone: str
    docker_registry: Optional[str] = ""


@router.post("/api/system")
async def update_system_config(
    request: Request,
    payload: SystemUpdatePayload,
    current_user: UserSession = Depends(get_current_admin),
    system_service: SystemService = Injected(SystemService)
):
    """Updates global system properties (hostname, domain name, timezone) and pushes changes to host."""
    await system_service.update_system_config(payload.hostname, payload.domain, payload.timezone, payload.docker_registry)
    log_config_change(
        username=current_user.username,
        section="system",
        action="update_system_properties",
        request=request,
        details=f"hostname={payload.hostname}, domain={payload.domain}, timezone={payload.timezone}"
    )
    return {"status": "success", "message": "System configurations updated successfully."}

@router.get("/api/system/health")
async def get_system_health(
    current_user: UserSession = Depends(get_current_user),
    system_service: SystemService = Injected(SystemService)
):
    """Runs a series of system diagnostics checks to verify router network/firewall integrity."""
    return await system_service.run_diagnostics()

@router.post("/api/system/reboot")
async def reboot_router(
    request: Request,
    current_user: UserSession = Depends(get_current_admin),
    system_service: SystemService = Injected(SystemService)
):
    """Initiates a graceful reboot of the underlying hardware/hypervisor VM."""
    log_system_action(
        username=current_user.username,
        action="reboot_router",
        request=request
    )
    await system_service.reboot_router()
    return {"status": "success", "message": "Reboot instruction triggered successfully."}

@router.get("/api/users")
async def get_users_list(
    current_user: UserSession = Depends(get_current_parent),
    auth_service: AuthService = Injected(AuthService)
):
    """Returns list of Web login users."""
    users = auth_service.get_users()
    return {"users": [{"username": u.username, "role": u.role, "person": u.person} for u in users]}

@router.post("/api/users")
async def save_user(
    request: Request,
    user_data: UserManagementSchema,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
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
    
    action_name = "update_user" if user_idx is not None else "create_user"
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
    log_config_change(
        username=current_user.username,
        section="users",
        action=action_name,
        request=request,
        details=f"target_user={user_data.username}, role={user_data.role}"
    )
    return {"status": "success", "message": f"User {user_data.username} saved successfully."}

@router.delete("/api/users/{username}")
async def delete_user(
    request: Request,
    username: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
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
    log_config_change(
        username=current_user.username,
        section="users",
        action="delete_user",
        request=request,
        details=f"deleted_user={username}"
    )
    return {"status": "success", "message": f"User {username} deleted successfully."}

@router.get("/api/system/services")
async def get_system_services(
    current_user: UserSession = Depends(get_current_parent),
    system_service: SystemService = Injected(SystemService)
):
    """Returns active state and substate for core system services."""
    return await system_service.get_services_status()


class InstallDependenciesPayload(BaseModel):
    feature: Optional[str] = None
    packages: Optional[List[str]] = None


@router.get("/api/system/dependencies")
async def get_system_dependencies(
    current_user: UserSession = Depends(get_current_parent),
):
    """Returns OS package dependency status for all RoostOS subsystem features."""
    return check_all_dependencies().model_dump()


@router.post("/api/system/dependencies/install")
async def install_system_dependencies(
    request: Request,
    payload: InstallDependenciesPayload,
    current_user: UserSession = Depends(get_current_admin),
):
    """Installs missing OS packages for a specific feature or explicit package list."""
    mgr = detect_package_manager()
    pkgs = list(payload.packages or [])
    if payload.feature:
        pkgs.extend(get_feature_dependencies(payload.feature))
    pkgs = list(dict.fromkeys(pkgs))

    if not pkgs:
        raise HTTPException(status_code=400, detail="No packages specified for installation.")

    result = mgr.install_packages(pkgs)
    log_system_action(
        username=current_user.username,
        action="install_dependencies",
        request=request,
        details=f"packages={pkgs}, success={result.success}",
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    return result.model_dump()


