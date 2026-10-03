"""FastAPI router for managing alert states, rules, and incident notifications."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException

from roostos_engine.telemetry_manager import TelemetryManager
from roostos_engine.notifications import NotificationDispatcher
from roostos_engine.alert_manager import AlertManager, ActiveAlert, AlertRule
from roostos_web.auth import get_current_user, get_current_admin
from roostos_web.services.base import get_repository
from roostos_web.services.events import event_publisher

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Provides a singleton AlertManager wired with repository config and SSE event publisher."""
    global _alert_manager_instance
    if _alert_manager_instance is None:
        try:
            repo = get_repository()
            sys_cfg = repo.get_config().system
            telemetry_mgr = TelemetryManager(config=sys_cfg.telemetry)
            dispatcher = NotificationDispatcher(
                config=sys_cfg.notifications,
                event_callback=lambda evt, data: event_publisher.publish(evt, data),
            )
            _alert_manager_instance = AlertManager(telemetry_manager=telemetry_mgr, dispatcher=dispatcher)
        except Exception:
            _alert_manager_instance = AlertManager()
    return _alert_manager_instance


def set_alert_manager(manager: AlertManager) -> None:
    """Overrides the AlertManager instance for testing purposes."""
    global _alert_manager_instance
    _alert_manager_instance = manager


@router.get("/active", response_model=List[ActiveAlert])
def get_active_alerts(
    mgr: AlertManager = Depends(get_alert_manager),
    _=Depends(get_current_user),
) -> List[ActiveAlert]:
    """Returns all currently firing alerts across the cluster."""
    return mgr.get_active_alerts()


@router.get("/history", response_model=List[ActiveAlert])
def get_alert_history(
    limit: int = 50,
    mgr: AlertManager = Depends(get_alert_manager),
    _=Depends(get_current_user),
) -> List[ActiveAlert]:
    """Returns recent alert history (firing and resolved)."""
    return mgr.get_alert_history(limit=limit)


@router.get("/rules", response_model=List[AlertRule])
def get_alert_rules(
    mgr: AlertManager = Depends(get_alert_manager),
    _=Depends(get_current_user),
) -> List[AlertRule]:
    """Returns the configured metric threshold rules."""
    return mgr.rules


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    mgr: AlertManager = Depends(get_alert_manager),
    _=Depends(get_current_user),
) -> Dict[str, Any]:
    """Acknowledges an active or historical alert."""
    success = mgr.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return {"success": True, "alert_id": alert_id}


@router.post("/evaluate", response_model=List[ActiveAlert])
def evaluate_alerts(
    mgr: AlertManager = Depends(get_alert_manager),
    _=Depends(get_current_user),
) -> List[ActiveAlert]:
    """Manually evaluates alert rules against current metrics and dispatches notifications."""
    return mgr.evaluate_rules()
