"""Mock implementation of RoostClient for isolated UI testing and local development without D-Bus."""

import time
from typing import List, Dict, Any, Callable, Optional
from roostos_sdk.client import RoostClient


class MockRoostClient(RoostClient):
    """In-memory RoostClient simulating daemon IPC for UI development and unit testing."""

    def __init__(
        self,
        initial_leases: Optional[List[Dict[str, Any]]] = None,
        initial_users: Optional[List[Dict[str, Any]]] = None,
        initial_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.session = True
        self._bus = None
        self._interface = None
        self._listeners: Dict[str, List[Callable]] = {
            "users_updated": [],
            "nodes_updated": [],
            "hardware_discovered": [],
            "people_updated": [],
            "locations_updated": [],
            "devices_updated": [],
            "schedules_updated": [],
            "device_connected": [],
            "unknown_device_discovered": [],
            "bypass_expired": [],
            "upnp_request_received": [],
            "upnp_queue_cleared": [],
        }

        self.active_leases: List[Dict[str, Any]] = initial_leases or [
            {
                "ip": "192.168.1.101",
                "mac": "dc:a6:32:11:22:33",
                "hostname": "Dads-MacBook-Pro",
                "network_interface": "br-lan",
                "vendor": "Apple, Inc.",
                "expires_in_seconds": 43200,
            },
            {
                "ip": "192.168.1.105",
                "mac": "f4:d4:88:44:55:66",
                "hostname": "Alices-iPad",
                "network_interface": "br-lan",
                "vendor": "Apple, Inc.",
                "expires_in_seconds": 38400,
            },
            {
                "ip": "192.168.20.15",
                "mac": "a0:b1:c2:d3:e4:f5",
                "hostname": "Guests-iPhone",
                "network_interface": "vlan-guest",
                "vendor": "Apple, Inc.",
                "expires_in_seconds": 7200,
            },
            {
                "ip": "192.168.40.10",
                "mac": "50:ec:50:aa:bb:cc",
                "hostname": "Nest-Front-Cam",
                "network_interface": "vlan-iot",
                "vendor": "Google LLC",
                "expires_in_seconds": 86400,
            },
        ]

        self.users: List[Dict[str, Any]] = initial_users or [
            {"username": "admin", "role": "admin", "person": "dad"},
            {"username": "mom", "role": "parent", "person": "mom"},
        ]

        self.nodes: List[Dict[str, Any]] = initial_nodes or [
            {"id": "roost-gateway-01", "name": "Roost Gateway 01", "role": "gateway", "ip": "192.168.1.1", "status": "online"},
            {"id": "roost-controller-01", "name": "Roost App Controller", "role": "worker", "ip": "192.168.1.2", "status": "online"},
        ]

        self.time_extensions: Dict[str, float] = {}
        self.reboot_required: bool = False
        self.pending_upnp: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        """No-op connection for mock client."""
        return None

    def disconnect(self) -> None:
        """No-op disconnection for mock client."""
        return None

    # ==========================================
    # Daemon Configuration & Mock CRUD
    # ==========================================

    async def get_config(self) -> Dict[str, Any]:
        return {"status": "ok", "mock": True}

    async def reload_config(self) -> bool:
        self.emit("devices_updated")
        return True

    async def get_users(self) -> List[Dict[str, Any]]:
        return list(self.users)

    async def get_active_leases(self) -> List[Dict[str, Any]]:
        return list(self.active_leases)

    async def register_lease(self, mac: str, ip: str, hostname: str) -> bool:
        norm_mac = mac.lower()
        lease = next((l for l in self.active_leases if l["mac"].lower() == norm_mac), None)
        if lease:
            lease["ip"] = ip
            lease["hostname"] = hostname
        else:
            self.active_leases.append({
                "ip": ip,
                "mac": norm_mac,
                "hostname": hostname,
                "network_interface": "br-lan",
                "vendor": "Simulated Device",
                "expires_in_seconds": 86400,
            })
        self.emit("device_connected", norm_mac, ip, hostname)
        return True

    async def release_lease(self, mac: str) -> bool:
        norm_mac = mac.lower()
        self.active_leases = [l for l in self.active_leases if l["mac"].lower() != norm_mac]
        return True

    async def grant_time_extension(self, mac: str, duration_seconds: int) -> bool:
        norm_mac = mac.lower()
        self.time_extensions[norm_mac] = time.time() + duration_seconds
        self.emit("devices_updated")
        return True

    async def remove_time_extension(self, mac: str) -> bool:
        norm_mac = mac.lower()
        self.time_extensions.pop(norm_mac, None)
        self.emit("bypass_expired", norm_mac)
        return True

    async def delete_device(self, mac: str) -> bool:
        norm_mac = mac.lower()
        self.active_leases = [l for l in self.active_leases if l["mac"].lower() != norm_mac]
        self.emit("devices_updated")
        return True

    async def get_reboot_required(self) -> bool:
        return self.reboot_required

    async def reboot_host(self) -> bool:
        self.reboot_required = False
        return True

    async def create_backup(self, passphrase: str) -> str:
        return "/tmp/roostos-mock-backup.tar.gz"

    async def restore_backup(self, backup_path: str, passphrase: str) -> bool:
        return True

    async def get_certificate_status(self) -> Dict[str, Any]:
        return {
            "root_ca": {"valid": True, "subject": "CN=RoostOS Mock Root CA", "expires": "2036-01-01"},
            "server": {"valid": True, "subject": "CN=roost-router.local", "expires": "2027-01-01"},
            "domains": {},
        }

    async def renew_server_certificate(self) -> Dict[str, Any]:
        return {"status": "success", "message": "Mock server certificate renewed."}

    async def get_cluster_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "cluster_id": "roost-home-cluster",
            "nodes_count": len(self.nodes),
            "ha_enabled": True,
            "nodes": self.nodes,
        }

    async def get_node_health(self, check_mqtt: bool = False) -> Dict[str, Any]:
        return {"status": "healthy", "cpu_percent": 12.5, "memory_percent": 42.1, "temp_c": 44.0}

    async def get_detected_hardware(self) -> List[Dict[str, Any]]:
        return [
            {"interface": "eth0", "speed_mbps": 2500, "type": "ethernet", "driver": "igc"},
            {"interface": "wlan0", "speed_mbps": 1200, "type": "wifi", "driver": "ath11k"},
        ]

    async def get_nodes(self) -> List[Dict[str, Any]]:
        return list(self.nodes)

    async def save_nodes(self, nodes: List[Dict[str, Any]]) -> bool:
        self.nodes = list(nodes)
        self.emit("nodes_updated")
        return True

    async def generate_join_token(self) -> str:
        return "mock-cluster-join-token-987654321"

    async def discover_controllers(self) -> List[Dict[str, Any]]:
        return [{"host": "192.168.1.2", "hostname": "roost-controller-01", "port": 8000}]

    async def get_pending_upnp_requests(self) -> List[Dict[str, Any]]:
        return list(self.pending_upnp)

    async def approve_upnp_request(self, mac: str, port: int, protocol: str) -> bool:
        self.pending_upnp = [r for r in self.pending_upnp if not (r["mac"] == mac and r["port"] == port)]
        return True

    async def reject_upnp_request(self, mac: str, port: int, protocol: str) -> bool:
        self.pending_upnp = [r for r in self.pending_upnp if not (r["mac"] == mac and r["port"] == port)]
        return True

    # ==========================================
    # Signal Observers & Emitter
    # ==========================================

    def _register_listener(self, event_name: str, callback: Callable) -> None:
        self._listeners.setdefault(event_name, []).append(callback)

    def on_users_updated(self, callback: Callable[[], None]) -> None:
        self._register_listener("users_updated", callback)

    def on_nodes_updated(self, callback: Callable[[], None]) -> None:
        self._register_listener("nodes_updated", callback)

    def on_hardware_discovered(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._register_listener("hardware_discovered", callback)

    def on_people_updated(self, callback: Callable[[], None]) -> None:
        self._register_listener("people_updated", callback)

    def on_locations_updated(self, callback: Callable[[], None]) -> None:
        self._register_listener("locations_updated", callback)

    def on_devices_updated(self, callback: Callable[[], None]) -> None:
        self._register_listener("devices_updated", callback)

    def on_schedules_updated(self, callback: Callable[[], None]) -> None:
        self._register_listener("schedules_updated", callback)

    def on_device_connected(self, callback: Callable[[str, str, str], None]) -> None:
        self._register_listener("device_connected", callback)

    def on_unknown_device_discovered(self, callback: Callable[[str, str, str], None]) -> None:
        self._register_listener("unknown_device_discovered", callback)

    def on_bypass_expired(self, callback: Callable[[str], None]) -> None:
        self._register_listener("bypass_expired", callback)

    def on_upnp_request_received(self, callback: Callable[[str, int, str, str], None]) -> None:
        self._register_listener("upnp_request_received", callback)

    def on_upnp_queue_cleared(self, callback: Callable[[], None]) -> None:
        self._register_listener("upnp_queue_cleared", callback)

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Helper to invoke registered callbacks for simulated D-Bus events."""
        for cb in self._listeners.get(event_name, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"MockRoostClient listener error for {event_name}: {e}")
