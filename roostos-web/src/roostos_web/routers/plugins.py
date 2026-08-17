import os
import sys
from typing import List, Optional
from fastapi import APIRouter, Depends, Body, HTTPException, UploadFile, File, Request, Response
from fastapi.responses import JSONResponse

from roostos_engine.config import PluginsConfig, PluginConfig, ContainerConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_user, get_current_admin, UserSession
from roostos_web.services import PluginsService
from roostos_web.di import Injected

router = APIRouter(tags=["plugins"])

@router.get("/api/plugins")
async def get_plugins(
    current_user: UserSession = Depends(get_current_user),
    plugins_service: PluginsService = Injected(PluginsService)
):
    """Returns the list of installed plugin configurations with their container statuses."""
    return {"plugins": await plugins_service.get_plugins_status()}

@router.post("/api/plugins/upload")
async def upload_plugin_zip(
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Installs a plugin package from an uploaded ZIP archive containing a manifest and UI script."""
    import zipfile
    import tempfile
    import yaml
    import shutil
    
    contents = await file.read()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "plugin.zip")
        with open(zip_path, "wb") as f:
            f.write(contents)
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
            
        manifest_path = None
        for name in ("roostos-pod.yaml", "roostos-pod.yml", "manifest.yaml", "manifest.yml"):
            p = os.path.join(tmpdir, name)
            if os.path.exists(p):
                manifest_path = p
                break
                
        if not manifest_path:
            for root, dirs, files in os.walk(tmpdir):
                for f_name in files:
                    if f_name in ("roostos-pod.yaml", "roostos-pod.yml"):
                        manifest_path = os.path.join(root, f_name)
                        break
                if manifest_path:
                    break
                    
        if not manifest_path:
            raise HTTPException(status_code=400, detail="Could not find roostos-pod.yaml inside ZIP archive.")
            
        try:
            with open(manifest_path, "r") as f:
                manifest = yaml.safe_load(f)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse roostos-pod.yaml: {e}")
            
        plugin_id = manifest.get("id")
        name = manifest.get("name")
        network_mode = manifest.get("network_mode", "bridge")
        ui_entrypoint = manifest.get("ui_entrypoint")
        containers_raw = manifest.get("containers", [])
        
        if not plugin_id or not name:
            raise HTTPException(status_code=400, detail="Manifest must contain 'id' and 'name'.")
            
        containers = []
        for c in containers_raw:
            try:
                containers.append(ContainerConfig.model_validate(c))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid container specification in manifest: {e}")
                
        ui_src = os.path.join(os.path.dirname(manifest_path), "ui.js")
        ui_copied = False
        assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
        dest_dir = os.path.join(assets_dir, "plugins", plugin_id)
        
        if os.path.exists(ui_src):
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = os.path.join(dest_dir, "ui.js")
            shutil.copy2(ui_src, dest_file)
            ui_copied = True
            
        if ui_entrypoint and containers and not ui_copied:
            primary_image = containers[0].image
            try:
                await dbus.extract_plugin_ui(primary_image, ui_entrypoint, plugin_id)
            except Exception as e:
                local_dev_path = f"/home/matt/source/github/mageos/roostos/plugins/{plugin_id}/ui.js"
                if os.path.exists(local_dev_path):
                    print(f"Warning: Failed to extract UI from image, but local ui.js is available: {e}", file=sys.stderr)
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to extract plugin UI: {e}")
                    
        known_services = []
        for key in ["known_services", "knownServices", "known_service", "knownService"]:
            if key in manifest:
                val = manifest[key]
                if isinstance(val, list):
                    known_services.extend(val)
                elif isinstance(val, str):
                    known_services.append(val)
        known_services = list(dict.fromkeys(known_services))

        config = repo.get_config()
        existing_plugins = config.plugins
        
        new_plugin = PluginConfig(
            id=plugin_id,
            name=name,
            enabled=True,
            network_mode=network_mode,
            containers=containers,
            ui_entrypoint=ui_entrypoint,
            known_services=known_services
        )
        
        plugin_idx = next((i for i, p in enumerate(existing_plugins) if p.id == plugin_id), None)
        if plugin_idx is not None:
            existing_plugins[plugin_idx] = new_plugin
        else:
            existing_plugins.append(new_plugin)
            
        plugins_config_obj = PluginsConfig(plugins=existing_plugins)
        repo.save_plugins_config(plugins_config_obj)
        
        await dbus.get_config()
        return {"status": "success", "message": f"Plugin {plugin_id} installed successfully from ZIP archive."}

@router.post("/api/plugins/manifest")
async def install_plugin_via_manifest(
    manifest_yaml: str = Body(..., embed=True),
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Installs/registers a plugin directly from its YAML manifest text."""
    import yaml
    try:
        manifest = yaml.safe_load(manifest_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML manifest: {e}")

    plugin_id = manifest.get("id")
    name = manifest.get("name")
    network_mode = manifest.get("network_mode", "bridge")
    containers_data = manifest.get("containers", [])
    ui_entrypoint = manifest.get("ui_entrypoint")
    known_services = manifest.get("known_services", [])
    
    if not plugin_id or not name or not containers_data:
        raise HTTPException(status_code=400, detail="Manifest missing required fields (id, name, containers)")
        
    containers = [ContainerConfig(**c) for c in containers_data]
    
    if ui_entrypoint and containers:
        first_image = containers[0].image
        try:
            await dbus.extract_plugin_ui(first_image, ui_entrypoint, plugin_id)
        except Exception as e:
            assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
            ui_path = os.path.join(assets_dir, "plugins", plugin_id, "ui.js")
            local_dev_path = f"/home/matt/source/github/mageos/roostos/plugins/{plugin_id}/ui.js"
            if os.path.exists(ui_path) or os.path.exists(local_dev_path):
                print(f"Warning: Failed to extract UI from image for {plugin_id}, but local ui.js is available: {e}", file=sys.stderr)
            else:
                raise HTTPException(status_code=500, detail=f"Failed to extract plugin UI: {e}")

    config = repo.get_config()
    existing_plugins = config.plugins
    
    plugin_idx = next((i for i, p in enumerate(existing_plugins) if p.id == plugin_id), None)
    
    new_plugin = PluginConfig(
        id=plugin_id,
        name=name,
        enabled=True,
        network_mode=network_mode,
        containers=containers,
        ui_entrypoint=ui_entrypoint,
        known_services=known_services
    )
    
    if plugin_idx is not None:
        existing_plugins[plugin_idx] = new_plugin
    else:
        existing_plugins.append(new_plugin)
        
    plugins_config_obj = PluginsConfig(plugins=existing_plugins)
    repo.save_plugins_config(plugins_config_obj)
    
    await dbus.get_config()
    return {"status": "success", "message": f"Plugin {plugin_id} registered and loaded from manifest successfully."}

@router.post("/api/plugins")
async def install_plugin(
    id: str = Body(...),
    name: str = Body(...),
    image: str = Body(...),
    ui_entrypoint: Optional[str] = Body(None),
    network_mode: str = Body("bridge"),
    known_services: Optional[List[str]] = Body(None),
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Installs/registers a plugin, extracts its UI asset from container, and triggers reload."""
    if ui_entrypoint:
        try:
            await dbus.extract_plugin_ui(image, ui_entrypoint, id)
        except Exception as e:
            assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
            ui_path = os.path.join(assets_dir, "plugins", id, "ui.js")
            local_dev_path = f"/home/matt/source/github/mageos/roostos/plugins/{id}/ui.js"
            if os.path.exists(ui_path) or os.path.exists(local_dev_path):
                print(f"Warning: Failed to extract UI from image for {id}, but local ui.js is available: {e}", file=sys.stderr)
            else:
                raise HTTPException(status_code=500, detail=f"Failed to extract plugin UI: {e}")

    config = repo.get_config()
    existing_plugins = config.plugins
    
    plugin_idx = next((i for i, p in enumerate(existing_plugins) if p.id == id), None)
    main_container = ContainerConfig(name=id, image=image)
    
    new_plugin = PluginConfig(
        id=id,
        name=name,
        enabled=True,
        network_mode=network_mode,
        containers=[main_container],
        ui_entrypoint=ui_entrypoint,
        known_services=known_services or []
    )
    
    if plugin_idx is not None:
        existing_plugins[plugin_idx] = new_plugin
    else:
        existing_plugins.append(new_plugin)
        
    plugins_config_obj = PluginsConfig(plugins=existing_plugins)
    repo.save_plugins_config(plugins_config_obj)
    
    await dbus.get_config()
    return {"status": "success", "message": f"Plugin {id} registered and loaded successfully."}

@router.post("/api/plugins/{plugin_id}/toggle")
async def toggle_plugin(
    plugin_id: str,
    enabled: bool = Body(..., embed=True),
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Enables or disables an existing plugin."""
    config = repo.get_config()
    existing_plugins = config.plugins
    
    plugin = next((p for p in existing_plugins if p.id == plugin_id), None)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
        
    plugin.enabled = enabled
    
    plugins_config_obj = PluginsConfig(plugins=existing_plugins)
    repo.save_plugins_config(plugins_config_obj)
    
    await dbus.get_config()
    return {"status": "success", "message": f"Plugin {plugin_id} state updated successfully."}

@router.delete("/api/plugins/{plugin_id}")
async def delete_plugin(
    plugin_id: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Deletes/unregisters a plugin config from the system."""
    config = repo.get_config()
    existing_plugins = config.plugins
    
    plugin_idx = next((i for i, p in enumerate(existing_plugins) if p.id == plugin_id), None)
    if plugin_idx is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
        
    existing_plugins.pop(plugin_idx)
    
    plugins_config_obj = PluginsConfig(plugins=existing_plugins)
    repo.save_plugins_config(plugins_config_obj)
    
    await dbus.get_config()
    return {"status": "success", "message": f"Plugin {plugin_id} deleted successfully."}

@router.api_route("/api/services/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def service_proxy(
    service_name: str,
    path: str,
    request: Request,
    current_user: UserSession = Depends(get_current_user),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Reverse proxies request dynamically to the container hosting the plugin service."""
    import httpx
    
    target_ip = None
    target_port = None
    
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(filters={"label": f"org.roostos.plugin_id={service_name}"})
        if containers:
            container = containers[0]
            networks = container.attrs["NetworkSettings"]["Networks"]
            net_name = list(networks.keys())[0]
            target_ip = networks[net_name]["IPAddress"]
            
            ports = container.attrs["NetworkSettings"]["Ports"] or {}
            tcp_ports = [p.split("/")[0] for p in ports.keys() if p.endswith("/tcp")]
            if tcp_ports:
                target_port = tcp_ports[0]
            else:
                target_port = "80"
    except Exception as e:
        print(f"Proxy resolution warning: {e}", file=sys.stderr)

    if not target_ip or not target_port:
        return JSONResponse(
            content={"status": "mock", "message": f"Proxying to {service_name}/{path}"},
            status_code=200
        )

    url = f"http://{target_ip}:{target_port}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"
        
    async with httpx.AsyncClient() as client:
        try:
            proxy_response = await client.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "authorization")},
                content=await request.body(),
                timeout=10.0
            )
            return Response(
                content=proxy_response.content,
                status_code=proxy_response.status_code,
                headers=dict(proxy_response.headers)
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Bad Gateway proxying to service: {e}")
