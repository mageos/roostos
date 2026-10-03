"""Centralized alerting engine and metric threshold evaluator for RoostOS."""

import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from roostos_engine.telemetry_manager import TelemetryManager
from roostos_engine.notifications import NotificationDispatcher, NotificationPayload


class AlertRule(BaseModel):
    """Defines a threshold condition to monitor across nodes."""
    id: str
    name: str
    query: str
    op: str = ">"  # ">", ">=", "<", "<=", "=="
    threshold: float
    severity: str = "warning"  # "info", "warning", "critical"
    description_template: str = "{name} triggered with value {value} on {node}"


class ActiveAlert(BaseModel):
    """Represents a live or recently resolved alert event."""
    id: str
    rule_id: str
    title: str
    message: str
    severity: str
    node_id: str
    state: str = "firing"  # "firing" or "resolved"
    value: float
    fired_at: str
    resolved_at: Optional[str] = None
    acknowledged: bool = False


DEFAULT_ALERT_RULES: List[AlertRule] = [
    AlertRule(
        id="disk_critical",
        name="Disk Usage Critical",
        query="system_disk_usage_percent",
        op=">",
        threshold=90.0,
        severity="critical",
        description_template="Disk usage critical ({value}%) on node {node}",
    ),
    AlertRule(
        id="disk_warning",
        name="Disk Usage High",
        query="system_disk_usage_percent",
        op=">",
        threshold=80.0,
        severity="warning",
        description_template="Disk usage high ({value}%) on node {node}",
    ),
    AlertRule(
        id="memory_critical",
        name="Memory Pressure Critical",
        query="system_memory_usage_percent",
        op=">",
        threshold=95.0,
        severity="critical",
        description_template="Memory usage critical ({value}%) on node {node}",
    ),
    AlertRule(
        id="cpu_high",
        name="CPU Load Sustained",
        query="system_cpu_load_5m",
        op=">",
        threshold=90.0,
        severity="warning",
        description_template="Sustained high CPU load ({value}) on node {node}",
    ),
    AlertRule(
        id="firewall_quarantine",
        name="Device Quarantined",
        query="roostos_firewall_quarantined_devices",
        op=">",
        threshold=0.0,
        severity="warning",
        description_template="Unregistered device(s) quarantined ({value}) on node {node}",
    ),
]


def compare_value(val: float, op: str, threshold: float) -> bool:
    """Evaluates comparison operator against numeric threshold."""
    if op == ">":
        return val > threshold
    elif op == ">=":
        return val >= threshold
    elif op == "<":
        return val < threshold
    elif op == "<=":
        return val <= threshold
    elif op == "==":
        return val == threshold
    return False


class AlertManager:
    """Evaluates metrics against alert rules, manages alert states, and dispatches notifications."""

    def __init__(
        self,
        telemetry_manager: Optional[TelemetryManager] = None,
        dispatcher: Optional[NotificationDispatcher] = None,
        custom_rules: Optional[List[AlertRule]] = None,
    ) -> None:
        self.telemetry_manager = telemetry_manager or TelemetryManager()
        self.dispatcher = dispatcher or NotificationDispatcher()
        self.rules: List[AlertRule] = custom_rules or list(DEFAULT_ALERT_RULES)
        self.active_alerts: Dict[str, ActiveAlert] = {}
        self.history: List[ActiveAlert] = []

    def evaluate_rules(self) -> List[ActiveAlert]:
        """Queries VictoriaMetrics and evaluates all alert rules across all nodes."""
        current_firing_keys = set()
        new_alerts: List[ActiveAlert] = []
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for rule in self.rules:
            res = self.telemetry_manager.query_instant(rule.query)
            if res.get("status") != "success":
                continue

            results = res.get("data", {}).get("result", [])
            for item in results:
                metric_val_str = item.get("value", [0, "0"])[1]
                try:
                    val = float(metric_val_str)
                except (ValueError, TypeError):
                    continue

                metric_labels = item.get("metric", {})
                node = metric_labels.get("node", "node-01")
                alert_key = f"{rule.id}:{node}"

                if compare_value(val, rule.op, rule.threshold):
                    current_firing_keys.add(alert_key)
                    if alert_key not in self.active_alerts:
                        msg = rule.description_template.format(name=rule.name, value=val, node=node)
                        alert = ActiveAlert(
                            id=alert_key,
                            rule_id=rule.id,
                            title=rule.name,
                            message=msg,
                            severity=rule.severity,
                            node_id=node,
                            state="firing",
                            value=val,
                            fired_at=now_iso,
                        )
                        self.active_alerts[alert_key] = alert
                        self.history.insert(0, alert)
                        new_alerts.append(alert)

                        payload = NotificationPayload(
                            alert_id=alert_key,
                            rule_id=rule.id,
                            title=rule.name,
                            message=msg,
                            severity=rule.severity,
                            state="firing",
                            node_id=node,
                            value=val,
                            timestamp=now_iso,
                        )
                        self.dispatcher.dispatch(payload)

        # Check for resolved alerts
        resolved_keys = [k for k in self.active_alerts if k not in current_firing_keys]
        for key in resolved_keys:
            alert = self.active_alerts.pop(key)
            alert.state = "resolved"
            alert.resolved_at = now_iso

            payload = NotificationPayload(
                alert_id=alert.id,
                rule_id=alert.rule_id,
                title=f"Resolved: {alert.title}",
                message=f"Alert resolved on node {alert.node_id}",
                severity=alert.severity,
                state="resolved",
                node_id=alert.node_id,
                value=alert.value,
                timestamp=now_iso,
            )
            self.dispatcher.dispatch(payload)

        return new_alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Marks an active alert as acknowledged by an administrator."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            return True
        for h in self.history:
            if h.id == alert_id:
                h.acknowledged = True
                return True
        return False

    def get_active_alerts(self) -> List[ActiveAlert]:
        """Returns list of currently firing alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(self, limit: int = 50) -> List[ActiveAlert]:
        """Returns recent alert history."""
        return self.history[:limit]
