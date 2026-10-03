"""FastAPI router for first-run setup wizard and node environment discovery."""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from roostos_cli.models import (
    NodeRole,
    SystemEnvironment,
    GatewayConfigParams,
    ControllerConfigParams,
    WorkstationConfigParams,
    SetupResult,
)
from roostos_cli.inspector import EnvironmentInspector
from roostos_cli.discovery import NetworkDiscoverer
from roostos_cli.wizard import SetupWizard

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupStatusResponse(BaseModel):
    is_configured: bool
    configured_roles: list[str] = Field(default_factory=list)
    environment: SystemEnvironment


class ApplySetupPayload(BaseModel):
    role: NodeRole
    gateway_params: Optional[GatewayConfigParams] = None
    controller_params: Optional[ControllerConfigParams] = None
    workstation_params: Optional[WorkstationConfigParams] = None
    mock_install: Optional[bool] = None


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(config_dir: Optional[str] = None) -> SetupStatusResponse:
    """Checks whether the system has been initialized and returns environment details."""
    target_dir = config_dir or os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
    sys_path = os.path.join(target_dir, "system.yaml")
    is_configured = False
    configured_roles: list[str] = []

    if os.path.exists(sys_path):
        try:
            import yaml
            with open(sys_path, "r") as f:
                data = yaml.safe_load(f) or {}
            roles = data.get("system", {}).get("cluster", {}).get("roles", [])
            if roles:
                is_configured = True
                configured_roles = roles
        except Exception:
            pass

    env = EnvironmentInspector.inspect()
    env.discovered_gateways = NetworkDiscoverer.discover_gateways()
    env.discovered_controllers = NetworkDiscoverer.discover_controllers()

    return SetupStatusResponse(
        is_configured=is_configured,
        configured_roles=configured_roles,
        environment=env,
    )


@router.post("/discover")
async def scan_network() -> Dict[str, Any]:
    """Scans the local subnet for existing RoostOS gateways and controllers."""
    services = NetworkDiscoverer.discover_services(timeout_seconds=1.5)
    return {
        "services": [s.model_dump() for s in services],
        "gateways": [s.model_dump() for s in services if s.service_type == "gateway"],
        "controllers": [s.model_dump() for s in services if s.service_type == "controller"],
    }


@router.post("/apply", response_model=SetupResult)
async def apply_setup(
    payload: ApplySetupPayload,
    config_dir: Optional[str] = None
) -> SetupResult:
    """Executes setup provisioning for the selected role."""
    target_dir = config_dir or os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos")
    mock = payload.mock_install
    if mock is None:
        mock = (config_dir is not None) or (os.environ.get("ROOSTOS_MOCK_INSTALL") == "1")
    wizard = SetupWizard(config_dir=target_dir, mock_install=mock)

    result = wizard.run_setup(
        role=payload.role,
        gateway_params=payload.gateway_params,
        controller_params=payload.controller_params,
        workstation_params=payload.workstation_params,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.message,
        )

    return result


@router.get("/enroll-script")
async def get_enrollment_script(request: Request, token: Optional[str] = None) -> Dict[str, str]:
    """Generates the single-line command for client workstation enrollment."""
    host = request.headers.get("host", "roostos.local:8000")
    token_arg = f"--token={token}" if token else ""
    cmd = f"curl -sSL http://{host}/api/setup/enroll.sh | sudo bash -s -- {token_arg}".strip()
    return {
        "command": cmd,
        "token": token or "",
    }


@router.get("/enroll.sh", response_class=PlainTextResponse)
async def get_enroll_script() -> str:
    """Serves the automated workstation enrollment bash script."""
    candidate_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../scripts/roostos-workstation-enroll.sh")),
        "/usr/local/bin/roostos-workstation-enroll",
        "/usr/local/bin/roostos-workstation-join",
        "/usr/share/roostos/scripts/roostos-workstation-enroll.sh",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            with open(p, "r") as f:
                return f.read()

    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo 'Installing RoostOS Workstation Client stack...'\n"
        "apt-get update -qq && apt-get install -y -qq python3-paho-mqtt dbus\n"
    )
