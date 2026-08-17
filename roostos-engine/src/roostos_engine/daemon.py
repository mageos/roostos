import os
import sys
import json
import asyncio
import signal
import hashlib
import tempfile
import shutil
import tarfile
from typing import List, Dict, Any, Optional, Callable

from dbus_next.service import ServiceInterface, method, signal as dbus_signal, dbus_property
from dbus_next.aio import MessageBus
from dbus_next import BusType
import datetime
import subprocess

from roostos_engine.config import DevicesConfig, SystemConfig, SchedulesConfig, DeviceConfig, InputRuleConfig, FirewallSettings
from roostos_engine.repository import ConfigRepository, YAMLConfigRepository
from roostos_engine.state_db import StateDB
from roostos_engine.firewall_manager import FirewallManager
from roostos_engine.scheduler import is_schedule_active, resolve_schedule_targets

BUS_NAME = "org.roostos.Daemon"
OBJECT_PATH = "/org/roostos/Daemon"

from roostos_engine.cert_manager import CertificateManager

class RoostDaemonInterface(ServiceInterface):
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
        
        from roostos_engine.subsystems import discover_subsystems
        self.subsystems = discover_subsystems(self)
        
        try:
            self.load_initial_config()
            print(f"RoostOS config loaded successfully from {self.config_dir}")
        except Exception as e:
            print(f"Warning: Failed to load configuration on start: {e}", file=sys.stderr)

        # Initialize SQLite state cache
        db_path = os.path.join(self.config_dir, "state.db")
        self.state_db = StateDB(db_path)
        self.temporary_bypasses: List[Dict[str, Any]] = []
        
        # Initialize Firewall and Scheduling structures
        self.currently_blocked: Set[str] = set()
        self.allowance_usage: Dict[str, int] = {} # mac -> seconds used today
        self.nft_call_history: List[List[str]] = []
        self._last_allowance_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        try:
            # Start background enforcer loop
            coro = self.scheduler_loop()
            self.enforcer_task = asyncio.create_task(coro)
            self.run_scheduler_check()
        except Exception as e:
            coro.close()  # Prevent "coroutine was never awaited" warning
            self.enforcer_task = None
            print(f"Warning: Failed to start enforcer: {e}", file=sys.stderr)

    def load_initial_config(self):
        self._config = self.repository.get_config()
        self.firewall_manager = FirewallManager(self._config)
        for subsystem in self.subsystems:
            if subsystem.run_on_init:
                print(f"Initializing subsystem: {subsystem.name}")
                subsystem.update()

    def reload_config(self):
        self._config = self.repository.get_config()
        self.firewall_manager = FirewallManager(self._config)
        for subsystem in self.subsystems:
            if subsystem.run_on_reload:
                print(f"Reloading subsystem: {subsystem.name}")
                subsystem.update()






    @method()
    def IssuePluginCertificate(self, plugin_id: 's', scopes_json: 's') -> 's':
        try:
            scopes = json.loads(scopes_json)
            res = self.cert_manager.issue_plugin_cert(plugin_id, scopes)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @method()
    def IssueServiceCertificate(self, service_name: 's', scopes_json: 's') -> 's':
        try:
            scopes = json.loads(scopes_json)
            res = self.cert_manager.issue_service_cert(service_name, scopes)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @method()
    def VerifyCertificate(self, cert_pem: 's') -> 's':
        try:
            res = self.cert_manager.verify_client_cert(cert_pem)
            return json.dumps(res)
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
        """Pulls the specified image, extracts the ui_entrypoint file, and saves it to the host static folder."""
        try:
            import docker
            client = docker.from_env()
        except Exception as e:
            raise Exception(f"Docker client error: {e}")

        registry = getattr(self._config.system, "docker_registry", None)
        if registry:
            if "/" in image_name:
                first_part = image_name.split("/")[0]
                if "." in first_part or ":" in first_part or first_part == "localhost":
                    image_name = registry.rstrip("/") + "/" + "/".join(image_name.split("/")[1:])
                else:
                    image_name = f"{registry.rstrip('/')}/{image_name}"
            else:
                image_name = f"{registry.rstrip('/')}/{image_name}"

        try:
            print(f"Pulling image for UI extraction: {image_name}")
            client.images.pull(image_name)
        except Exception as e:
            raise Exception(f"Image pull failed: {e}")

        temp_container = None
        try:
            temp_container = client.containers.create(image_name)
            
            import io
            import tarfile
            
            stream, stat = temp_container.get_archive(ui_entrypoint)
            file_data = b"".join(stream)
            
            tar = tarfile.open(fileobj=io.BytesIO(file_data))
            member = tar.next()
            if not member:
                raise Exception("Empty UI tar stream from container")
            
            extracted_file = tar.extractfile(member)
            ui_content = extracted_file.read()
            
            assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
            dest_dir = os.path.join(assets_dir, "plugins", plugin_id)
            os.makedirs(dest_dir, exist_ok=True)
            
            dest_file = os.path.join(dest_dir, "ui.js")
            with open(dest_file, "wb") as f:
                f.write(ui_content)
                
            print(f"Successfully extracted plugin UI script for {plugin_id} to {dest_file}")
            return True
            
        except Exception as e:
            print(f"Error during UI extraction: {e}", file=sys.stderr)
            raise Exception(f"Extraction failed: {e}")
        finally:
            if temp_container:
                try:
                    temp_container.remove(force=True)
                except Exception:
                    pass

    @dbus_property()
    def RebootRequired(self) -> 'b':
        if os.path.exists("/var/run/reboot-required"):
            return True
        return self._reboot_required

    @RebootRequired.setter
    def RebootRequired(self, val: bool):
        self._reboot_required = val

    @dbus_signal()
    def UsersUpdated(self) -> None:
        pass

    @dbus_signal()
    def PeopleUpdated(self) -> None:
        pass

    @dbus_signal()
    def LocationsUpdated(self) -> None:
        pass

    @dbus_signal()
    def DevicesUpdated(self) -> None:
        pass

    @dbus_signal()
    def SchedulesUpdated(self) -> None:
        pass

    @dbus_signal()
    def DeviceConnected(self, mac: str, ip: str, hostname: str) -> 's':
        return f"{mac},{ip},{hostname}"

    @dbus_signal()
    def UnknownDeviceDiscovered(self, mac: str, ip: str, hostname: str) -> 's':
        return f"{mac},{ip},{hostname}"

    @dbus_signal()
    def BypassExpired(self, mac: str) -> 's':
        return mac

    @dbus_signal()
    def UPnPRequestReceived(self, mac: str, port: int, protocol: str, description: str) -> 's':
        return f"{mac},{port},{protocol},{description}"

    @dbus_signal()
    def UPnPQueueCleared(self) -> None:
        pass

    @method()
    def GetConfig(self) -> 's':
        self.reload_config()
        return json.dumps(self._config.model_dump(exclude_none=True))

    @method()
    def GetUsers(self) -> 's':
        self.reload_config()
        return json.dumps([u.model_dump() for u in self._config.users])

    @method()
    def GetPeople(self) -> 's':
        self.reload_config()
        return json.dumps([p.model_dump() for p in self._config.people])

    @method()
    def GetBuildings(self) -> 's':
        self.reload_config()
        return json.dumps([b.model_dump() for b in self._config.buildings])

    @method()
    def GetRooms(self) -> 's':
        self.reload_config()
        return json.dumps([r.model_dump() for r in self._config.rooms])

    @method()
    def GetDevices(self) -> 's':
        self.reload_config()
        return json.dumps([d.model_dump() for d in self._config.devices])

    @method()
    def GetActiveLeases(self) -> 's':
        return json.dumps(self.state_db.get_active_leases())

    @method()
    def RegisterLease(self, mac: 's', ip: 's', hostname: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            
            # Check if device is registered
            registered = any(d.mac == norm_mac for d in self._config.devices)
            
            # Register in cache. If not registered, mark as quarantined
            success = self.state_db.register_lease(norm_mac, ip, hostname, quarantined=not registered)
            if not success:
                return False

            # Emit discovery or connect signal
            if registered:
                self.DeviceConnected(norm_mac, ip, hostname)
            else:
                self.UnknownDeviceDiscovered(norm_mac, ip, hostname)
                
            return True
        except Exception as e:
            print(f"Error registering lease on D-Bus: {e}", file=sys.stderr)
            return False

    @method()
    def ReleaseLease(self, mac: 's') -> 'b':
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            success = self.state_db.release_lease(norm_mac)
            return success
        except Exception as e:
            print(f"Error releasing lease on D-Bus: {e}", file=sys.stderr)
            return False

    @method()
    def GetSchedules(self) -> 's':
        self.reload_config()
        return json.dumps([s.model_dump() for s in self._config.schedules])

    @method()
    def GetFirewallRules(self) -> 's':
        """Returns JSON array of configured firewall input rules."""
        self.reload_config()
        return json.dumps([r.model_dump() for r in self._config.firewall.rules])

    @method()
    def UpdateFirewallRule(self, name: 's', interface: 's', protocol: 's', port: 'i', source: 's', action: 's', enabled: 'b') -> 'b':
        """Creates or updates a firewall input rule by name."""
        try:
            self.reload_config()

            new_rule = InputRuleConfig(
                name=name,
                interface=interface if interface else "*",
                protocol=protocol if protocol else "tcp",
                port=port,
                source=source if source else None,
                action=action if action else "accept",
                enabled=enabled
            )

            rules_list = [r.model_dump() for r in self._config.firewall.rules]
            rule_idx = next((i for i, r in enumerate(rules_list) if r["name"] == name), -1)
            if rule_idx >= 0:
                rules_list[rule_idx] = new_rule.model_dump()
            else:
                rules_list.append(new_rule.model_dump())

            firewall_config_obj = FirewallConfig(
                firewall=FirewallSettings(
                    port_forwards=self._config.firewall.port_forwards,
                    rules=rules_list
                )
            )
            self.repository.save_firewall_config(firewall_config_obj)
            self.reload_config()
            self.SchedulesUpdated()
            return True
        except Exception as e:
            print(f"Error updating firewall rule: {e}", file=sys.stderr)
            return False

    @method()
    def DeleteFirewallRule(self, name: 's') -> 'b':
        """Deletes a firewall input rule by name."""
        try:
            self.reload_config()
            rules_list = [r.model_dump() for r in self._config.firewall.rules if r.name != name]

            firewall_config_obj = FirewallConfig(
                firewall=FirewallSettings(
                    port_forwards=self._config.firewall.port_forwards,
                    rules=rules_list
                )
            )
            self.repository.save_firewall_config(firewall_config_obj)
            self.reload_config()
            self.SchedulesUpdated()
            return True
        except Exception as e:
            print(f"Error deleting firewall rule: {e}", file=sys.stderr)
            return False

    @method()
    def UpdateDevice(self, mac: 's', name: 's', owner_id: 's', location_id: 's', tags: 'as', static_ip: 's', upnp_trusted: 'b', upnp_allowed_ports_json: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            
            allowed_ports = []
            if upnp_allowed_ports_json:
                allowed_ports = json.loads(upnp_allowed_ports_json)

            device_idx = -1
            for idx, d in enumerate(self._config.devices):
                if d.mac == norm_mac:
                    device_idx = idx
                    break

            new_device = {
                "mac": norm_mac,
                "name": name,
                "owner": owner_id if owner_id else None,
                "location": location_id if location_id else None,
                "tags": tags,
                "static_ip": static_ip if static_ip else None,
                "upnp_trusted": upnp_trusted,
                "upnp_allowed_ports": allowed_ports
            }
            
            devices_list = [d.model_dump() for d in self._config.devices]
            if device_idx >= 0:
                devices_list[device_idx] = new_device
            else:
                devices_list.append(new_device)

            devices_config_obj = DevicesConfig(
                people=self._config.people,
                buildings=self._config.buildings,
                rooms=self._config.rooms,
                devices=devices_list
            )
            
            self.repository.save_devices_config(devices_config_obj)
            self.reload_config()
            self.DevicesUpdated()
            return True
        except Exception as e:
            print(f"Error updating device: {e}", file=sys.stderr)
            return False

    @method()
    def DeleteDevice(self, mac: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            devices_list = [d.model_dump() for d in self._config.devices if d.mac != norm_mac]
            
            devices_config_obj = DevicesConfig(
                people=self._config.people,
                buildings=self._config.buildings,
                rooms=self._config.rooms,
                devices=devices_list
            )
            self.repository.save_devices_config(devices_config_obj)
            self.reload_config()
            self.DevicesUpdated()
            return True
        except Exception as e:
            print(f"Error deleting device: {e}", file=sys.stderr)
            return False

    @method()
    def GrantTimeExtension(self, mac: 's', duration_seconds: 'i') -> 'b':
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.temporary_bypasses = [b for b in self.temporary_bypasses if b["mac"] != norm_mac]
            
            expiry = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
            self.temporary_bypasses.append({
                "mac": norm_mac,
                "expiry": expiry
            })
            print(f"Time extension of {duration_seconds}s granted to MAC: {norm_mac} (expires at {expiry})")
            self.run_scheduler_check()
            return True
        except Exception as e:
            print(f"Error granting extension: {e}", file=sys.stderr)
            return False

    @method()
    def RemoveTimeExtension(self, mac: 's') -> 'b':
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.temporary_bypasses = [b for b in self.temporary_bypasses if b["mac"] != norm_mac]
            self.BypassExpired(norm_mac)
            self.run_scheduler_check()
            return True
        except Exception as e:
            print(f"Error removing extension: {e}", file=sys.stderr)
            return False

    @method()
    def CreateBackup(self, passphrase: 's') -> 's':
        backup_dir = "/var/lib/roostos/backups"
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except PermissionError:
            # Fall back to user-writeable path inside config_dir for testing/sandbox envs
            backup_dir = os.path.join(self.config_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, "roostos-backup.tar.gz.gpg")

        # Create a temporary directory to stage configuration files and manifest
        with tempfile.TemporaryDirectory() as tmp_dir:
            staged_configs = os.path.join(tmp_dir, "roostos")
            os.makedirs(staged_configs, exist_ok=True)

            # Copy all files from config directory (e.g. /etc/roostos/) into staged_configs
            config_files = []
            if os.path.exists(self.config_dir):
                for item in os.listdir(self.config_dir):
                    item_path = os.path.join(self.config_dir, item)
                    # Skip state.db or temporary/cache files
                    if item in ("state.db", "state.db-shm", "state.db-wal"):
                        continue
                    if os.path.isdir(item_path):
                        shutil.copytree(item_path, os.path.join(staged_configs, item))
                    else:
                        shutil.copy2(item_path, os.path.join(staged_configs, item))
                        config_files.append(item)

            # Calculate SHA-256 hashes of copied configuration files
            manifest_files = []
            for root, dirs, files in os.walk(staged_configs):
                for f in files:
                    file_abspath = os.path.join(root, f)
                    rel_path = os.path.relpath(file_abspath, staged_configs)
                    sha = hashlib.sha256()
                    with open(file_abspath, "rb") as file_bin:
                        while chunk := file_bin.read(4096):
                            sha.update(chunk)
                    manifest_files.append({
                        "path": rel_path,
                        "sha256": sha.hexdigest()
                    })

            # Create manifest.json
            manifest = {
                "roostos_backup_version": "1.0",
                "roostos_version": "0.1.0",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "hostname": self._config.system.hostname,
                "files": manifest_files
            }
            with open(os.path.join(staged_configs, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2)

            # Tar the staging directory
            tar_path = os.path.join(tmp_dir, "backup.tar.gz")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(staged_configs, arcname="roostos")

            # Encrypt tar.gz using GPG
            try:
                subprocess.run(
                    ["gpg", "--symmetric", "--cipher-algo", "AES256", "--batch", "--yes", "--passphrase-fd", "0", "-o", backup_path, tar_path],
                    input=passphrase.encode(),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                print(f"Backup created successfully at {backup_path} using GPG encryption.")
                return backup_path
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode()
                print(f"Error encrypting backup: {err_msg}", file=sys.stderr)
                raise Exception(f"Encryption failed: {err_msg}")

    @method()
    def RestoreBackup(self, backup_path: 's', passphrase: 's') -> 'b':
        if not os.path.exists(backup_path):
            print(f"Restore failed: Backup file {backup_path} not found.", file=sys.stderr)
            return False

        with tempfile.TemporaryDirectory() as tmp_dir:
            decrypted_tar = os.path.join(tmp_dir, "backup.tar.gz")
            
            # Decrypt the GPG backup
            try:
                subprocess.run(
                    ["gpg", "--decrypt", "--batch", "--yes", "--passphrase-fd", "0", "-o", decrypted_tar, backup_path],
                    input=passphrase.encode(),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                print(f"Restore failed: Decryption error: {e.stderr.decode()}", file=sys.stderr)
                return False

            # Extract tar
            restore_staged = os.path.join(tmp_dir, "restore_staged")
            try:
                with tarfile.open(decrypted_tar, "r:gz") as tar:
                    tar.extractall(path=restore_staged, filter="data")
            except Exception as e:
                print(f"Restore failed: Failed to extract archive: {e}", file=sys.stderr)
                return False

            roostos_dir = os.path.join(restore_staged, "roostos")
            manifest_path = os.path.join(roostos_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                print("Restore failed: manifest.json missing from backup.", file=sys.stderr)
                return False

            # Read and parse manifest
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except Exception as e:
                print(f"Restore failed: Failed to parse manifest: {e}", file=sys.stderr)
                return False

            # Validate manifest structure and versions
            if manifest.get("roostos_backup_version") != "1.0":
                print(f"Restore failed: Incompatible backup version: {manifest.get('roostos_backup_version')}", file=sys.stderr)
                return False

            # Verify checksums of files
            for file_entry in manifest.get("files", []):
                rel_path = file_entry.get("path")
                expected_sha = file_entry.get("sha256")
                full_path = os.path.join(roostos_dir, rel_path)

                if not os.path.exists(full_path):
                    print(f"Restore failed: File {rel_path} in manifest is missing from backup.", file=sys.stderr)
                    return False

                sha = hashlib.sha256()
                with open(full_path, "rb") as file_bin:
                    while chunk := file_bin.read(4096):
                        sha.update(chunk)
                
                if sha.hexdigest() != expected_sha:
                    print(f"Restore failed: Checksum mismatch for file {rel_path}.", file=sys.stderr)
                    return False

            # If all checks pass, restore files to config directory
            try:
                # Remove manifest.json from staged before copying to /etc/roostos
                os.remove(manifest_path)
                
                # Copy everything to config_dir
                for item in os.listdir(roostos_dir):
                    src_item = os.path.join(roostos_dir, item)
                    dst_item = os.path.join(self.config_dir, item)
                    if os.path.isdir(src_item):
                        if os.path.exists(dst_item):
                            shutil.rmtree(dst_item)
                        shutil.copytree(src_item, dst_item)
                    else:
                        shutil.copy2(src_item, dst_item)
                
                print("Backup files successfully restored to configuration directory.")
                self.reload_config()
                return True
            except Exception as e:
                print(f"Restore failed: Failed to copy configurations: {e}", file=sys.stderr)
                return False

    @method()
    def RebootHost(self) -> 'b':
        print("Mock Host reboot command issued cleanly.")
        return True

    @method()
    def GetPendingUPnPRequests(self) -> 's':
        return json.dumps(self.state_db.get_pending_upnp())

    @method()
    def RegisterUPnPRequest(self, mac: 's', internal_ip: 's', port: 'i', internal_port: 'i', protocol: 's', description: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            
            # Check if device is trusted or mapping is pre-approved
            trusted = False
            for d in self._config.devices:
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
            self.UPnPRequestReceived(norm_mac, port, protocol, description)
            return False
        except Exception as e:
            print(f"Error registering UPnP request on D-Bus: {e}", file=sys.stderr)
            return False

    @method()
    def ApproveUPnPRequest(self, mac: 's', port: 'i', protocol: 's', remember: 'b', trust_device: 'b') -> 'b':
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.state_db.remove_pending_upnp(norm_mac, port, protocol)
            
            if trust_device:
                self.reload_config()
                devices_list = []
                for d in self._config.devices:
                    d_dump = d.model_dump()
                    if d.mac == norm_mac:
                        d_dump["upnp_trusted"] = True
                    devices_list.append(d_dump)
                
                devices_config_obj = DevicesConfig(
                    people=self._config.people,
                    buildings=self._config.buildings,
                    rooms=self._config.rooms,
                    devices=devices_list
                )
                self.repository.save_devices_config(devices_config_obj)
                self.reload_config()
                self.DevicesUpdated()

            elif remember:
                self.reload_config()
                devices_list = []
                for d in self._config.devices:
                    d_dump = d.model_dump()
                    if d.mac == norm_mac:
                        allowed_ports = d_dump.get("upnp_allowed_ports", [])
                        if not any(ap["port"] == port and ap["protocol"] == protocol for ap in allowed_ports):
                            allowed_ports.append({"port": port, "protocol": protocol})
                        d_dump["upnp_allowed_ports"] = allowed_ports
                    devices_list.append(d_dump)
                
                devices_config_obj = DevicesConfig(
                    people=self._config.people,
                    buildings=self._config.buildings,
                    rooms=self._config.rooms,
                    devices=devices_list
                )
                self.repository.save_devices_config(devices_config_obj)
                self.reload_config()
                self.DevicesUpdated()
            
            self.UPnPQueueCleared()
            print(f"UPnP request approved for MAC: {norm_mac}, Port: {port}/{protocol} (Remember: {remember}, Trust: {trust_device})")
            return True
        except Exception as e:
            print(f"Error approving UPnP request: {e}", file=sys.stderr)
            return False

    @method()
    def RejectUPnPRequest(self, mac: 's', port: 'i', protocol: 's') -> 'b':
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.state_db.remove_pending_upnp(norm_mac, port, protocol)
            self.UPnPQueueCleared()
            print(f"UPnP request rejected for MAC: {norm_mac}, Port: {port}/{protocol}")
            return True
        except Exception as e:
            print(f"Error rejecting UPnP request: {e}", file=sys.stderr)
            return False

    # ==========================================
    # Firewall Scheduling & Allowance Loop
    # ==========================================

    async def scheduler_loop(self):
        """Periodic enforcer loop running bedtime checkouts and allowance increments."""
        while True:
            try:
                self.run_scheduler_check()
            except Exception as e:
                print(f"Error in background scheduler enforcer loop: {e}", file=sys.stderr)
            await asyncio.sleep(60)

    def stop_enforcer(self):
        """Stops the background enforcer loop task."""
        if self.enforcer_task:
            self.enforcer_task.cancel()
            self.enforcer_task = None

    def execute_system_cmd(self, args: List[str]) -> bool:
        """Executes active firewall or network routing command. Tracks history for tests."""
        self.nft_call_history.append(args)
        print(f"Executing system command: {' '.join(args)}")
        if self.mock or os.getuid() != 0:
            return True
        try:
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"Error executing command: {e}", file=sys.stderr)
            return False

    def setup_policy_routing(self) -> None:
        """Configures routing tables and rules for policy routing (VPNs)."""
        cmds = self.firewall_manager.compile_routing_setup_cmds()
        for cmd in cmds:
            self.execute_system_cmd(cmd)

    def run_scheduler_check(self) -> None:
        """Evaluates active bedtimes, daily limits, and temporary bypass whitelists. Emits delta nft updates."""
        self.reload_config()
        self.setup_policy_routing()
        now = datetime.datetime.now()
        
        # 1. Evaluate Bypasses
        active_bypasses = set()
        valid_bypasses = []
        for b in self.temporary_bypasses:
            if b["expiry"] > now:
                valid_bypasses.append(b)
                active_bypasses.add(b["mac"])
            else:
                self.BypassExpired(b["mac"])
                print(f"Temporary whitelisted bypass expired for MAC: {b['mac']}")
        self.temporary_bypasses = valid_bypasses

        # 2. Check schedules
        blocked_by_schedules = set()
        active_schedules_with_limits = []

        if hasattr(self._config, "schedules") and self._config.schedules:
            for sched in self._config.schedules:
                if is_schedule_active(sched, now):
                    targets = resolve_schedule_targets(sched, self._config)
                    blocked_by_schedules.update(targets)
                
                if sched.daily_limit is not None:
                    active_schedules_with_limits.append(sched)

        # 3. Check Daily Allowances
        today_str = now.strftime("%Y-%m-%d")
        if self._last_allowance_date != today_str:
            self._last_allowance_date = today_str
            self.allowance_usage.clear()
            print(f"Daily allowance counters reset for new date {today_str}.")

        active_leases = self.state_db.get_active_leases()
        active_macs = {l["mac"] for l in active_leases}

        for sched in active_schedules_with_limits:
            targets = resolve_schedule_targets(sched, self._config)
            for mac in targets:
                if mac in active_macs:
                    # Accumulate 60 seconds of usage
                    self.allowance_usage[mac] = self.allowance_usage.get(mac, 0) + 60
                
                limit_seconds = sched.daily_limit * 60
                if self.allowance_usage.get(mac, 0) >= limit_seconds:
                    blocked_by_schedules.add(mac)

        # 4. Filter out whitelisted bypasses
        final_blocked = blocked_by_schedules - active_bypasses

        # 5. Delta nft updates
        to_block = final_blocked - self.currently_blocked
        to_unblock = self.currently_blocked - final_blocked

        for mac in to_block:
            self.execute_system_cmd(self.firewall_manager.get_block_mac_cmd(mac))
            self.currently_blocked.add(mac)

        for mac in to_unblock:
            self.execute_system_cmd(self.firewall_manager.get_unblock_mac_cmd(mac))
            self.currently_blocked.remove(mac)


async def start_daemon(config_dir: str, bus_type: BusType = BusType.SYSTEM, mock: bool = False):
    try:
        bus = await MessageBus(bus_type=bus_type).connect()
    except Exception as e:
        if bus_type == BusType.SYSTEM:
            print("System D-Bus connection failed. Falling back to Session D-Bus bus for local sandbox...", file=sys.stderr)
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
        else:
            raise e

    interface = RoostDaemonInterface(BUS_NAME, config_dir, mock=mock)
    bus.export(OBJECT_PATH, interface)
    await bus.request_name(BUS_NAME)
    print(f"RoostOS Engine Daemon registered on D-Bus: '{BUS_NAME}' at object path '{OBJECT_PATH}'")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def shutdown():
        print("\nShutdown signal received. Releasing D-Bus interfaces...")
        interface.stop_enforcer()
        bus.disconnect()
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass

    await stop_event.wait()


def main():
    import argparse
    from roostos_engine.di import load_providers_settings
    parser = argparse.ArgumentParser(description="RoostOS Engine core daemon service")
    parser.add_argument("--config-dir", default=os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos"), help="Path to split configurations folder")
    parser.add_argument("--providers-config", default=os.environ.get("ROOSTOS_PROVIDERS_CONFIG"), help="Path to custom providers.yaml")
    parser.add_argument("--config-repo", default=os.environ.get("ROOSTOS_CONFIG_REPO"), help="Override repository: 'staging', 'yaml', 'memory'")
    parser.add_argument("--firewall-manager", default=os.environ.get("ROOSTOS_FIREWALL_MANAGER"), help="Override firewall manager: 'nftables', 'mock'")
    parser.add_argument("--cert-manager", default=os.environ.get("ROOSTOS_CERT_MANAGER"), help="Override certificate manager: 'standard', 'mock'")
    parser.add_argument("--session", action="store_true", help="Force connecting to Session D-Bus bus instead of System D-Bus")
    parser.add_argument("--mock", action="store_true", help="Force mock mode, bypassing system modifications")
    args = parser.parse_args()

    bus_type = BusType.SESSION if args.session else BusType.SYSTEM

    overrides = {
        "config_repository": args.config_repo,
        "firewall_manager": args.firewall_manager,
        "cert_manager": args.cert_manager,
    }
    if args.mock:
        overrides["firewall_manager"] = "mock"

    providers_settings = load_providers_settings(
        config_dir=args.config_dir,
        providers_config_path=args.providers_config,
        overrides=overrides
    )
    
    try:
        asyncio.run(start_daemon(args.config_dir, bus_type, args.mock or providers_settings.firewall_manager == "mock"))
    except KeyboardInterrupt:
        pass
    print("Daemon stopped cleanly.")


if __name__ == "__main__":
    main()
