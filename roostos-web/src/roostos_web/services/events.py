import json
import asyncio
from typing import Set, Dict, Any, AsyncGenerator


class EventPublisher:
    """Manages Server-Sent Events (SSE) broadcast queues for connected Web UI clients."""

    def __init__(self) -> None:
        self._listeners: Set[asyncio.Queue] = set()

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribes an active HTTP connection to the event broadcast stream."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._listeners.add(queue)
        try:
            # Yield initial connection heartbeat
            yield f"event: ping\ndata: {json.dumps({'status': 'connected'})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield message
                except (asyncio.TimeoutError, TimeoutError):
                    yield f"event: ping\ndata: {json.dumps({'status': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self._listeners.discard(queue)

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publishes an event to all connected subscriber queues."""
        formatted_sse = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        for queue in list(self._listeners):
            try:
                queue.put_nowait(formatted_sse)
            except asyncio.QueueFull:
                self._listeners.discard(queue)

    def setup_dbus_listeners(self, dbus_client: Any) -> None:
        """Attaches D-Bus signal observers from RoostClient to the event publisher."""
        try:
            dbus_client.on_device_connected(
                lambda mac, ip, host: self.publish("device_connected", {"mac": mac, "ip": ip, "hostname": host})
            )
            dbus_client.on_unknown_device_discovered(
                lambda mac, ip, host: self.publish("unknown_device", {"mac": mac, "ip": ip, "hostname": host})
            )
            dbus_client.on_bypass_expired(
                lambda mac: self.publish("bypass_expired", {"mac": mac})
            )
            dbus_client.on_upnp_request_received(
                lambda mac, port, proto, desc: self.publish(
                    "upnp_request", {"mac": mac, "port": port, "protocol": proto, "description": desc}
                )
            )
            dbus_client.on_upnp_queue_cleared(
                lambda: self.publish("upnp_cleared", {})
            )
            dbus_client.on_devices_updated(
                lambda: self.publish("devices_updated", {})
            )
            dbus_client.on_schedules_updated(
                lambda: self.publish("schedules_updated", {})
            )
            print("D-Bus event listeners connected to SSE publisher successfully.")
        except Exception as e:
            print(f"Notice: D-Bus event listeners could not be attached: {e}")


# Singleton instance
event_publisher = EventPublisher()
