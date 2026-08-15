import json
from typing import List, Dict, Any, Callable, Optional
from dbus_next.aio import MessageBus
from dbus_next import BusType

BUS_NAME = "org.roostos.Daemon"
OBJECT_PATH = "/org/roostos/Daemon"

class RoostClient:
    """Python client wrapper to interact with the RoostOS daemon over D-Bus."""
    
    def __init__(self, session: bool = False):
        self.session = session
        self._bus: Optional[MessageBus] = None
        self._interface: Optional[Any] = None

    async def connect(self) -> None:
        """Establishes connection to the D-Bus system or session bus and retrieves proxy interface."""
        bus_type = BusType.SESSION if self.session else BusType.SYSTEM
        self._bus = await MessageBus(bus_type=bus_type).connect()
        
        # Introspect path and fetch the org.roostos.Daemon interface
        introspection = await self._bus.introspect(BUS_NAME, OBJECT_PATH)
        proxy_object = self._bus.get_proxy_object(BUS_NAME, OBJECT_PATH, introspection)
        self._interface = proxy_object.get_interface(BUS_NAME)

    def disconnect(self) -> None:
        """Safely disconnects from the D-Bus bus."""
        if self._bus:
            self._bus.disconnect()
            self._bus = None
            self._interface = None

    # ==========================================
    # Daemon Configuration & CRUD Methods
    # ==========================================

    async def get_config(self) -> Dict[str, Any]:
        """Returns the compiled unified RoostConfig dictionary."""
        res = await self._interface.call_get_config()
        return json.loads(res)

    async def extract_plugin_ui(self, image_name: str, ui_entrypoint: str, plugin_id: str) -> None:
        """Invokes D-Bus ExtractPluginUI to pull and extract static UI assets."""
        await self._interface.call_extract_plugin_ui(image_name, ui_entrypoint, plugin_id)

    async def get_users(self) -> List[Dict[str, Any]]:
        """Returns list of Web login users."""
        res = await self._interface.call_get_users()
        return json.loads(res)

    async def get_people(self) -> List[Dict[str, Any]]:
        """Returns list of person family profiles."""
        res = await self._interface.call_get_people()
        return json.loads(res)

    async def get_buildings(self) -> List[Dict[str, Any]]:
        """Returns list of buildings."""
        res = await self._interface.call_get_buildings()
        return json.loads(res)

    async def get_rooms(self) -> List[Dict[str, Any]]:
        """Returns list of rooms."""
        res = await self._interface.call_get_rooms()
        return json.loads(res)

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Returns list of registered device profiles."""
        res = await self._interface.call_get_devices()
        return json.loads(res)

    async def get_active_leases(self) -> List[Dict[str, Any]]:
        """Returns active DHCP leases logged in the cache."""
        res = await self._interface.call_get_active_leases()
        return json.loads(res)

    async def get_schedules(self) -> Dict[str, Any]:
        """Returns firewall schedules and port forwards settings."""
        res = await self._interface.call_get_schedules()
        return json.loads(res)

    async def get_firewall_rules(self) -> List[Dict[str, Any]]:
        """Returns list of configured firewall input rules."""
        res = await self._interface.call_get_firewall_rules()
        return json.loads(res)

    async def update_firewall_rule(
        self,
        name: str,
        interface: str = "*",
        protocol: str = "tcp",
        port: int = 0,
        source: str = "",
        action: str = "accept",
        enabled: bool = True
    ) -> bool:
        """Creates or updates a firewall input rule by name."""
        return await self._interface.call_update_firewall_rule(
            name, interface, protocol, port, source, action, enabled
        )

    async def delete_firewall_rule(self, name: str) -> bool:
        """Deletes a firewall input rule by name."""
        return await self._interface.call_delete_firewall_rule(name)

    async def update_device(
        self,
        mac: str,
        name: str,
        owner_id: str = "",
        location_id: str = "",
        tags: Optional[List[str]] = None,
        static_ip: str = "",
        upnp_trusted: bool = False,
        upnp_allowed_ports: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Creates or updates a device profile in devices.yaml."""
        tags = tags or []
        allowed_ports_json = json.dumps(upnp_allowed_ports or [])
        return await self._interface.call_update_device(
            mac, name, owner_id, location_id, tags, static_ip, upnp_trusted, allowed_ports_json
        )

    async def delete_device(self, mac: str) -> bool:
        """Removes a registered device profile by MAC address."""
        return await self._interface.call_delete_device(mac)

    async def register_lease(self, mac: str, ip: str, hostname: str) -> bool:
        """Registers an active DHCP client lease in the transient cache."""
        return await self._interface.call_register_lease(mac, ip, hostname)

    async def release_lease(self, mac: str) -> bool:
        """Releases a DHCP client lease from the transient cache."""
        return await self._interface.call_release_lease(mac)

    # ==========================================
    # System Operations
    # ==========================================

    async def get_reboot_required(self) -> bool:
        """Checks if a reboot is pending on the host OS."""
        return await self._interface.get_reboot_required()

    async def grant_time_extension(self, mac: str, duration_seconds: int) -> bool:
        """Grants temporary schedule bypass extension to a client MAC."""
        return await self._interface.call_grant_time_extension(mac, duration_seconds)

    async def remove_time_extension(self, mac: str) -> bool:
        """Revokes active schedule bypass extension from a client MAC."""
        return await self._interface.call_remove_time_extension(mac)

    async def create_backup(self, passphrase: str) -> str:
        """Creates a passphrase-encrypted configurations backup bundle and returns its path."""
        return await self._interface.call_create_backup(passphrase)

    async def restore_backup(self, backup_path: str, passphrase: str) -> bool:
        """Restores configurations from an encrypted backup bundle path."""
        return await self._interface.call_restore_backup(backup_path, passphrase)

    async def reboot_host(self) -> bool:
        """Commands the host OS to issue a system reboot."""
        return await self._interface.call_reboot_host()

    # ==========================================
    # Certificate Management Operations
    # ==========================================

    async def get_certificate_status(self) -> Dict[str, Any]:
        """Returns status of Root CA, server cert, services, and plugins."""
        res = await self._interface.call_get_certificate_status()
        return json.loads(res)

    async def issue_plugin_certificate(self, plugin_id: str, scopes: List[str]) -> Dict[str, str]:
        """Issues an mTLS client certificate for a plugin container."""
        res = await self._interface.call_issue_plugin_certificate(plugin_id, json.dumps(scopes))
        return json.loads(res)

    async def issue_service_certificate(self, service_name: str, scopes: List[str]) -> Dict[str, str]:
        """Issues an mTLS client certificate for an internal service."""
        res = await self._interface.call_issue_service_certificate(service_name, json.dumps(scopes))
        return json.loads(res)

    async def verify_certificate(self, cert_pem: str) -> Dict[str, Any]:
        """Verifies a certificate against the Root CA."""
        res = await self._interface.call_verify_certificate(cert_pem)
        return json.loads(res)

    async def renew_server_certificate(self) -> Dict[str, Any]:
        """Renews the HTTPS server TLS certificate."""
        res = await self._interface.call_renew_server_certificate()
        return json.loads(res)

    async def exchange_cert_for_token(self, api_url: str, cert_pem: str) -> Dict[str, Any]:
        """Exchanges an X.509 client certificate for a scoped OAuth Bearer JWT."""
        import httpx
        url = f"{api_url.rstrip('/')}/oauth/token"
        data = {
            "grant_type": "client_certificate",
            "client_certificate": cert_pem
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data, timeout=10.0)
            resp.raise_for_status()
            return resp.json()

    # ==========================================
    # UPnP Gateway Operations
    # ==========================================

    async def get_pending_upnp_requests(self) -> List[Dict[str, Any]]:
        """Returns lists of pending UPnP port mappings awaiting staging reviews."""
        res = await self._interface.call_get_pending_u_pn_p_requests()
        return json.loads(res)

    async def approve_upnp_request(
        self, mac: str, port: int, protocol: str, remember: bool, trust_device: bool
    ) -> bool:
        """Approves a staged UPnP request, optionally saving port mappings or trusting device."""
        return await self._interface.call_approve_u_pn_p_request(
            mac, port, protocol, remember, trust_device
        )

    async def reject_upnp_request(self, mac: str, port: int, protocol: str) -> bool:
        """Rejects and cleans up a staged UPnP request."""
        return await self._interface.call_reject_u_pn_p_request(mac, port, protocol)

    async def register_upnp_request(
        self, mac: str, internal_ip: str, port: int, internal_port: int, protocol: str, description: str = ""
    ) -> bool:
        """Registers a staged UPnP request. Returns True if pre-approved/instantly trusted."""
        return await self._interface.call_register_u_pn_p_request(
            mac, internal_ip, port, internal_port, protocol, description
        )

    # ==========================================
    # Signal Observers
    # ==========================================

    def on_users_updated(self, callback: Callable[[], None]) -> None:
        """Subscribes callback to UsersUpdated signal."""
        self._interface.on_users_updated(callback)

    def on_people_updated(self, callback: Callable[[], None]) -> None:
        """Subscribes callback to PeopleUpdated signal."""
        self._interface.on_people_updated(callback)

    def on_locations_updated(self, callback: Callable[[], None]) -> None:
        """Subscribes callback to LocationsUpdated signal."""
        self._interface.on_locations_updated(callback)

    def on_devices_updated(self, callback: Callable[[], None]) -> None:
        """Subscribes callback to DevicesUpdated signal."""
        self._interface.on_devices_updated(callback)

    def on_schedules_updated(self, callback: Callable[[], None]) -> None:
        """Subscribes callback to SchedulesUpdated signal."""
        self._interface.on_schedules_updated(callback)

    def on_device_connected(self, callback: Callable[[str, str, str], None]) -> None:
        """Subscribes callback to DeviceConnected(mac, ip, hostname) lease signals."""
        def wrapper(payload: str):
            parts = payload.split(",")
            if len(parts) == 3:
                callback(parts[0], parts[1], parts[2])
            else:
                callback(payload, "", "")
        self._interface.on_device_connected(wrapper)

    def on_unknown_device_discovered(self, callback: Callable[[str, str, str], None]) -> None:
        """Subscribes callback to UnknownDeviceDiscovered(mac, ip, hostname) signals."""
        def wrapper(payload: str):
            parts = payload.split(",")
            if len(parts) == 3:
                callback(parts[0], parts[1], parts[2])
            else:
                callback(payload, "", "")
        self._interface.on_unknown_device_discovered(wrapper)

    def on_bypass_expired(self, callback: Callable[[str], None]) -> None:
        """Subscribes callback to BypassExpired(mac) signals."""
        self._interface.on_bypass_expired(callback)

    def on_upnp_request_received(self, callback: Callable[[str, int, str, str], None]) -> None:
        """Subscribes callback to UPnPRequestReceived(mac, port, protocol, description) signals."""
        def wrapper(payload: str):
            parts = payload.split(",")
            if len(parts) >= 3:
                mac = parts[0]
                port = int(parts[1])
                proto = parts[2]
                desc = parts[3] if len(parts) > 3 else ""
                callback(mac, port, proto, desc)
            else:
                callback(payload, 0, "", "")
        self._interface.on_upnp_request_received(wrapper)

    def on_upnp_queue_cleared(self, callback: Callable[[], None]) -> None:
        """Subscribes callback to UPnPQueueCleared signal."""
        self._interface.on_upnp_queue_cleared(callback)
