"""FastAPI router for RoostOS decentralized application catalog."""

import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from roostos_engine.models.catalog import (
    CatalogAppEntry,
    CatalogSourceConfig,
    InstallAppRequest,
)
from roostos_engine.models.plugins import PluginsConfig
from roostos_engine.catalog_manager import CatalogManager
from roostos_engine.ingress_helper import provision_ingress_route
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected
from roostos_web.routers.catalog_images import images_router
from roostos_web.routers.catalog_import import import_router

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
router.include_router(images_router)
router.include_router(import_router)

_catalog_mgr: Optional[CatalogManager] = None


def get_catalog_manager(repo: ConfigRepository = Injected(ConfigRepository)) -> CatalogManager:
    """Dependency injector for CatalogManager."""
    global _catalog_mgr
    config_dir = getattr(repo, "config_dir", os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos"))
    if _catalog_mgr is None or _catalog_mgr.config_dir != config_dir:
        _catalog_mgr = CatalogManager(config_dir=config_dir)
    return _catalog_mgr


@router.get("/sources", response_model=List[CatalogSourceConfig])
async def list_catalog_sources(
    mgr: CatalogManager = Depends(get_catalog_manager),
    current_user: UserSession = Depends(get_current_user),
) -> List[CatalogSourceConfig]:
    """Lists all configured remote and local catalog sources."""
    return mgr.list_sources()


@router.post("/sources", response_model=CatalogSourceConfig, status_code=status.HTTP_201_CREATED)
async def add_catalog_source(
    source: CatalogSourceConfig,
    mgr: CatalogManager = Depends(get_catalog_manager),
    current_user: UserSession = Depends(get_current_admin),
) -> CatalogSourceConfig:
    """Registers a new remote or local application catalog source."""
    if not source.id or not source.url:
        raise HTTPException(status_code=400, detail="Source 'id' and 'url' are required.")
    mgr.add_source(source)
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_catalog_source(
    source_id: str,
    mgr: CatalogManager = Depends(get_catalog_manager),
    current_user: UserSession = Depends(get_current_admin),
) -> None:
    """Removes a configured catalog repository source."""
    success = mgr.remove_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Catalog source '{source_id}' not found.")


@router.post("/refresh", response_model=List[CatalogAppEntry])
async def refresh_catalogs(
    mgr: CatalogManager = Depends(get_catalog_manager),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_admin),
) -> List[CatalogAppEntry]:
    """Force re-fetches and updates cached application manifests across all sources."""
    config = repo.get_config()
    installed_ids = [p.id for p in config.plugins]
    return mgr.get_available_apps(installed_plugin_ids=installed_ids)


@router.get("/apps", response_model=List[CatalogAppEntry])
async def list_catalog_apps(
    mgr: CatalogManager = Depends(get_catalog_manager),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_user),
) -> List[CatalogAppEntry]:
    """Returns aggregated applications available for installation."""
    config = repo.get_config()
    installed_ids = [p.id for p in config.plugins]
    return mgr.get_available_apps(installed_plugin_ids=installed_ids)


@router.get("/apps/{app_id}", response_model=CatalogAppEntry)
async def get_catalog_app(
    app_id: str,
    mgr: CatalogManager = Depends(get_catalog_manager),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_user),
) -> CatalogAppEntry:
    """Retrieves detailed deployment specifications for a catalog application."""
    config = repo.get_config()
    installed_ids = [p.id for p in config.plugins]
    apps = mgr.get_available_apps(installed_plugin_ids=installed_ids)
    app = next((a for a in apps if a.id == app_id), None)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found in any catalog.")
    return app


@router.post("/apps/install", status_code=status.HTTP_201_CREATED)
async def install_catalog_app(
    req: InstallAppRequest,
    mgr: CatalogManager = Depends(get_catalog_manager),
    repo: ConfigRepository = Injected(ConfigRepository),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Installs an application from the catalog, configuring containers and optional Edge Ingress."""
    config = repo.get_config()
    installed_ids = [p.id for p in config.plugins]
    if req.app_id in installed_ids:
        raise HTTPException(status_code=400, detail=f"Application '{req.app_id}' is already installed.")

    apps = mgr.get_available_apps(installed_plugin_ids=installed_ids)
    app = next((a for a in apps if a.id == req.app_id), None)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application '{req.app_id}' not found in catalog.")

    new_plugin = mgr.create_plugin_from_app(app, req)
    updated_plugins = list(config.plugins) + [new_plugin]
    try:
        repo.save_plugins_config(PluginsConfig(plugins=updated_plugins))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save plugin configuration: {e}")

    ingress_route_id: Optional[str] = None
    if req.expose_edge_ingress and req.ingress_domain:
        target_port = 8080
        if app.container.ports:
            target_port = req.custom_ports.get(app.container.ports[0].container_port, app.container.ports[0].host_port)
        ingress_route_id = provision_ingress_route(config, repo, req.ingress_domain, target_port)

    return {
        "success": True,
        "message": f"Successfully installed application: {app.name}",
        "plugin_id": app.id,
        "ingress_route_id": ingress_route_id,
    }
