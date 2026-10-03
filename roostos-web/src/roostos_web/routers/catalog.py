"""FastAPI router for RoostOS decentralized application catalog and local image deployment."""

import os
import uuid
import tempfile
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from roostos_engine.models.catalog import (
    CatalogAppEntry,
    CatalogSourceConfig,
    InstallAppRequest,
)
from roostos_engine.models.plugins import PluginsConfig
from roostos_engine.models.network import NetworkConfig
from roostos_engine.models.edge import IngressRoute
from roostos_engine.catalog_manager import CatalogManager
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_user, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

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

    # 1. Convert catalog entry to plugin configuration and persist
    new_plugin = mgr.create_plugin_from_app(app, req)
    updated_plugins = list(config.plugins) + [new_plugin]
    try:
        repo.save_plugins_config(PluginsConfig(plugins=updated_plugins))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save plugin configuration: {e}")

    # 2. Configure Edge Gateway Ingress Route if requested
    ingress_route_id: Optional[str] = None
    if req.expose_edge_ingress and req.ingress_domain:
        edge_gateways = getattr(config.network, "edge_gateways", [])
        if edge_gateways:
            gw = edge_gateways[0]
            target_port = 8080
            if app.container.ports:
                target_port = req.custom_ports.get(
                    app.container.ports[0].container_port,
                    app.container.ports[0].host_port
                )
            # Default target IP is bridge IP or local LAN
            target_ip = "192.168.1.1"
            if config.network.bridges:
                target_ip = config.network.bridges[0].ip.split("/")[0]

            ingress_route_id = f"route-{uuid.uuid4().hex[:6]}"
            new_route = IngressRoute(
                id=ingress_route_id,
                domain=req.ingress_domain.strip().lower(),
                target_ip=target_ip,
                target_port=target_port,
                ssl_enabled=True,
                edge_gateway_id=gw.id,
            )
            gw.ingress_routes.append(new_route)
            try:
                repo.save_network_config(config.network)
            except Exception:
                pass

    return {
        "success": True,
        "message": f"Successfully installed application: {app.name}",
        "plugin_id": app.id,
        "ingress_route_id": ingress_route_id,
    }


@router.post("/images/load")
async def load_local_docker_image(
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Loads a container image from an uploaded .tar archive directly into the local Docker daemon."""
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Docker service unavailable: {e}")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            images = client.images.load(f.read())
        loaded_tags = [tag for img in images for tag in img.tags]
        return {
            "success": True,
            "message": f"Loaded {len(images)} image(s) into local cache.",
            "loaded_tags": loaded_tags or ["(untagged)"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load image archive: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/images")
async def list_local_docker_images(
    current_user: UserSession = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Lists Docker container images available in the local daemon cache."""
    try:
        import docker
        client = docker.from_env()
        images = client.images.list()
        return [
            {
                "id": img.short_id,
                "tags": img.tags,
                "size_mb": round(img.attrs.get("Size", 0) / (1024 * 1024), 1),
                "created": img.attrs.get("Created", ""),
            }
            for img in images
        ]
    except Exception:
        # Graceful fallback in environments without active Docker daemon
        return []
