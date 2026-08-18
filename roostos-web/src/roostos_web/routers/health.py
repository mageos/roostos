from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query

from roostos_sdk.client import RoostClient
from roostos_engine.repository import ConfigRepository
from roostos_engine.health import HealthChecker
from roostos_web.di import Injected


router = APIRouter(tags=["health"])


@router.get("/api/health")
async def get_node_health(
    check_mqtt: bool = Query(False, description="Whether to trigger an active MQTT broadcast ping health check"),
    dbus: RoostClient = Injected(RoostClient),
    repo: ConfigRepository = Injected(ConfigRepository),
):
    """Returns standardized node diagnostic health report, subsystem statuses, resource telemetry, and MQTT bus health."""
    try:
        return await dbus.get_node_health(check_mqtt=check_mqtt)
    except Exception:
        # Fallback to local health checker
        config = repo.get_config()
        node_id = "node-01"
        if config.system and config.system.cluster and config.system.cluster.node_id:
            node_id = config.system.cluster.node_id

        current_node = next((n for n in config.nodes if n.id == node_id), None)
        roles = [r.value if hasattr(r, "value") else str(r) for r in (current_node.roles if current_node else [])] or ["gateway_router"]
        node_name = current_node.name if current_node else config.system.hostname

        checker = HealthChecker(config_dir=getattr(repo, "config_dir", "/etc/roostos"), mock=True)
        report = checker.collect_health_report(
            node_id=node_id,
            node_name=node_name,
            roles=roles,
            dbus_connected=False,
            check_mqtt=check_mqtt,
        )
        return report.model_dump()
