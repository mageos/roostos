"""Unit tests for RoostOS AlertManager and NotificationDispatcher."""

import json
import urllib.request
from unittest.mock import patch, MagicMock
import pytest

from roostos_engine.models.system import NotificationsConfig, NotificationChannelConfig
from roostos_engine.notifications import NotificationDispatcher, NotificationPayload
from roostos_engine.telemetry_manager import TelemetryManager
from roostos_engine.alert_manager import AlertManager, AlertRule, ActiveAlert


def test_notification_dispatcher_filtering():
    cfg = NotificationsConfig(
        enabled=True,
        channels=[
            NotificationChannelConfig(
                id="webhook-1",
                name="Ops Webhook",
                type="webhook",
                url="https://hooks.example.com/alerts",
                min_severity="warning",
            )
        ]
    )
    dispatcher = NotificationDispatcher(config=cfg)

    # Info alert should be dropped
    info_payload = NotificationPayload(
        alert_id="test:1",
        rule_id="test",
        title="Info Test",
        message="Just info",
        severity="info",
    )
    assert dispatcher.dispatch(info_payload) == 0

    # Warning alert should be sent
    warn_payload = NotificationPayload(
        alert_id="test:2",
        rule_id="test",
        title="Disk Warning",
        message="Disk usage high",
        severity="warning",
    )
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        assert dispatcher.dispatch(warn_payload) == 1
        assert mock_urlopen.call_count == 1


def test_notification_dispatcher_ntfy():
    cfg = NotificationsConfig(
        enabled=True,
        channels=[
            NotificationChannelConfig(
                id="ntfy-1",
                name="My Ntfy",
                type="ntfy",
                url="https://ntfy.sh/roostos-alerts",
                min_severity="info",
            )
        ]
    )
    dispatcher = NotificationDispatcher(config=cfg)
    payload = NotificationPayload(
        alert_id="test:crit",
        rule_id="test",
        title="Critical Alert",
        message="Server on fire",
        severity="critical",
        node_id="gateway",
    )

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        count = dispatcher.dispatch(payload)
        assert count == 1

        req: urllib.request.Request = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "https://ntfy.sh/roostos-alerts"
        assert req.headers.get("Priority") == "5"
        assert req.headers.get("Title") == "Critical Alert"


def test_alert_manager_evaluation_lifecycle():
    mock_vm = MagicMock(spec=TelemetryManager)
    mock_dispatcher = MagicMock(spec=NotificationDispatcher)

    disk_val = 92.5

    def fake_query(query, *args, **kwargs):
        if query == "system_disk_usage_percent":
            return {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {"__name__": "system_disk_usage_percent", "node": "node-01"},
                            "value": [1700000000, str(disk_val)],
                        }
                    ]
                }
            }
        return {"status": "success", "data": {"resultType": "vector", "result": []}}

    mock_vm.query_instant.side_effect = fake_query
    mgr = AlertManager(telemetry_manager=mock_vm, dispatcher=mock_dispatcher)

    # First evaluation: alert fires (disk_critical > 90 and disk_warning > 80)
    new_alerts = mgr.evaluate_rules()
    assert len(new_alerts) == 2
    assert len(mgr.get_active_alerts()) == 2
    assert mock_dispatcher.dispatch.call_count == 2

    # Second evaluation with same metrics: no new alerts (deduplication)
    new_alerts_2 = mgr.evaluate_rules()
    assert len(new_alerts_2) == 0
    assert len(mgr.get_active_alerts()) == 2
    assert mock_dispatcher.dispatch.call_count == 2  # Not called again

    # Third evaluation: disk usage drops to normal (45%)
    disk_val = 45.0
    new_alerts_3 = mgr.evaluate_rules()
    assert len(new_alerts_3) == 0
    assert len(mgr.get_active_alerts()) == 0  # Both resolved
    # Dispatcher should be notified of resolution (2 firing + 2 resolved = 4)
    assert mock_dispatcher.dispatch.call_count == 4


def test_alert_manager_acknowledgment():
    mock_vm = MagicMock(spec=TelemetryManager)
    mock_vm.query_instant.return_value = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"__name__": "system_disk_usage_percent", "node": "node-01"},
                    "value": [1700000000, "95.0"],
                }
            ]
        }
    }
    mgr = AlertManager(telemetry_manager=mock_vm)
    mgr.evaluate_rules()

    active = mgr.get_active_alerts()
    assert len(active) > 0
    alert_id = active[0].id
    assert active[0].acknowledged is False

    success = mgr.acknowledge_alert(alert_id)
    assert success is True
    assert mgr.active_alerts[alert_id].acknowledged is True
