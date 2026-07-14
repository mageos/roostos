import json
import pytest
import asyncio
from typing import List
from roostos_sdk.client import RoostClient
from roostos_sdk.server import DNSResolverServer
from dbus_next.aio import MessageBus
from dbus_next import BusType

# ==========================================
# 1. Client Integration Tests
# ==========================================

@pytest.mark.asyncio
async def test_client_daemon_crud(dbus_session, running_daemon):
    """Verifies that RoostClient can successfully connect, query config, and perform CRUD operations."""
    client = RoostClient(session=True)
    await client.connect()

    try:
        # Verify get_config
        config = await client.get_config()
        assert config["system"]["hostname"] == "sdk-router"

        # Verify get_devices
        devices = await client.get_devices()
        assert len(devices) == 1
        assert devices[0]["mac"] == "a4:83:e7:12:34:56"

        # Verify update_device
        success = await client.update_device(
            mac="00:11:22:33:44:55",
            name="SDK Test client",
            owner_id="",
            location_id="",
            tags=["sdk", "test"],
            static_ip="192.168.1.99"
        )
        assert success is True

        # Verify list again
        devices = await client.get_devices()
        assert len(devices) == 2
        assert any(d["mac"] == "00:11:22:33:44:55" for d in devices)

        # Verify delete_device
        success = await client.delete_device("00:11:22:33:44:55")
        assert success is True

        # Verify removed
        devices = await client.get_devices()
        assert len(devices) == 1

    finally:
        client.disconnect()


@pytest.mark.asyncio
async def test_client_signals(dbus_session, running_daemon):
    """Verifies that client signal subscriptions trigger callbacks correctly when daemon state updates."""
    client = RoostClient(session=True)
    await client.connect()

    signal_received = asyncio.Event()

    def on_devices_updated_callback():
        signal_received.set()

    # Subscribe callback
    client.on_devices_updated(on_devices_updated_callback)

    try:
        # Trigger DevicesUpdated signal by registering a device
        await client.update_device(
            mac="aa:bb:cc:dd:ee:ff",
            name="Signal Test Device"
        )

        # Wait for the signal event to fire
        await asyncio.wait_for(signal_received.wait(), timeout=2.0)
        assert signal_received.is_set()

    finally:
        client.disconnect()


# ==========================================
# 2. Server Base Class Tests
# ==========================================

class MockDNSResolver(DNSResolverServer):
    """Test subclass implementing the standard org.roostos.DNSResolver hook methods."""
    
    def __init__(self):
        super().__init__()
        self.ad_blocking = False
        self.client_profiles = {}

    async def set_client_dns_profile(self, mac: str, profile_name: str) -> bool:
        self.client_profiles[mac] = profile_name
        return True

    async def clear_client_dns_profile(self, mac: str) -> bool:
        self.client_profiles.pop(mac, None)
        return True

    async def get_dns_profiles(self) -> str:
        return json.dumps(["Kids-Safe", "Standard", "Malware-Block"])

    async def set_ad_blocking_enabled(self, enabled: bool) -> bool:
        self.ad_blocking = enabled
        return True


@pytest.mark.asyncio
async def test_resolver_server_registration(dbus_session):
    """Verifies that DNSResolverServer exports to D-Bus and handles method calls correctly."""
    server = MockDNSResolver()
    await server.start(session=True)

    # Establish client bus and introspection
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        introspection = await bus.introspect("org.roostos.DNSResolver", "/org/roostos/DNSResolver")
        proxy = bus.get_proxy_object("org.roostos.DNSResolver", "/org/roostos/DNSResolver", introspection)
        interface = proxy.get_interface("org.roostos.DNSResolver")

        # 1. Test GetDNSProfiles
        profiles_json = await interface.call_get_dns_profiles()
        profiles = json.loads(profiles_json)
        assert "Kids-Safe" in profiles
        assert len(profiles) == 3

        # 2. Test SetAdBlockingEnabled
        assert server.ad_blocking is False
        success = await interface.call_set_ad_blocking_enabled(True)
        assert success is True
        assert server.ad_blocking is True

        # 3. Test SetClientDNSProfile
        assert "00:11:22:33:44:55" not in server.client_profiles
        success = await interface.call_set_client_dns_profile("00:11:22:33:44:55", "Kids-Safe")
        assert success is True
        assert server.client_profiles["00:11:22:33:44:55"] == "Kids-Safe"

    finally:
        bus.disconnect()
        server.stop()
