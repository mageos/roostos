"""FastAPI router for importing, updating, and building catalog apps from source."""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from roostos_engine.models.catalog import (
    PackageManifest,
    ImportFromSourceRequest,
    UpdateImportedAppRequest,
    InstallFromSourceRequest,
)
from roostos_engine.models.plugins import PluginsConfig
from roostos_engine.catalog_manager import CatalogManager
from roostos_engine.source_builder import SourceBuilder
from roostos_engine.ingress_helper import provision_ingress_route
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected

import_router = APIRouter(tags=["catalog-import"])

_catalog_mgr: Optional[CatalogManager] = None
_source_builder: Optional[SourceBuilder] = None


def get_catalog_manager(repo: ConfigRepository = Injected(ConfigRepository)) -> CatalogManager:
    """Dependency injector for CatalogManager."""
    global _catalog_mgr
    config_dir = getattr(repo, "config_dir", os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos"))
    if _catalog_mgr is None or _catalog_mgr.config_dir != config_dir:
        _catalog_mgr = CatalogManager(config_dir=config_dir)
    return _catalog_mgr


def get_source_builder(repo: ConfigRepository = Injected(ConfigRepository)) -> SourceBuilder:
    """Dependency injector for SourceBuilder."""
    global _source_builder
    sources_dir = os.environ.get("ROOSTOS_SOURCES_DIR")
    if not sources_dir:
        config_dir = getattr(repo, "config_dir", "/etc/roostos")
        sources_dir = os.path.join(config_dir, "sources")
    if _source_builder is None or _source_builder.sources_dir != sources_dir:
        _source_builder = SourceBuilder(sources_dir=sources_dir)
    return _source_builder


@import_router.post("/manifest/inspect", response_model=PackageManifest)
async def inspect_source_manifest(
    payload: Dict[str, str],
    builder: SourceBuilder = Depends(get_source_builder),
    current_user: UserSession = Depends(get_current_user),
) -> PackageManifest:
    """Clones or resolves a source directory and returns its parsed roost-app.yaml manifest."""
    source_url_or_path = payload.get("source_url_or_path", "").strip()
    git_ref = payload.get("git_ref", "main").strip()
    if not source_url_or_path:
        raise HTTPException(status_code=400, detail="Source URL or path is required.")
    try:
        repo_dir = builder.clone_or_resolve_source(source_url_or_path, git_ref)
        manifest = builder.load_manifest(repo_dir)
        if not manifest:
            raise HTTPException(status_code=404, detail=f"No roost-app.yaml manifest found at '{source_url_or_path}'.")
        return manifest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to inspect source: {e}")


@import_router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_source_app(
    req: ImportFromSourceRequest,
    builder: SourceBuilder = Depends(get_source_builder),
    mgr: CatalogManager = Depends(get_catalog_manager),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Clones repository, builds container in sandbox, and registers in the local catalog."""
    try:
        app_entry, build_logs = builder.import_to_catalog(req, mgr)
        return {
            "success": True,
            "message": f"Successfully imported and built {app_entry.name} into local catalog.",
            "app": app_entry,
            "build_logs": build_logs,
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import and build failed: {e}")


@import_router.get("/apps/{app_id}/check-update")
async def check_app_update(
    app_id: str,
    builder: SourceBuilder = Depends(get_source_builder),
    mgr: CatalogManager = Depends(get_catalog_manager),
    current_user: UserSession = Depends(get_current_user),
) -> Dict[str, Any]:
    """Checks if an imported application has updates available in its git repository."""
    local_index = mgr.get_local_catalog()
    app = next((a for a in local_index.applications if a.id == app_id), None)
    if not app:
        raise HTTPException(status_code=404, detail=f"Local application '{app_id}' not found.")
    has_update, latest_sha = builder.check_app_updates(app)
    return {
        "update_available": has_update,
        "current_commit": app.last_commit_built or "",
        "latest_commit": latest_sha or "",
    }


@import_router.post("/apps/{app_id}/update")
async def update_imported_app(
    app_id: str,
    req: UpdateImportedAppRequest,
    builder: SourceBuilder = Depends(get_source_builder),
    mgr: CatalogManager = Depends(get_catalog_manager),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Pulls latest changes, rebuilds container in sandbox, and updates the local catalog and plugin."""
    local_index = mgr.get_local_catalog()
    app = next((a for a in local_index.applications if a.id == app_id), None)
    if not app or not app.source_repo:
        raise HTTPException(status_code=404, detail=f"Imported application '{app_id}' not found.")

    import_req = ImportFromSourceRequest(
        source_url_or_path=app.source_repo,
        git_ref=app.source_ref,
        app_id_override=app.id,
        approve_network=req.approve_network,
        approved_endpoints=req.approved_endpoints,
    )
    try:
        updated_app, build_logs = builder.import_to_catalog(import_req, mgr)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Update failed: {e}")

    config = repo.get_config()
    existing_plugin = next((p for p in config.plugins if p.id == app_id), None)
    if existing_plugin and req.reinstall_if_running:
        for c in existing_plugin.containers:
            c.image = updated_app.container.image
        existing_plugin.settings = existing_plugin.settings or {}
        existing_plugin.settings["last_commit_built"] = updated_app.last_commit_built or ""
        existing_plugin.settings["version"] = updated_app.version
        try:
            repo.save_plugins_config(config.plugins)
        except Exception:
            pass

    return {
        "success": True,
        "message": f"Successfully updated {updated_app.name} to commit {updated_app.last_commit_built}.",
        "app": updated_app,
        "build_logs": build_logs,
    }


@import_router.delete("/apps/{app_id}/local", status_code=status.HTTP_204_NO_CONTENT)
async def delete_local_app(
    app_id: str,
    mgr: CatalogManager = Depends(get_catalog_manager),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_admin),
) -> None:
    """Removes an application from the local catalog if it is not currently installed."""
    config = repo.get_config()
    installed_ids = [p.id for p in config.plugins]
    if app_id in installed_ids:
        raise HTTPException(status_code=400, detail=f"Cannot remove '{app_id}' while installed.")
    success = mgr.remove_local_app(app_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Local application '{app_id}' not found.")


@import_router.post("/build-and-install")
async def build_and_install_source_app(
    req: InstallFromSourceRequest,
    builder: SourceBuilder = Depends(get_source_builder),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Clones repo, builds Docker image locally, and installs app as a managed plugin."""
    try:
        new_plugin, manifest, build_logs = builder.build_and_prepare_plugin(req)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Build and deployment failed: {e}")

    config = repo.get_config()
    existing_plugins = [p for p in config.plugins if p.id != new_plugin.id]
    existing_plugins.append(new_plugin)
    try:
        repo.save_plugins_config(PluginsConfig(plugins=existing_plugins))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save plugin configuration: {e}")

    ingress_route_id: Optional[str] = None
    if req.expose_edge_ingress and req.ingress_domain:
        target_port = 8080
        if new_plugin.containers and new_plugin.containers[0].ports:
            target_port = new_plugin.containers[0].ports[0].host_port
        ingress_route_id = provision_ingress_route(config, repo, req.ingress_domain, target_port)

    return {
        "success": True,
        "message": f"Successfully built and installed {new_plugin.name} from source.",
        "plugin_id": new_plugin.id,
        "ingress_route_id": ingress_route_id,
        "build_logs": build_logs,
    }
