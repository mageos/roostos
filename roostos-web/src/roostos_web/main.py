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

from roostos_web.routers import auth, system, devices, network, schedules, plugins, diagnostics, config, certificates

from roostos_web.services.base import get_repository, set_repository, get_dbus_client, set_dbus_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Validate connection to local D-Bus daemon on startup
        await get_dbus_client()
        print("Connected to RoostOS D-Bus Daemon successfully.")
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
app.include_router(devices.router)
app.include_router(network.router)
app.include_router(schedules.router)
app.include_router(plugins.router)
app.include_router(diagnostics.router)
app.include_router(config.router)
app.include_router(certificates.router)

# Mount Static Files (the Single Page Application UI)
web_assets_path = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
if os.path.exists(web_assets_path):
    app.mount("/", StaticFiles(directory=web_assets_path, html=True), name="static")
else:
    # Development fallback
    dev_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "roostos-ui")
    if os.path.exists(dev_path):
        app.mount("/", StaticFiles(directory=dev_path, html=True), name="static")


def main():
    port = int(os.environ.get("ROOSTOS_PORT", os.environ.get("ROOSTOS_WEB_PORT", 8000)))
    host = os.environ.get("ROOSTOS_HOST", "0.0.0.0")
    # Disable reload in production CLI entrypoint to avoid launch issues
    uvicorn.run("roostos_web.main:app", host=host, port=port)

if __name__ == "__main__":
    main()
