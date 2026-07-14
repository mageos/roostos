import asyncio
from typing import List
from dbus_next.service import ServiceInterface, method
from dbus_next.aio import MessageBus
from dbus_next import BusType

BUS_NAME = "org.roostos.DNSResolver"
OBJECT_PATH = "/org/roostos/DNSResolver"

class DNSResolverServer(ServiceInterface):
    """Base class for implementing the org.roostos.DNSResolver D-Bus service.
    
    Plugin developers can inherit from this class and override the hook methods
    (e.g., set_client_dns_profile) without managing raw D-Bus Next decorators or loops.
    """
    
    def __init__(self):
        super().__init__(BUS_NAME)
        self._bus = None

    # ==========================================
    # Decorated D-Bus Endpoint Methods
    # ==========================================

    @method()
    async def SetClientDNSProfile(self, mac: 's', profile_name: 's') -> 'b':
        """D-Bus Method to bind a client MAC address to a filter profile."""
        return await self.set_client_dns_profile(mac, profile_name)

    @method()
    async def ClearClientDNSProfile(self, mac: 's') -> 'b':
        """D-Bus Method to clear custom DNS profile mappings for a client MAC."""
        return await self.clear_client_dns_profile(mac)

    @method()
    async def SetGlobalForwarders(self, forwarders: 'as') -> 'b':
        """D-Bus Method to update upstream global forwarders."""
        return await self.set_global_forwarders(forwarders)

    @method()
    async def GetDNSProfiles(self) -> 's':
        """D-Bus Method returning a JSON list of active filtering profiles."""
        return await self.get_dns_profiles()

    @method()
    async def SetAdBlockingEnabled(self, enabled: 'b') -> 'b':
        """D-Bus Method to toggle ad-blocking filter list globally."""
        return await self.set_ad_blocking_enabled(enabled)

    # ==========================================
    # Hook Methods (Overridden by Subclasses)
    # ==========================================

    async def set_client_dns_profile(self, mac: str, profile_name: str) -> bool:
        """Override to implement client DNS profile bindings."""
        return False

    async def clear_client_dns_profile(self, mac: str) -> bool:
        """Override to clear client DNS profiles."""
        return False

    async def set_global_forwarders(self, forwarders: List[str]) -> bool:
        """Override to set global DNS forwarders."""
        return False

    async def get_dns_profiles(self) -> str:
        """Override to return available DNS profiles as a JSON string."""
        return "[]"

    async def set_ad_blocking_enabled(self, enabled: bool) -> bool:
        """Override to enable/disable ad-blocking globally."""
        return False

    # ==========================================
    # Lifecycle Control
    # ==========================================

    async def start(self, session: bool = False) -> None:
        """Connects to the D-Bus bus and exports the service interface."""
        bus_type = BusType.SESSION if session else BusType.SYSTEM
        self._bus = await MessageBus(bus_type=bus_type).connect()
        self._bus.export(OBJECT_PATH, self)
        await self._bus.request_name(BUS_NAME)
        print(f"DNS Resolver D-Bus service registered successfully: '{BUS_NAME}' at object path '{OBJECT_PATH}'")

    def stop(self) -> None:
        """Disconnects and releases the D-Bus service."""
        if self._bus:
            self._bus.disconnect()
            self._bus = None
            print("DNS Resolver D-Bus service stopped.")
        else:
            print("DNS Resolver D-Bus service was not running.")
