"""FastAPI router for VictoriaMetrics telemetry queries and metrics collection."""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from roostos_engine.telemetry_manager import TelemetryManager
from roostos_engine.telemetry_collector import TelemetryCollector
from roostos_web.auth import get_current_user
from roostos_web.services.base import get_repository

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


def get_telemetry_manager() -> TelemetryManager:
    try:
        repo = get_repository()
        cfg = repo.get_config().system.telemetry
        return TelemetryManager(config=cfg)
    except Exception:
        return TelemetryManager()


def get_telemetry_collector() -> TelemetryCollector:
    mgr = get_telemetry_manager()
    try:
        repo = get_repository()
        cfg = repo.get_config().system.telemetry
        export_cfg = cfg.export if cfg else None
        return TelemetryCollector(telemetry_manager=mgr, export_config=export_cfg)
    except Exception:
        return TelemetryCollector(telemetry_manager=mgr)


@router.get("/health")
def get_telemetry_health(mgr: TelemetryManager = Depends(get_telemetry_manager)) -> Dict[str, Any]:
    """Returns the operational status and connectivity to the local VictoriaMetrics engine."""
    healthy = mgr.is_healthy()
    available = mgr.is_binary_available()
    return {
        "healthy": healthy,
        "binary_installed": available,
        "base_url": mgr.base_url,
    }


@router.get("/query")
def query_instant(
    query: str = Query(..., description="PromQL expression to evaluate"),
    time: Optional[float] = Query(None, description="Evaluation timestamp"),
    mgr: TelemetryManager = Depends(get_telemetry_manager),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    """Evaluates an instant PromQL metric expression."""
    res = mgr.query_instant(query, timestamp=time)
    if res.get("status") == "error":
        raise HTTPException(status_code=502, detail=res.get("error", "Error querying metrics"))
    return res


@router.get("/query_range")
def query_range(
    query: str = Query(..., description="PromQL expression to evaluate"),
    start: float = Query(..., description="Start epoch timestamp"),
    end: float = Query(..., description="End epoch timestamp"),
    step: str = Query("15s", description="Query resolution step (e.g. 15s, 1m)"),
    mgr: TelemetryManager = Depends(get_telemetry_manager),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    """Evaluates a PromQL expression over a time range for plotting charts."""
    res = mgr.query_range(query, start=start, end=end, step=step)
    if res.get("status") == "error":
        raise HTTPException(status_code=502, detail=res.get("error", "Error querying range metrics"))
    return res


@router.post("/collect")
def trigger_collection(
    collector: TelemetryCollector = Depends(get_telemetry_collector),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    """Triggers an on-demand metrics collection and push cycle."""
    success, count = collector.collect_and_push()
    return {"success": success, "samples_collected": count}
