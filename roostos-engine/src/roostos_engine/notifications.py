"""Outbound notification dispatcher for alerts and security events."""

import json
import urllib.request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from roostos_engine.models.system import NotificationsConfig, NotificationChannelConfig


SEVERITY_LEVELS = {
    "info": 1,
    "warning": 2,
    "critical": 3,
}

NTFY_PRIORITIES = {
    "info": "2",
    "warning": "4",
    "critical": "5",
}

DISCORD_COLORS = {
    "info": 3447003,      # Blue
    "warning": 16776960,  # Yellow
    "critical": 15158332, # Red
}


class NotificationPayload(BaseModel):
    """Normalized alert notification payload."""
    alert_id: str
    rule_id: str
    title: str
    message: str
    severity: str = "warning"
    state: str = "firing"  # "firing" or "resolved"
    node_id: str = "node-01"
    value: float = 0.0
    timestamp: str = ""


class NotificationDispatcher:
    """Dispatches alerts to configured channels (Webhooks, ntfy.sh, Discord, Slack)."""

    def __init__(
        self,
        config: Optional[NotificationsConfig] = None,
        event_callback: Optional[Any] = None,
    ) -> None:
        self.config = config or NotificationsConfig()
        self.event_callback = event_callback

    def should_notify(self, channel: NotificationChannelConfig, severity: str) -> bool:
        """Determines if the alert severity meets the channel's minimum threshold."""
        if not channel.enabled:
            return False
        channel_min = SEVERITY_LEVELS.get(channel.min_severity.lower(), 2)
        alert_lvl = SEVERITY_LEVELS.get(severity.lower(), 2)
        return alert_lvl >= channel_min

    def dispatch(self, payload: NotificationPayload) -> int:
        """Sends the notification payload to all eligible channels."""
        if self.event_callback:
            try:
                self.event_callback("alert", payload.model_dump())
            except Exception:
                pass

        if not self.config.enabled:
            return 0

        dispatched_count = 0
        for channel in self.config.channels:
            if not self.should_notify(channel, payload.severity):
                continue

            success = self._send_to_channel(channel, payload)
            if success:
                dispatched_count += 1

        return dispatched_count

    def _send_to_channel(self, channel: NotificationChannelConfig, payload: NotificationPayload) -> bool:
        """Formats and posts notification payload according to channel type."""
        try:
            ch_type = channel.type.lower()
            if ch_type == "ntfy":
                return self._send_ntfy(channel, payload)
            elif ch_type == "discord":
                return self._send_discord(channel, payload)
            elif ch_type == "slack":
                return self._send_slack(channel, payload)
            else:
                return self._send_webhook(channel, payload)
        except Exception:
            return False

    def _send_webhook(self, channel: NotificationChannelConfig, payload: NotificationPayload) -> bool:
        data = json.dumps(payload.model_dump()).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if channel.auth_token:
            headers["Authorization"] = f"Bearer {channel.auth_token}"
        req = urllib.request.Request(channel.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status in (200, 201, 202, 204)

    def _send_ntfy(self, channel: NotificationChannelConfig, payload: NotificationPayload) -> bool:
        data = f"[{payload.state.upper()}] {payload.message}\nNode: {payload.node_id}".encode("utf-8")
        headers = {
            "Title": payload.title,
            "Priority": NTFY_PRIORITIES.get(payload.severity.lower(), "3"),
            "Tags": f"roostos,{payload.severity}",
        }
        if channel.auth_token:
            headers["Authorization"] = f"Bearer {channel.auth_token}"
        req = urllib.request.Request(channel.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status in (200, 201, 202, 204)

    def _send_discord(self, channel: NotificationChannelConfig, payload: NotificationPayload) -> bool:
        discord_body = {
            "embeds": [
                {
                    "title": f"[{payload.state.upper()}] {payload.title}",
                    "description": payload.message,
                    "color": DISCORD_COLORS.get(payload.severity.lower(), 16776960),
                    "fields": [
                        {"name": "Severity", "value": payload.severity.upper(), "inline": True},
                        {"name": "Node", "value": payload.node_id, "inline": True},
                    ],
                }
            ]
        }
        data = json.dumps(discord_body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(channel.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status in (200, 204)

    def _send_slack(self, channel: NotificationChannelConfig, payload: NotificationPayload) -> bool:
        slack_body = {
            "text": f"*[{payload.state.upper()}] {payload.title}*\n{payload.message}\n*Node:* `{payload.node_id}` | *Severity:* `{payload.severity}`"
        }
        data = json.dumps(slack_body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(channel.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status in (200, 204)
