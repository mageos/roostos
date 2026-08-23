import pytest
from roostos_web.services.events import event_publisher


@pytest.mark.asyncio
async def test_event_publisher_subscription():
    """Verifies that subscribing to EventPublisher yields initial ping and published events."""
    publisher = event_publisher
    stream = publisher.subscribe()
    
    # First message should be the initial ping
    first_msg = await anext(stream)
    assert "event: ping" in first_msg
    assert "connected" in first_msg

    # Publish an event and verify subscriber receives it
    publisher.publish("test_event", {"hello": "world"})
    second_msg = await anext(stream)
    assert "event: test_event" in second_msg
    assert '"hello": "world"' in second_msg

    # Close stream
    await stream.aclose()


def test_event_publisher_setup_listeners():
    """Verifies D-Bus listener registration helper doesn't fail on mock client."""
    class MockDBusClient:
        def on_device_connected(self, cb): pass
        def on_unknown_device_discovered(self, cb): pass
        def on_bypass_expired(self, cb): pass
        def on_upnp_request_received(self, cb): pass
        def on_upnp_queue_cleared(self, cb): pass
        def on_devices_updated(self, cb): pass
        def on_schedules_updated(self, cb): pass

    publisher = event_publisher
    publisher.setup_dbus_listeners(MockDBusClient())
