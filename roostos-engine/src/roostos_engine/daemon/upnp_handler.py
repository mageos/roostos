import sys
from typing import Callable, List, Dict, Any
from roostos_engine.config import RoostConfig, DevicesConfig, DeviceConfig
from roostos_engine.state_db import StateDB


class UPnPHandler:
    """Manages UPnP port mapping requests, device trust checks, and admin staging approvals."""

    def __init__(
        self,
        state_db: StateDB,
        get_config: Callable[[], RoostConfig],
        save_devices: Callable[[DevicesConfig], None],
        on_devices_updated: Callable[[], None],
        on_queue_cleared: Callable[[], None],
        on_request_received: Callable[[str, int, str, str], None],
    ):
        self.state_db = state_db
        self.get_config = get_config
        self.save_devices = save_devices
        self.on_devices_updated = on_devices_updated
        self.on_queue_cleared = on_queue_cleared
        self.on_request_received = on_request_received

    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Returns list of pending UPnP requests from the SQLite cache."""
        return self.state_db.get_pending_upnp()

    def register_request(
        self,
        mac: str,
        internal_ip: str,
        port: int,
        internal_port: int,
        protocol: str,
        description: str,
    ) -> bool:
        """Evaluates incoming UPnP request against trust rules or queues for review."""
        try:
            config = self.get_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            
            # Check if device is trusted or mapping is pre-approved
            trusted = False
            for d in config.devices:
                if d.mac == norm_mac:
                    if d.upnp_trusted:
                        trusted = True
                        break
                    if any(ap.port == port and ap.protocol == protocol.lower() for ap in d.upnp_allowed_ports):
                        trusted = True
                        break
            
            if trusted:
                print(f"UPnP request from trusted device {norm_mac} on port {port}/{protocol} approved immediately.")
                return True
                
            # Otherwise, queue in SQLite cache and broadcast review signal
            self.state_db.add_pending_upnp(norm_mac, internal_ip, port, internal_port, protocol, description)
            self.on_request_received(norm_mac, port, protocol, description)
            return False
        except Exception as e:
            print(f"Error registering UPnP request: {e}", file=sys.stderr)
            return False

    def approve_request(
        self,
        mac: str,
        port: int,
        protocol: str,
        remember: bool,
        trust_device: bool,
    ) -> bool:
        """Approves a pending UPnP request, optionally remembering the port or trusting the device."""
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.state_db.remove_pending_upnp(norm_mac, port, protocol)
            config = self.get_config()
            
            if trust_device:
                devices_list = []
                for d in config.devices:
                    d_dump = d.model_dump()
                    if d.mac == norm_mac:
                        d_dump["upnp_trusted"] = True
                    devices_list.append(d_dump)
                
                devices_config_obj = DevicesConfig(
                    people=config.people,
                    buildings=config.buildings,
                    rooms=config.rooms,
                    devices=devices_list
                )
                self.save_devices(devices_config_obj)
                self.on_devices_updated()

            elif remember:
                devices_list = []
                for d in config.devices:
                    d_dump = d.model_dump()
                    if d.mac == norm_mac:
                        allowed_ports = d_dump.get("upnp_allowed_ports", [])
                        if not any(ap["port"] == port and ap["protocol"] == protocol for ap in allowed_ports):
                            allowed_ports.append({"port": port, "protocol": protocol})
                        d_dump["upnp_allowed_ports"] = allowed_ports
                    devices_list.append(d_dump)
                
                devices_config_obj = DevicesConfig(
                    people=config.people,
                    buildings=config.buildings,
                    rooms=config.rooms,
                    devices=devices_list
                )
                self.save_devices(devices_config_obj)
                self.on_devices_updated()
            
            self.on_queue_cleared()
            print(f"UPnP request approved for MAC: {norm_mac}, Port: {port}/{protocol} (Remember: {remember}, Trust: {trust_device})")
            return True
        except Exception as e:
            print(f"Error approving UPnP request: {e}", file=sys.stderr)
            return False

    def reject_request(self, mac: str, port: int, protocol: str) -> bool:
        """Rejects and removes a pending UPnP request from the staging queue."""
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.state_db.remove_pending_upnp(norm_mac, port, protocol)
            self.on_queue_cleared()
            print(f"UPnP request rejected for MAC: {norm_mac}, Port: {port}/{protocol}")
            return True
        except Exception as e:
            print(f"Error rejecting UPnP request: {e}", file=sys.stderr)
            return False
