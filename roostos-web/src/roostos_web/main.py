import os
import sys
from typing import Optional
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from roostos_engine.repository import ConfigRepository, YAMLConfigRepository
from roostos_sdk.client import RoostClient

from roostos_web.routers import auth, system, devices, network, schedules, plugins, diagnostics, config, certificates, cluster, health, events
from roostos_web.services.events import event_publisher

from roostos_web.services.base import get_repository, set_repository, get_dbus_client, set_dbus_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Validate connection to local D-Bus daemon on startup
        client = await get_dbus_client()
        event_publisher.setup_dbus_listeners(client)
        print("Connected to RoostOS D-Bus Daemon and initialized SSE event stream.")
    except Exception as e:
        print(f"Warning: Could not connect to RoostOS D-Bus daemon: {e}", file=sys.stderr)
    yield


app = FastAPI(title="RoostOS Core Management Web API", version="0.1.0", lifespan=lifespan)

# Enable CORS for developer environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount modular routes
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(cluster.router)
app.include_router(health.router)
app.include_router(devices.router)
app.include_router(network.router)
app.include_router(schedules.router)
app.include_router(plugins.router)
app.include_router(diagnostics.router)
app.include_router(config.router)
app.include_router(certificates.router)
app.include_router(events.router)

# Mount Static Files (the Single Page Application UI)
web_assets_path = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
if os.path.exists(web_assets_path):
    app.mount("/", StaticFiles(directory=web_assets_path, html=True), name="static")
else:
    # Development fallback
    dev_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "roostos-ui")
    if os.path.exists(dev_path):
        app.mount("/", StaticFiles(directory=dev_path, html=True), name="static")


import argparse
from roostos_web.di import create_web_injector, set_injector
from roostos_engine.di import load_providers_settings


def main():
    parser = argparse.ArgumentParser(description="RoostOS Web API & UI Service")
    parser.add_argument("--config-dir", default=os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos"), help="Directory containing RoostOS configuration files")
    parser.add_argument("--providers-config", default=os.environ.get("ROOSTOS_PROVIDERS_CONFIG"), help="Path to custom providers.yaml")
    parser.add_argument("--auth-provider", default=os.environ.get("ROOSTOS_AUTH_PROVIDER"), help="Override auth provider: 'pam', 'mock', 'ldap'")
    parser.add_argument("--config-repo", default=os.environ.get("ROOSTOS_CONFIG_REPO"), help="Override repository: 'staging', 'yaml', 'memory'")
    parser.add_argument("--system-client", default=os.environ.get("ROOSTOS_SYSTEM_CLIENT"), help="Override system client: 'dbus', 'mock'")
    parser.add_argument("--cert-manager", default=os.environ.get("ROOSTOS_CERT_MANAGER"), help="Override certificate manager: 'standard', 'mock'")
    parser.add_argument("--firewall-manager", default=os.environ.get("ROOSTOS_FIREWALL_MANAGER"), help="Override firewall manager: 'nftables', 'mock'")
    parser.add_argument("--host", default=os.environ.get("ROOSTOS_HOST", "0.0.0.0"), help="Host IP to bind web server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("ROOSTOS_PORT", os.environ.get("ROOSTOS_WEB_PORT", 8000))), help="Port to bind web server")

    args = parser.parse_args()

    # Configure environmental overrides
    if args.config_dir:
        os.environ["ROOSTOS_CONFIG_DIR"] = args.config_dir

    overrides = {
        "auth_provider": args.auth_provider,
        "config_repository": args.config_repo,
        "system_client": args.system_client,
        "cert_manager": args.cert_manager,
        "firewall_manager": args.firewall_manager,
    }

    providers_settings = load_providers_settings(
        config_dir=args.config_dir,
        providers_config_path=args.providers_config,
        overrides=overrides
    )

    injector = create_web_injector(
        config_dir=args.config_dir,
        providers_settings=providers_settings
    )
    set_injector(injector)

    print(f"RoostOS Web initialized with providers: auth='{providers_settings.auth_provider}', repo='{providers_settings.config_repository}', client='{providers_settings.system_client}'")
    uvicorn.run("roostos_web.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
