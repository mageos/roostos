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
    config, certificates, cluster, health, events, identity, setup, edge, edge_peers, catalog,
    telemetry, alerts, updates, dns, topology, dhcp, household, family, protection
)
from roostos_web.services.events import event_publisher
from roostos_web import __version__

from roostos_web.services.base import get_repository, set_repository, get_dbus_client, set_dbus_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "mode", "full") != "edge_gateway":
        try:
            client = await get_dbus_client()
            event_publisher.setup_dbus_listeners(client)
            client_type = "MockRoostClient" if os.environ.get("ROOSTOS_MOCK") == "1" else "RoostOS D-Bus Daemon"
            print(f"Connected to {client_type} and initialized SSE event stream.")
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


class ApiV1FallbackMiddleware:
    """Transparently rewrites unversioned /api/* paths to /api/v1/* and prevents stale UI caching."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        is_static_http = False
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path.startswith("/api/") and not path.startswith("/api/v1/"):
                scope["path"] = f"/api/v1{path[4:]}"
                if "raw_path" in scope:
                    scope["raw_path"] = scope["path"].encode("ascii")
            elif scope["type"] == "http" and not path.startswith("/api/"):
                is_static_http = True

        if not is_static_http:
            await self.app(scope, receive, send)
            return

        async def send_with_no_cache(message):
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() not in (b"cache-control", b"pragma", b"expires")
                ]
                headers.append((b"cache-control", b"no-cache, no-store, must-revalidate"))
                headers.append((b"pragma", b"no-cache"))
                headers.append((b"expires", b"0"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_no_cache)


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
    app_instance.add_middleware(ApiV1FallbackMiddleware)

    # Public ACME HTTP-01 challenge responder for Let's Encrypt validation
    app_instance.include_router(certificates.acme_challenge_router)

    if active_mode == "edge_gateway":
        for rtr in (edge.router, edge_peers.router, health.router):
            app_instance.include_router(rtr)
    else:
        for rtr in (
            setup.router, edge.router, edge_peers.router, catalog.router,
            telemetry.router, alerts.router, updates.router, auth.router,
            system.router, dns.router, topology.router, identity.router,
            cluster.router, health.router, devices.router, network.router,
            schedules.router, plugins.router, diagnostics.router, config.router,
            certificates.router, events.router, dhcp.router, household.router,
            family.router, protection.router,
        ):
            app_instance.include_router(rtr)

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


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the argument parser for roostos_web."""
    parser = argparse.ArgumentParser(description="RoostOS Web API & UI Service")
    parser.add_argument("--config-dir", default=os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos"), help="Directory containing RoostOS configuration files")
    parser.add_argument("--container-config", default=os.environ.get("ROOSTOS_CONTAINER_CONFIG"), help="Path to container configuration YAML or preset ('mock', 'prod')")
    parser.add_argument("--providers-config", default=os.environ.get("ROOSTOS_PROVIDERS_CONFIG"), help="Legacy alias for --container-config")
    parser.add_argument("--auth-provider", default=os.environ.get("ROOSTOS_AUTH_PROVIDER"), help="Override auth provider: 'pam', 'mock', 'ldap'")
    parser.add_argument("--config-repo", default=os.environ.get("ROOSTOS_CONFIG_REPO"), help="Override repository: 'staging', 'yaml', 'memory'")
    parser.add_argument("--system-client", default=os.environ.get("ROOSTOS_SYSTEM_CLIENT"), help="Override system client: 'dbus', 'mock'")
    parser.add_argument("--cert-manager", default=os.environ.get("ROOSTOS_CERT_MANAGER"), help="Override certificate manager: 'standard', 'mock'")
    parser.add_argument("--firewall-manager", default=os.environ.get("ROOSTOS_FIREWALL_MANAGER"), help="Override firewall manager: 'nftables', 'iptables', 'ebpf', 'mock'")
    parser.add_argument("--dhcp-manager", default=os.environ.get("ROOSTOS_DHCP_MANAGER"), help="Override DHCP manager: 'kea', 'dnsmasq', 'mock'")
    parser.add_argument("--dns-manager", default=os.environ.get("ROOSTOS_DNS_MANAGER"), help="Override DNS manager: 'local', 'technitium', 'dnsmasq', 'mock'")
    parser.add_argument("--network-manager", default=os.environ.get("ROOSTOS_NETWORK_MANAGER"), help="Override network manager: 'systemd', 'mock'")
    parser.add_argument("--host", default=os.environ.get("ROOSTOS_HOST", "0.0.0.0"), help="Host IP to bind web server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("ROOSTOS_PORT", os.environ.get("ROOSTOS_WEB_PORT", 8000))), help="Port to bind web server")
    parser.add_argument("--mode", default=os.environ.get("ROOSTOS_MODE"), choices=["full", "edge", "edge_gateway", "api_only", "limited"], help="Server operation mode: 'full', 'edge_gateway', or 'api_only'")
    parser.add_argument("--api-only", "--no-ui", dest="no_ui", action="store_true", default=False, help="Disable hosting the static Web UI, running API only")
    parser.add_argument("--mock", "--dev", dest="mock", action="store_true", default=False, help="Launch standalone mock backend with seeded in-memory state and mock client for UI testing")
    parser.add_argument("--reload", action="store_true", default=False, help="Enable auto-reload on code changes")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    container_config_target = args.container_config or args.providers_config
    if args.mock and not container_config_target:
        container_config_target = "mock"

    overrides = {
        "auth_provider": args.auth_provider,
        "config_repository": args.config_repo,
        "system_client": args.system_client,
        "cert_manager": args.cert_manager,
        "firewall_manager": args.firewall_manager,
        "dhcp_manager": args.dhcp_manager,
        "dns_manager": args.dns_manager,
        "network_manager": args.network_manager,
    }

    providers_settings = load_providers_settings(
        config_dir=args.config_dir,
        providers_config_path=container_config_target,
        overrides=overrides
    )

    is_mock = (
        args.mock
        or providers_settings.auth_provider == "mock"
        or providers_settings.system_client == "mock"
        or providers_settings.auto_auth
    )

    if is_mock:
        os.environ["ROOSTOS_MOCK"] = "1"
        if providers_settings.auto_auth or args.mock:
            os.environ["ROOSTOS_MOCK_AUTH"] = "1"
            os.environ["ROOSTOS_DEV_MOCK"] = "1"
        if not args.config_dir or args.config_dir == "/etc/roostos":
            import tempfile
            mock_dir = os.path.join(tempfile.gettempdir(), "roostos-ui-mock")
            os.makedirs(mock_dir, exist_ok=True)
            args.config_dir = mock_dir
            os.environ["ROOSTOS_CONFIG_DIR"] = mock_dir

    if args.config_dir:
        os.environ["ROOSTOS_CONFIG_DIR"] = args.config_dir

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

    if is_mock:
        print("=" * 64)
        print("  🚀 RoostOS UI Test Server (Mock Container Active)")
        if providers_settings.description:
            print(f"  📋 Profile:    {providers_settings.description}")
        print(f"  🌐 Web UI:     http://{args.host}:{args.port}/")
        print(f"  📚 API Docs:   http://{args.host}:{args.port}/docs")
        print(f"  🔑 Auth:       {'Auto-Login (Admin)' if providers_settings.auto_auth else 'Mock (User: admin, Pass: password)'}")
        print(f"  💾 Data Store: In-Memory ({providers_settings.data_seeder} seed)")
        print("=" * 64)
    else:
        print(
            f"RoostOS Web initialized with container profile: auth='{providers_settings.auth_provider}', "
            f"repo='{providers_settings.config_repository}', client='{providers_settings.system_client}', "
            f"mode='{app_to_run.state.mode}', ui={not app_to_run.state.no_ui}"
        )

    if args.reload:
        uvicorn.run("roostos_web.main:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app_to_run, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
