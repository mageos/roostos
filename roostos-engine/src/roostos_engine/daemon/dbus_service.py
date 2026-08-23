import os
import sys
import json
import asyncio
from typing import List, Optional, Set, Dict, Any, Coroutine

from dbus_next.service import ServiceInterface, method, signal as dbus_signal, dbus_property

from roostos_engine.repository import ConfigRepository, YAMLConfigRepository
from roostos_engine.state_db import StateDB
from roostos_engine.firewall_manager import FirewallManager
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.health import HealthChecker
from roostos_engine.cluster_manager import ClusterManager
from roostos_engine.mdns_discovery import MDNSDiscoveryService
from roostos_engine.daemon.backup_handler import BackupHandler
from roostos_engine.daemon.upnp_handler import UPnPHandler
from roostos_engine.daemon.allowance_tracker import AllowanceTracker
from roostos_engine.daemon.ui_extractor import extract_plugin_ui
from roostos_engine.daemon.config_adapter import ConfigDBusMixin
from roostos_engine.daemon.cluster_adapter import ClusterDBusMixin

BUS_NAME = "org.roostos.Daemon"
OBJECT_PATH = "/org/roostos/Daemon"


class RoostDaemonInterface(ServiceInterface, ConfigDBusMixin, ClusterDBusMixin):
    """Primary D-Bus service interface orchestrating subsystems, certs, state, and firewall policies."""

    def __init__(self, name: str, config_dir: str, mock: bool = False, repository: Optional[ConfigRepository] = None):
        super().__init__(name)
        self.mock = mock
        if repository is not None:
            self.repository = repository
            self.config_dir = getattr(repository, "config_dir", config_dir)
        else:
            self.repository = YAMLConfigRepository(config_dir)
            self.config_dir = config_dir
        self._reboot_required = False

        certs_dir = os.path.join(self.config_dir, "certs")
        self.cert_manager = CertificateManager(certs_dir)
        self.health_checker = HealthChecker(config_dir=self.config_dir, mock=self.mock)
        self.mdns_service = MDNSDiscoveryService(mock=self.mock)
        self.cluster_manager = ClusterManager(
            config_dir=self.config_dir,
            mock=self.mock,
            health_checker=self.health_checker,
            mdns_service=self.mdns_service,
        )

        from roostos_engine.subsystems import discover_subsystems
        self.subsystems = discover_subsystems(self)

        # Initialize SQLite state cache
        db_path = os.path.join(self.config_dir, "state.db")
        self.state_db = StateDB(db_path)

        # Initialize modular handlers
        self.backup_handler = BackupHandler(
            config_dir=self.config_dir,
            get_hostname=lambda: self._config.system.hostname,
            on_restored=self.reload_config,
        )

        self.upnp_handler = UPnPHandler(
            state_db=self.state_db,
            get_config=lambda: self._config,
            save_devices=self.repository.save_devices_config,
            on_devices_updated=self._on_devices_updated,
            on_queue_cleared=self.UPnPQueueCleared,
            on_request_received=self.UPnPRequestReceived,
        )

        self.allowance_tracker = AllowanceTracker(
            get_config=lambda: self._config,
            get_firewall_manager=lambda: self.firewall_manager,
            state_db=self.state_db,
            mock=self.mock,
            on_bypass_expired=self.BypassExpired,
        )

        try:
            self.load_initial_config()
            print(f"RoostOS config loaded successfully from {self.config_dir}")
        except Exception as e:
            print(f"Warning: Failed to load configuration on start: {e}", file=sys.stderr)

        self.allowance_tracker.start_loop()

    # Backwards compatibility properties forwarding to allowance_tracker
    @property
    def currently_blocked(self) -> Set[str]:
        return self.allowance_tracker.currently_blocked

    @property
    def allowance_usage(self) -> Dict[str, int]:
        return self.allowance_tracker.allowance_usage

    @property
    def temporary_bypasses(self) -> List[Dict[str, Any]]:
        return self.allowance_tracker.temporary_bypasses

    @temporary_bypasses.setter
    def temporary_bypasses(self, val: List[Dict[str, Any]]) -> None:
        self.allowance_tracker.temporary_bypasses = val

    @property
    def nft_call_history(self) -> List[List[str]]:
        return self.allowance_tracker.nft_call_history

    @property
    def enforcer_task(self) -> Optional[asyncio.Task]:
        return self.allowance_tracker.enforcer_task

    def execute_system_cmd(self, args: List[str]) -> bool:
        return self.allowance_tracker.execute_system_cmd(args)

    def setup_policy_routing(self) -> None:
        self.allowance_tracker.setup_policy_routing()

    def run_scheduler_check(self) -> None:
        self.allowance_tracker.run_scheduler_check()

    def scheduler_loop(self) -> Coroutine[Any, Any, None]:
        return self.allowance_tracker._scheduler_loop()

    def stop_enforcer(self) -> None:
        self.allowance_tracker.stop_loop()

    def _on_devices_updated(self) -> None:
        self.reload_config()
        self.DevicesUpdated()

    def should_run_subsystem(self, subsystem_name: str) -> bool:
        node_id = "node-01"
        if self._config.system and self._config.system.cluster and self._config.system.cluster.node_id:
            node_id = self._config.system.cluster.node_id

        current_node = next((n for n in self._config.nodes if n.id == node_id), None)
        if not current_node or not current_node.roles:
            return True

        roles = [r.value if hasattr(r, "value") else str(r) for r in current_node.roles]
        if subsystem_name in ("system_settings", "network_interfaces"):
            return True
        if subsystem_name in ("firewall_services", "dhcp_services", "qos_services"):
            return "gateway_router" in roles
        if subsystem_name == "wifi_services":
            return "access_point" in roles or "gateway_router" in roles
        if subsystem_name == "plugins_sync":
            return "compute_node" in roles or "controller" in roles
        if subsystem_name == "mdns_repeater":
            return "gateway_router" in roles or "access_point" in roles
        return True

    def load_initial_config(self) -> None:
        self._config = self.repository.get_config()
        self.firewall_manager = FirewallManager(self._config)
        for subsystem in self.subsystems:
            if subsystem.run_on_init and self.should_run_subsystem(subsystem.name):
                print(f"Initializing subsystem: {subsystem.name}")
                subsystem.update()

    def reload_config(self) -> None:
        self._config = self.repository.get_config()
        self.firewall_manager = FirewallManager(self._config)
        for subsystem in self.subsystems:
            if subsystem.run_on_reload and self.should_run_subsystem(subsystem.name):
                print(f"Reloading subsystem: {subsystem.name}")
                subsystem.update()

    # D-Bus Methods - Certificates
    @method()
    def IssuePluginCertificate(self, plugin_id: 's', scopes_json: 's') -> 's':
        try:
            return json.dumps(self.cert_manager.issue_plugin_cert(plugin_id, json.loads(scopes_json)))
        except Exception as e:
            return json.dumps({"error": str(e)})

    @method()
    def IssueServiceCertificate(self, service_name: 's', scopes_json: 's') -> 's':
        try:
            return json.dumps(self.cert_manager.issue_service_cert(service_name, json.loads(scopes_json)))
        except Exception as e:
            return json.dumps({"error": str(e)})

    @method()
    def VerifyCertificate(self, cert_pem: 's') -> 's':
        try:
            return json.dumps(self.cert_manager.verify_client_cert(cert_pem))
        except Exception as e:
            return json.dumps({"valid": False, "error": str(e)})

    @method()
    def RenewServerCertificate(self) -> 's':
        try:
            res = self.cert_manager.issue_server_cert(
                hostname=self._config.system.hostname,
                domain=getattr(self._config.system, "domain", "lan")
            )
            return json.dumps({"status": "success", "cert_status": self.cert_manager.get_cert_status()})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @method()
    def GetCertificateStatus(self) -> 's':
        return json.dumps(self.cert_manager.get_cert_status())

    @method()
    async def ExtractPluginUI(self, image_name: 's', ui_entrypoint: 's', plugin_id: 's') -> 'b':
        registry = getattr(self._config.system, "docker_registry", None)
        return extract_plugin_ui(image_name, ui_entrypoint, plugin_id, registry)

    @dbus_property()
    def RebootRequired(self) -> 'b':
        if os.path.exists("/var/run/reboot-required"):
            return True
        return self._reboot_required

    @RebootRequired.setter
    def RebootRequired(self, val: bool):
        self._reboot_required = val

    @dbus_signal()
    def UsersUpdated(self) -> None: pass
    @dbus_signal()
    def PeopleUpdated(self) -> None: pass
    @dbus_signal()
    def LocationsUpdated(self) -> None: pass
    @dbus_signal()
    def DevicesUpdated(self) -> None: pass
    @dbus_signal()
    def SchedulesUpdated(self) -> None: pass
    @dbus_signal()
    def NodesUpdated(self) -> None: pass
    @dbus_signal()
    def UPnPQueueCleared(self) -> None: pass

    @dbus_signal()
    def DeviceConnected(self, mac: str, ip: str, hostname: str) -> 's': return f"{mac},{ip},{hostname}"
    @dbus_signal()
    def UnknownDeviceDiscovered(self, mac: str, ip: str, hostname: str) -> 's': return f"{mac},{ip},{hostname}"
    @dbus_signal()
    def BypassExpired(self, mac: str) -> 's': return mac
    @dbus_signal()
    def UPnPRequestReceived(self, mac: str, port: int, protocol: str, description: str) -> 's':
        return f"{mac},{port},{protocol},{description}"
    @dbus_signal()
    def HardwareDiscovered(self, interface_json: str) -> 's': return interface_json

    @method()
    def GrantTimeExtension(self, mac: 's', duration_seconds: 'i') -> 'b':
        return self.allowance_tracker.grant_time_extension(mac, duration_seconds)

    @method()
    def RemoveTimeExtension(self, mac: 's') -> 'b':
        return self.allowance_tracker.remove_time_extension(mac)

    @method()
    def CreateBackup(self, passphrase: 's') -> 's':
        return self.backup_handler.create_backup(passphrase)

    @method()
    def RestoreBackup(self, backup_path: 's', passphrase: 's') -> 'b':
        return self.backup_handler.restore_backup(backup_path, passphrase)

    @method()
    def RebootHost(self) -> 'b':
        print("Mock Host reboot command issued cleanly.")
        return True

    @method()
    def GetPendingUPnPRequests(self) -> 's':
        return json.dumps(self.upnp_handler.get_pending_requests())

    @method()
    def RegisterUPnPRequest(self, mac: 's', internal_ip: 's', port: 'i', internal_port: 'i', protocol: 's', description: 's') -> 'b':
        return self.upnp_handler.register_request(mac, internal_ip, port, internal_port, protocol, description)

    @method()
    def ApproveUPnPRequest(self, mac: 's', port: 'i', protocol: 's', remember: 'b', trust_device: 'b') -> 'b':
        return self.upnp_handler.approve_request(mac, port, protocol, remember, trust_device)

    @method()
    def RejectUPnPRequest(self, mac: 's', port: 'i', protocol: 's') -> 'b':
        return self.upnp_handler.reject_request(mac, port, protocol)
