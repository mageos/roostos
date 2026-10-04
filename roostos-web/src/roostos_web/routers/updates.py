"""FastAPI router for checking, scheduling, and installing system updates."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException

from roostos_engine.models.system import SystemUpdatesConfig
from roostos_engine.update_manager import UpdateManager, UpdateCheckResult, UpdateInstallResult
from roostos_web.auth import get_current_admin
from roostos_web.services.base import get_repository
from roostos_web.services.events import event_publisher

router = APIRouter(prefix="/api/v1/system/updates", tags=["updates"])

_update_manager_instance: Optional[UpdateManager] = None


def get_update_manager() -> UpdateManager:
    """Provides a singleton UpdateManager instance wired to the configuration repository."""
    global _update_manager_instance
    if _update_manager_instance is None:
        try:
            repo = get_repository()
            sys_cfg = repo.get_config().system
            _update_manager_instance = UpdateManager(config=sys_cfg.updates, config_dir=repo.config_dir)
        except Exception:
            _update_manager_instance = UpdateManager()
    return _update_manager_instance


def set_update_manager(manager: UpdateManager) -> None:
    """Overrides the UpdateManager instance for testing."""
    global _update_manager_instance
    _update_manager_instance = manager


@router.get("/status", response_model=UpdateCheckResult)
def get_updates_status(
    mgr: UpdateManager = Depends(get_update_manager),
    _=Depends(get_current_admin),
) -> UpdateCheckResult:
    """Returns the current update availability status without forcing a full repo refresh."""
    return mgr.check_updates(refresh_cache=False)


@router.post("/check", response_model=UpdateCheckResult)
def check_updates(
    mgr: UpdateManager = Depends(get_update_manager),
    _=Depends(get_current_admin),
) -> UpdateCheckResult:
    """Forces a refresh of native package repositories and checks for available updates."""
    result = mgr.check_updates(refresh_cache=True)
    event_publisher.publish("system_updates_checked", result.model_dump())
    return result


@router.post("/install", response_model=UpdateInstallResult)
def install_updates(
    security_only: bool = False,
    mgr: UpdateManager = Depends(get_update_manager),
    _=Depends(get_current_admin),
) -> UpdateInstallResult:
    """Creates a configuration backup and applies available updates."""
    result = mgr.install_updates(security_only=security_only)
    event_publisher.publish("system_updates_installed", result.model_dump())
    return result


@router.get("/config", response_model=SystemUpdatesConfig)
def get_updates_config(
    mgr: UpdateManager = Depends(get_update_manager),
    _=Depends(get_current_admin),
) -> SystemUpdatesConfig:
    """Returns the current unattended update and reboot window configuration."""
    return mgr.config


@router.put("/config", response_model=SystemUpdatesConfig)
def update_updates_config(
    config_update: SystemUpdatesConfig,
    mgr: UpdateManager = Depends(get_update_manager),
    _=Depends(get_current_admin),
) -> SystemUpdatesConfig:
    """Updates the unattended update schedule and reboot window in system.yaml."""
    repo = get_repository()
    cfg = repo.get_config()
    cfg.system.updates = config_update
    repo.save_config("system", cfg.system)
    mgr.config = config_update
    return mgr.config
