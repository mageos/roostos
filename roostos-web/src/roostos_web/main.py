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

from roostos_web.routers import (
    auth, system, devices, network, schedules, plugins, diagnostics,
    config, certificates, cluster, health, events, identity, setup, edge, catalog,
    telemetry, alerts, updates, dns
)
from roostos_web.services.events import event_publisher
from roostos_web import __version__

from roostos_web.services.base import get_repository, set_repository, get_dbus_client, set_dbus_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "mode", "full") != "edge_gateway":
        try:
            # Validate connection to local D-Bus daemon on startup
            client = await get_dbus_client()
            event_publisher.setup_dbus_listeners(client)
            print("Connected to RoostOS D-Bus Daemon and initialized SSE event stream.")
        except Exception as e:
            print(f"Warning: Could not connect to RoostOS D-Bus daemon: {e}", file=sys.stderr)
    yield


def determine_server_mode(
    config_dir: Optional[str] = None,
    explicit_mode: Optional[str] = None,
) -> str:
    """Determines server mode: 'edge_gateway', 'api_only', or 'full'."""
    if explicit_mode:
        normalized = explicit_mode.strip().lower()
        if normalized in ("edge", "edge_gateway", "limited"):
            return "edge_gateway"
        return normalized

    env_mode = os.environ.get("ROOSTOS_MODE") or os.environ.get("ROOSTOS_ROLE")
    if env_mode:
        normalized = env_mode.strip().lower()
        if normalized in ("edge", "edge_gateway", "limited"):
            return "edge_gateway"
        return normalized

    cfg_dir = config_dir or os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
    sys_path = os.path.join(cfg_dir, "system.yaml")
    if os.path.exists(sys_path):
        try:
            import yaml
            with open(sys_path, "r") as f:
                data = yaml.safe_load(f) or {}
            roles = data.get("system", {}).get("cluster", {}).get("roles", [])
            if "edge_gateway" in roles:
                return "edge_gateway"
        except Exception:
            pass

    return "full"


def create_app(
    mode: Optional[str] = None,
    no_ui: Optional[bool] = None,
    config_dir: Optional[str] = None,
) -> FastAPI:
    """Builds and configures the FastAPI application according to node role."""
    active_mode = determine_server_mode(config_dir=config_dir, explicit_mode=mode)
    disable_ui = no_ui if no_ui is not None else (
        os.environ.get("ROOSTOS_NO_UI", "").lower() in ("1", "true", "yes")
        or active_mode in ("edge_gateway", "api_only")
    )

    title = "RoostOS Edge Gateway API" if active_mode == "edge_gateway" else "RoostOS Core Management Web API"
    app_instance = FastAPI(title=title, version=__version__, lifespan=lifespan)
    app_instance.state.mode = active_mode
    app_instance.state.no_ui = disable_ui

    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if active_mode == "edge_gateway":
        # Limited mode: Minimal attack surface for VPS Edge Gateway
        app_instance.include_router(edge.router)
        app_instance.include_router(health.router)
    else:
        # Full Router mode: Mount all management subsystems
        app_instance.include_router(setup.router)
        app_instance.include_router(edge.router)
        app_instance.include_router(catalog.router)
        app_instance.include_router(telemetry.router)
        app_instance.include_router(alerts.router)
        app_instance.include_router(updates.router)
        app_instance.include_router(auth.router)
        app_instance.include_router(system.router)
        app_instance.include_router(dns.router)
        app_instance.include_router(identity.router)
        app_instance.include_router(cluster.router)
        app_instance.include_router(health.router)
        app_instance.include_router(devices.router)
        app_instance.include_router(network.router)
        app_instance.include_router(schedules.router)
        app_instance.include_router(plugins.router)
        app_instance.include_router(diagnostics.router)
        app_instance.include_router(config.router)
        app_instance.include_router(certificates.router)
        app_instance.include_router(events.router)

    # Mount Static UI if not disabled
    if not disable_ui:
        web_assets_path = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
        if os.path.exists(web_assets_path):
            app_instance.mount("/", StaticFiles(directory=web_assets_path, html=True), name="static")
        else:
            dev_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "roostos-ui"
            )
            if os.path.exists(dev_path):
                app_instance.mount("/", StaticFiles(directory=dev_path, html=True), name="static")

    return app_instance


app = create_app()


import argparse
from roostos_web.di import create_web_injector, set_injector
from roostos_engine.di import load_providers_settings


def main() -> None:
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
    parser.add_argument("--mode", default=os.environ.get("ROOSTOS_MODE"), choices=["full", "edge", "edge_gateway", "api_only", "limited"], help="Server operation mode: 'full', 'edge_gateway', or 'api_only'")
    parser.add_argument("--api-only", "--no-ui", dest="no_ui", action="store_true", default=False, help="Disable hosting the static Web UI, running API only")

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

    app_to_run = create_app(
        mode=args.mode,
        no_ui=True if args.no_ui else None,
        config_dir=args.config_dir,
    )

    print(
        f"RoostOS Web initialized with providers: auth='{providers_settings.auth_provider}', "
        f"repo='{providers_settings.config_repository}', client='{providers_settings.system_client}', "
        f"mode='{app_to_run.state.mode}', ui={not app_to_run.state.no_ui}"
    )
    uvicorn.run(app_to_run, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
