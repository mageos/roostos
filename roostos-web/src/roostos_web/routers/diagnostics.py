import re
import subprocess
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from roostos_web.auth import get_current_parent, get_current_admin, UserSession

router = APIRouter(tags=["diagnostics"])

# Valid host regex: alphanumeric, dots, and hyphens
HOST_REGEX = re.compile(r"^[a-zA-Z0-9.-]+$")

# Permitted services for log viewing
PERMITTED_SERVICES = {
    "roostd": "roostd.service",
    "roostos-web": "roostos-web.service",
    "systemd-networkd": "systemd-networkd.service",
    "kea": "kea-dhcp4-server.service",
    "iwd": "iwd.service"
}

class PingRequest(BaseModel):
    host: str = Field(..., max_length=100)
    count: int = Field(4, ge=1, le=10)

class TracerouteRequest(BaseModel):
    host: str = Field(..., max_length=100)

class DNSLookupRequest(BaseModel):
    host: str = Field(..., max_length=100)

def validate_host(host: str) -> None:
    if not HOST_REGEX.match(host):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid host. Must be a valid domain name or IP address."
        )

@router.post("/api/diagnostics/ping")
async def ping(
    request: PingRequest,
    current_user: UserSession = Depends(get_current_parent)
):
    """Executes a diagnostic ICMP ping check."""
    validate_host(request.host)
    try:
        res = subprocess.run(
            ["ping", "-c", str(request.count), request.host],
            capture_output=True,
            text=True,
            timeout=15
        )
        return {
            "status": "success" if res.returncode == 0 else "failed",
            "output": res.stdout or res.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Ping timed out")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/api/diagnostics/traceroute")
async def traceroute(
    request: TracerouteRequest,
    current_user: UserSession = Depends(get_current_parent)
):
    """Executes a diagnostic network traceroute check."""
    validate_host(request.host)
    try:
        # Check if traceroute is installed, fallback to tracepath if missing
        cmd = ["traceroute", "-w", "2", request.host]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        # Fallback to tracepath if traceroute fails with command not found
        if res.returncode == 127 or "not found" in res.stderr:
            cmd = ["tracepath", "-m", "30", request.host]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        return {
            "status": "success" if res.returncode == 0 else "failed",
            "output": res.stdout or res.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Traceroute timed out")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/api/diagnostics/dns-lookup")
async def dns_lookup(
    request: DNSLookupRequest,
    current_user: UserSession = Depends(get_current_parent)
):
    """Executes a diagnostic host resolution lookup."""
    validate_host(request.host)
    try:
        res = subprocess.run(
            ["nslookup", request.host],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Fallback to dig if nslookup is not found/fails
        if res.returncode == 127 or "not found" in res.stderr:
            res = subprocess.run(
                ["dig", request.host],
                capture_output=True,
                text=True,
                timeout=10
            )
        return {
            "status": "success" if res.returncode == 0 else "failed",
            "output": res.stdout or res.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="DNS lookup timed out")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/diagnostics/logs")
async def get_logs(
    service: str = Query("roostd"),
    limit: int = Query(100, ge=1, le=500),
    current_user: UserSession = Depends(get_current_admin)
):
    """Returns recent system logs for specified router service units."""
    if service not in PERMITTED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Log access not permitted for '{service}'. Allowed: {list(PERMITTED_SERVICES.keys())}"
        )
    
    systemd_unit = PERMITTED_SERVICES[service]
    try:
        res = subprocess.run(
            ["journalctl", "-u", systemd_unit, "-n", str(limit), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "service": service,
            "logs": res.stdout or res.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Log retrieval timed out")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
