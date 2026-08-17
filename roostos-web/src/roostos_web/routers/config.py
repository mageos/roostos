import os
import yaml
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, status
from pydantic import BaseModel

from roostos_engine.repository import ConfigRepository, StagingConfigRepository
from roostos_engine.git_engine import GitEngine
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_parent, get_current_admin, UserSession
from roostos_web.di import Injected

router = APIRouter(tags=["config"])

class CommitRequest(BaseModel):
    description: str

class RollbackRequest(BaseModel):
    commit: str

@router.get("/api/config/staged")
async def get_staged_status(
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Checks if there are any staged/dirty configurations pending commit."""
    if isinstance(repo, StagingConfigRepository):
        has_changes = repo.has_staged_changes()
        staged_files = []
        if has_changes and os.path.exists(repo.staged_dir):
            staged_files = [f for f in os.listdir(repo.staged_dir) if f.endswith(".yaml")]
        return {
            "has_staged_changes": has_changes,
            "staged_files": staged_files
        }
    return {
        "has_staged_changes": False,
        "staged_files": []
    }

@router.post("/api/config/commit")
async def commit_changes(
    request: CommitRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Commits staged configurations, initiates git tracking commit, and triggers daemon apply."""
    if not isinstance(repo, StagingConfigRepository):
        raise HTTPException(status_code=400, detail="Staging repository not active.")

    if not repo.has_staged_changes():
        raise HTTPException(status_code=400, detail="No staged changes to commit.")

    # 1. Apply staged configurations by moving files to the active directory
    repo.commit_staged_changes()

    # 2. Run Git commit on active directory
    git_engine = GitEngine(repo.active_repo.config_dir)
    git_success = git_engine.commit_changes(request.description)

    # 3. Request D-Bus config updates to reload core engine daemon settings
    await dbus.get_config()

    return {
        "status": "success",
        "message": "Configurations committed and applied successfully.",
        "git_commit": git_success
    }

@router.post("/api/config/discard")
async def discard_staged_changes(
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Discard all currently staged configurations."""
    if not isinstance(repo, StagingConfigRepository):
        raise HTTPException(status_code=400, detail="Staging repository not active.")

    repo.discard_staged_changes()
    return {"status": "success", "message": "Staged changes discarded."}

@router.get("/api/config/history")
async def get_config_history(
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Returns the list of configuration revisions (git commit log)."""
    active_dir = repo.active_repo.config_dir if isinstance(repo, StagingConfigRepository) else repo.config_dir
    git_engine = GitEngine(active_dir)
    history = git_engine.get_commit_history()
    return {"history": history}

@router.post("/api/config/rollback")
async def rollback_config(
    request: RollbackRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Restores configurations to a historical git commit reference."""
    active_dir = repo.active_repo.config_dir if isinstance(repo, StagingConfigRepository) else repo.config_dir
    git_engine = GitEngine(active_dir)
    
    # Perform git checkout and new commit
    success = git_engine.rollback_to_commit(request.commit)
    if not success:
        raise HTTPException(status_code=500, detail="Rollback failed.")

    # Refresh core systems configurations
    await dbus.get_config()
    
    return {"status": "success", "message": f"Successfully rolled back configuration to {request.commit[:8]}."}
