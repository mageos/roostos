import os
import sys
import json
import asyncio
import signal
import hashlib
import tempfile
import shutil
import tarfile
from typing import List, Dict, Any, Optional

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

    def apply_system_settings(self):
        """Applies global system configuration (hostname, domain name)."""
        hostname = self._config.system.hostname
        etc_dir = os.environ.get("ROOSTOS_ETC_DIR")

        if etc_dir:
            try:
                os.makedirs(etc_dir, exist_ok=True)
                hostname_path = os.path.join(etc_dir, "hostname")
                with open(hostname_path, "w") as f:
                    f.write(f"{hostname}\n")
                
                hosts_path = os.path.join(etc_dir, "hosts")
                hosts_lines = []
                if os.path.exists(hosts_path):
                    with open(hosts_path, "r") as f:
                        for line in f:
                            if line.strip().startswith("127.0.0.1"):
                                hosts_lines.append(f"127.0.0.1 localhost {hostname}\n")
                            else:
                                hosts_lines.append(line)
                else:
                    hosts_lines = [f"127.0.0.1 localhost {hostname}\n"]
                with open(hosts_path, "w") as f:
                    f.writelines(hosts_lines)
                print(f"Mock applied hostname '{hostname}' to {etc_dir}")
            except Exception as e:
                print(f"Error applying mock hostname configuration to {etc_dir}: {e}", file=sys.stderr)
        elif not self.mock and os.getuid() == 0:
            try:
                # Update /etc/hostname
                with open("/etc/hostname", "w") as f:
                    f.write(f"{hostname}\n")
                
                # Update /etc/hosts safely
                hosts_lines = []
                if os.path.exists("/etc/hosts"):
                    with open("/etc/hosts", "r") as f:
                        for line in f:
                            if line.strip().startswith("127.0.0.1"):
                                hosts_lines.append(f"127.0.0.1 localhost {hostname}\n")
                            else:
                                hosts_lines.append(line)
                else:
                    hosts_lines = [f"127.0.0.1 localhost {hostname}\n"]
                with open("/etc/hosts", "w") as f:
                    f.writelines(hosts_lines)
                
                # Apply instantly on host
                subprocess.run(["hostnamectl", "set-hostname", hostname], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Successfully applied hostname '{hostname}' to system")
            except Exception as e:
                print(f"Error applying system hostname configuration: {e}", file=sys.stderr)
        else:
            print(f"Non-root or mock mode. Mock applied hostname: '{hostname}'")

        domain = self._config.system.domain
        print(f"Applied local domain name: '{domain}'")

    def load_initial_config(self):
        self._config = self.repository.get_config()
        self.firewall_manager = FirewallManager(self._config)
        self.apply_system_settings()
        self.update_network_interfaces()
        self.update_wifi_services()
        self.update_dhcp_services()
        self.update_qos_services()
        self.update_firewall_services()

    def reload_config(self):
        self._config = self.repository.get_config()
        self.firewall_manager = FirewallManager(self._config)
        self.apply_system_settings()
        self.update_network_interfaces()
        self.update_wifi_services()
        self.update_dhcp_services()
        self.update_qos_services()
        self.update_firewall_services()
        self.sync_plugins()

    def update_firewall_services(self):
        """Generates nftables configuration and applies it using nft command line."""
        nft_conf = os.environ.get("ROOSTOS_NFTABLES_CONF")
        if not nft_conf:
            if self.mock:
                return
            nft_conf = "/etc/nftables.conf"

        try:
            os.makedirs(os.path.dirname(nft_conf), exist_ok=True)
            self.firewall_manager.write_ruleset(nft_conf)
            print(f"nftables firewall ruleset written to {nft_conf}")
            
            if self.mock:
                return

            # Apply configuration directly via nft command line for better visibility on errors
            res = subprocess.run(["nft", "-f", nft_conf], capture_output=True, text=True)
            if res.returncode != 0:
                raise Exception(res.stderr.strip())
            print("nftables firewall ruleset applied successfully")
        except Exception as e:
            print(f"Error applying firewall/nftables configuration: {e}", file=sys.stderr)
    def update_network_interfaces(self):
        """Generates systemd-networkd configuration files dynamically from network settings."""
        network_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR")
        if not network_dir:
            if self.mock:
                return
            network_dir = "/etc/systemd/network"

        if not os.path.isdir(network_dir):
            try:
                os.makedirs(network_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create network dir {network_dir}: {e}", file=sys.stderr)
                return

        try:
            print(f"Generating systemd-networkd configurations in {network_dir}...")
            generated_files = set()

            # 1. Generate Bridge NetDev and Network configs
            for bridge in self._config.network.bridges:
                netdev_file = f"20-{bridge.name}.netdev"
                netdev_path = os.path.join(network_dir, netdev_file)
                generated_files.add(netdev_file)
                
                with open(netdev_path, "w") as f:
                    f.write(f"[NetDev]\nName={bridge.name}\nKind=bridge\n")

                network_file = f"20-{bridge.name}.network"
                network_path = os.path.join(network_dir, network_file)
                generated_files.add(network_file)
                
                with open(network_path, "w") as f:
                    f.write(f"[Match]\nName={bridge.name}\n\n[Network]\nAddress={bridge.ip}\nIPMasquerade=yes\nIPForward=yes\n")

            # 2. Generate Physical Interface configs
            etc_dir = os.environ.get("ROOSTOS_ETC_DIR", "/etc")
            pppoe_active = False
            pppoe_iface = ""

            for interface in self._config.network.interfaces:
                if interface.network == "wan":
                    target_iface_name = interface.name
                    
                    # If VLAN tag is present, create a netdev and write network config for parent
                    if interface.vlan_tag:
                        target_iface_name = f"{interface.name}.{interface.vlan_tag}"
                        
                        netdev_file = f"10-{interface.name}.{interface.vlan_tag}.netdev"
                        netdev_path = os.path.join(network_dir, netdev_file)
                        generated_files.add(netdev_file)
                        with open(netdev_path, "w") as f:
                            f.write(f"[NetDev]\nName={target_iface_name}\nKind=vlan\n\n[VLAN]\nId={interface.vlan_tag}\n")
                        
                        # Parent interface only needs matching and linking the VLAN
                        parent_file = f"10-{interface.name}.network"
                        parent_path = os.path.join(network_dir, parent_file)
                        generated_files.add(parent_file)
                        with open(parent_path, "w") as f:
                            f.write(f"[Match]\nName={interface.name}\nKernelCommandLine=!nfsroot\n\n[Network]\nVLAN={target_iface_name}\n")
                    
                    network_file = f"10-{target_iface_name}.network"
                    network_path = os.path.join(network_dir, network_file)
                    generated_files.add(network_file)
                    
                    with open(network_path, "w") as f:
                        if interface.protocol == "pppoe":
                            # Standard systemd-networkd profile to just bring the physical/VLAN link UP
                            f.write(f"[Match]\nName={target_iface_name}\n\n[Network]\nKeepConfiguration=yes\nLinkLocalAddressing=no\n")
                            pppoe_active = True
                            pppoe_iface = target_iface_name
                        else:
                            f.write(f"[Match]\nName={target_iface_name}\nKernelCommandLine=!nfsroot\n\n[Network]\n")
                            if interface.protocol == "dhcp" or (interface.protocol is None and interface.dhcp is not False):
                                if interface.ipv6 is False:
                                    f.write("DHCP=ipv4\nIPv6AcceptRA=no\nLinkLocalAddressing=ipv4\n")
                                else:
                                    f.write("DHCP=yes\nIPv6AcceptRA=yes\n")
                            else:  # Static config
                                if interface.ip:
                                    f.write(f"Address={interface.ip}\n")
                                if interface.gateway:
                                    f.write(f"Gateway={interface.gateway}\n")
                                if self._config.system.dns and self._config.system.dns.forwarders:
                                    for dns in self._config.system.dns.forwarders:
                                        f.write(f"DNS={dns}\n")
                                if interface.ipv6 is False:
                                    f.write("IPv6AcceptRA=no\nLinkLocalAddressing=ipv4\n")
                                else:
                                    f.write("IPv6AcceptRA=yes\n")
                
                elif interface.network == "lan" and interface.bridge:
                    network_file = f"25-{interface.name}.network"
                    network_path = os.path.join(network_dir, network_file)
                    generated_files.add(network_file)
                    
                    with open(network_path, "w") as f:
                        f.write(f"[Match]\nName={interface.name}\n\n[Network]\nBridge={interface.bridge}\n")

            # PPPoE configuration writing
            if pppoe_active:
                wan_if = next((i for i in self._config.network.interfaces if i.network == "wan" and i.protocol == "pppoe"), None)
                if wan_if and wan_if.pppoe:
                    username = wan_if.pppoe.username
                    password = wan_if.pppoe.password
                    
                    ppp_dir = os.path.join(etc_dir, "ppp", "peers")
                    try:
                        os.makedirs(ppp_dir, exist_ok=True)
                        peer_path = os.path.join(ppp_dir, "roost-wan")
                        with open(peer_path, "w") as f:
                            f.write(f'plugin rp-pppoe.so\n{pppoe_iface}\nuser "{username}"\nnoipdefault\nusepeerdns\ndefaultroute\npersist\nmaxfail 0\n')
                        
                        # Update chap-secrets / pap-secrets
                        for secret_file in ["chap-secrets", "pap-secrets"]:
                            secret_path = os.path.join(etc_dir, "ppp", secret_file)
                            secret_line = f'"{username}" * "{password}"\n'
                            lines = []
                            if os.path.exists(secret_path):
                                with open(secret_path, "r") as sf:
                                    lines = sf.readlines()
                            lines = [l for l in lines if username not in l]
                            lines.append(secret_line)
                            with open(secret_path, "w") as sf:
                                sf.writelines(lines)
                            os.chmod(secret_path, 0o600)
                    except Exception as e:
                        print(f"Warning: Failed to write PPPoE configuration: {e}", file=sys.stderr)
                    
                    if os.getuid() == 0 and not self.mock:
                        print("Starting PPPoE connection...")
                        subprocess.run(["pon", "roost-wan"], check=False)
            else:
                if os.getuid() == 0 and not self.mock:
                    peer_file = os.path.join(etc_dir, "ppp", "peers", "roost-wan")
                    if os.path.exists(peer_file):
                        print("Stopping PPPoE connection...")
                        subprocess.run(["poff", "roost-wan"], check=False)

            # 3. Clean up any stale configuration files starting with 10-, 20-, or 25-
            for filename in os.listdir(network_dir):
                if (filename.startswith("10-") or filename.startswith("20-") or filename.startswith("25-")) \
                        and (filename.endswith(".network") or filename.endswith(".netdev")):
                    if filename not in generated_files:
                        try:
                            os.remove(os.path.join(network_dir, filename))
                        except Exception as e:
                            print(f"Warning: Could not remove stale network config {filename}: {e}", file=sys.stderr)

            if os.getuid() == 0 and not self.mock:
                print("Restarting systemd-networkd service...")
                subprocess.run(["systemctl", "restart", "systemd-networkd"], check=True)
        except Exception as e:
            print(f"Error updating network interfaces: {e}", file=sys.stderr)

    def update_wifi_services(self):
        """Generates IWD Access Point configurations for wireless interfaces."""
        if not self._config.wifi:
            return

        iwd_dir = os.environ.get("ROOSTOS_IWD_DIR")
        if not iwd_dir:
            if self.mock:
                import tempfile
                iwd_dir = os.path.join(tempfile.gettempdir(), "iwd")
            else:
                iwd_dir = "/var/lib/iwd"

        try:
            os.makedirs(iwd_dir, exist_ok=True)
            print(f"Generating IWD AP configurations in {iwd_dir}...")
            
            # Map radios for quick lookup
            radios_map = {r.interface: r for r in self._config.wifi.radios}
            
            # Generate AP profile file for each access point
            for ap in self._config.wifi.access_points:
                if ap.interface:
                    iface_name = ap.interface
                elif ap.radio:
                    if ap.bridge == "br0":
                        iface_name = ap.radio
                    else:
                        iface_name = f"{ap.radio}_guest"
                else:
                    iface_name = "wlan0"

                ap_file = f"{iface_name}.ap"
                ap_path = os.path.join(iwd_dir, ap_file)
                
                radio_iface = ap.radio or ap.interface or "wlan0"
                radio = radios_map.get(radio_iface)
                
                with open(ap_path, "w") as f:
                    f.write("[General]\n")
                    f.write(f"Name={ap.ssid}\n")
                    f.write("Mode=ap\n")
                    
                    if radio:
                        if radio.channel != "auto":
                            f.write(f"Channel={radio.channel}\n")
                        if "5ghz" in radio.band.lower():
                            f.write("Band=5g\n")
                        elif "2.4ghz" in radio.band.lower():
                            f.write("Band=2.4g\n")
                    
                    f.write("\n[AP]\n")
                    if ap.security == "wpa3-sae":
                        f.write("Security=sae\n")
                    elif ap.security == "wpa2-psk":
                        f.write("Security=psk\n")
                    
                    f.write(f"Passphrase={ap.passphrase}\n")
                
                if os.getuid() == 0 and not self.mock:
                    if iface_name != radio_iface:
                        try:
                            subprocess.run(["ip", "link", "show", iface_name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        except subprocess.CalledProcessError:
                            print(f"Creating virtual wireless AP interface {iface_name} on {radio_iface}...")
                            subprocess.run(["iw", "dev", radio_iface, "interface", "add", iface_name, "type", "__ap"], check=True)
                            subprocess.run(["ip", "link", "set", iface_name, "up"], check=True)

            if os.getuid() == 0 and not self.mock:
                print("Restarting IWD service...")
                subprocess.run(["systemctl", "restart", "iwd"], check=True)
                
        except Exception as e:
            print(f"Error updating Wi-Fi services: {e}", file=sys.stderr)

    def update_dhcp_services(self):
        """Compiles the Kea DHCP4 configuration and restarts the kea-dhcp4-server service."""
        try:
            from roostos_engine.dhcp_manager import DHCPManager
            
            kea_conf_dir = os.environ.get("ROOSTOS_KEA_CONF_DIR")
            if kea_conf_dir:
                target_path = os.path.join(kea_conf_dir, "kea-dhcp4.conf")
            else:
                target_path = "/etc/kea/kea-dhcp4.conf"
            
            # If in mock mode, write to custom overridden path or temp dir
            if self.mock:
                if not kea_conf_dir:
                    target_path = os.path.join(tempfile.gettempdir(), "kea-dhcp4.conf")
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                manager = DHCPManager(self._config, target_path)
                manager.write_config()
                return

            # Attempt writing to standard /etc/kea/kea-dhcp4.conf path
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                manager = DHCPManager(self._config, target_path)
                manager.write_config()
            except OSError as e:
                print(f"Warning: Failed to write to {target_path} ({e}), falling back to temp file.", file=sys.stderr)
                target_path = os.path.join(tempfile.gettempdir(), "kea-dhcp4.conf")
                manager = DHCPManager(self._config, target_path)
                manager.write_config()
                return
            
            # Restart kea-dhcp4-server using systemctl if running as root
            if os.getuid() == 0:
                # Remove stale socket/lock files to prevent permission issues for the _kea user
                for stale_file in ["/run/kea/kea-dhcp4-ctrl.sock", "/run/kea/kea-dhcp4-ctrl.sock.lock"]:
                    try:
                        if os.path.exists(stale_file):
                            os.remove(stale_file)
                    except Exception as ex:
                        print(f"Warning: Could not remove stale file {stale_file}: {ex}", file=sys.stderr)

                print("Restarting kea-dhcp4-server service...")
                subprocess.run(["systemctl", "restart", "kea-dhcp4-server"], check=True)
        except Exception as e:
            print(f"Error updating DHCP services: {e}", file=sys.stderr)

    def update_qos_services(self):
        """Re-compiles and applies traffic shaping rules (tc/fq_codel)."""
        try:
            from roostos_engine.qos_manager import QoSManager
            active_leases = self.state_db.get_active_leases() if hasattr(self, "state_db") and self.state_db else []
            manager = QoSManager(self._config, mock=self.mock, active_leases=active_leases)
            manager.update_qos()
        except Exception as e:
            print(f"Error updating QoS services: {e}", file=sys.stderr)

    def sync_plugins(self):
        # For local plugin development: sync local ui.js assets directly if they exist
        local_plugins_dir = "/home/matt/source/github/mageos/roostos/plugins"
        if os.path.isdir(local_plugins_dir):
            for plugin in self._config.plugins:
                local_ui_file = os.path.join(local_plugins_dir, plugin.id, "ui.js")
                if os.path.isfile(local_ui_file):
                    assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
                    dest_dir = os.path.join(assets_dir, "plugins", plugin.id)
                    dest_file = os.path.join(dest_dir, "ui.js")
                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.copy2(local_ui_file, dest_file)
                        print(f"Developer sync: Copied local plugin UI for {plugin.id} to {dest_file}")
                    except Exception as e:
                        print(f"Failed to sync local UI file for {plugin.id}: {e}", file=sys.stderr)

        # Synchronize Docker containers for enabled plugins
        try:
            import docker
            client = docker.from_env()
        except Exception as e:
            print(f"Warning: Failed to initialize Docker client: {e}", file=sys.stderr)
            return

        # 1. Get currently running roostos containers
        try:
            existing_containers = client.containers.list(all=True, filters={"label": "org.roostos.managed=true"})
        except Exception as e:
            print(f"Warning: Failed to list Docker containers: {e}", file=sys.stderr)
            return

        # Compile list of active/desired plugins
        active_plugins = {p.id: p for p in self._config.plugins if p.enabled}
        
        # Stop and remove containers for disabled plugins
        for container in existing_containers:
            plugin_id = container.labels.get("org.roostos.plugin_id")
            if plugin_id not in active_plugins:
                print(f"Stopping and removing container: {container.name}")
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                except Exception as e:
                    print(f"Failed to remove container {container.name}: {e}", file=sys.stderr)

        # Start desired plugin containers
        for plugin_id, plugin in active_plugins.items():
            for c_cfg in plugin.containers:
                container_name = f"roostos-plugin-{plugin_id}-{c_cfg.name}"
                
                # Check if it already exists and is running
                running_container = next((c for c in existing_containers if c.name == container_name), None)
                if running_container:
                    if running_container.status != "running":
                        try:
                            running_container.start()
                        except Exception as e:
                            print(f"Failed to start container {container_name}: {e}", file=sys.stderr)
                    continue

                # Prepare port bindings
                ports_dict = {}
                for p in c_cfg.ports:
                    ports_dict[f"{p.container_port}/{p.protocol}"] = p.host_port

                # Prepare volumes
                volumes_dict = {}
                for v in c_cfg.volumes:
                    volumes_dict[v.host_path] = {"bind": v.container_path, "mode": v.mode}

                # Automatically mount D-Bus socket for the container to interact with the host system/session bus
                dbus_addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
                container_env = c_cfg.environment.copy()
                if dbus_addr:
                    container_env["DBUS_SESSION_BUS_ADDRESS"] = dbus_addr
                    if "path=" in dbus_addr:
                        parts = dbus_addr.split("path=")
                        socket_path = parts[1].split(",")[0]
                        if os.path.exists(socket_path):
                            volumes_dict[socket_path] = {"bind": socket_path, "mode": "rw"}
                else:
                    system_socket = "/var/run/dbus/system_bus_socket"
                    if os.path.exists(system_socket):
                        volumes_dict[system_socket] = {"bind": system_socket, "mode": "rw"}

                 # Start the container
                image_name = c_cfg.image
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

                print(f"Starting plugin container: {container_name} ({image_name})")
                try:
                    client.containers.run(
                        image_name,
                        name=container_name,
                        detach=True,
                        ports=ports_dict if plugin.network_mode != "host" else None,
                        volumes=volumes_dict,
                        environment=container_env,
                        network_mode=plugin.network_mode,
                        labels={
                            "org.roostos.managed": "true",
                            "org.roostos.plugin_id": plugin_id
                        },
                        restart_policy={"Name": "unless-stopped"}
                    )
                except Exception as e:
                    print(f"Failed to run container {container_name}: {e}", file=sys.stderr)

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
        return json.dumps(self._config.firewall.model_dump(exclude_none=True))

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

            schedules_config_obj = SchedulesConfig(
                firewall=FirewallSettings(
                    port_forwards=self._config.firewall.port_forwards,
                    rules=rules_list,
                    schedules=self._config.firewall.schedules
                )
            )
            self.repository.save_schedules_config(schedules_config_obj)
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

            schedules_config_obj = SchedulesConfig(
                firewall=FirewallSettings(
                    port_forwards=self._config.firewall.port_forwards,
                    rules=rules_list,
                    schedules=self._config.firewall.schedules
                )
            )
            self.repository.save_schedules_config(schedules_config_obj)
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

        if hasattr(self._config, "firewall") and self._config.firewall:
            for sched in self._config.firewall.schedules:
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
    parser = argparse.ArgumentParser(description="RoostOS Engine core daemon service")
    parser.add_argument("--config-dir", default="/etc/roostos", help="Path to split configurations folder")
    parser.add_argument("--session", action="store_true", help="Force connecting to Session D-Bus bus instead of System D-Bus")
    parser.add_argument("--mock", action="store_true", help="Force mock mode, bypassing system modifications")
    args = parser.parse_args()

    bus_type = BusType.SESSION if args.session else BusType.SYSTEM
    
    try:
        asyncio.run(start_daemon(args.config_dir, bus_type, args.mock))
    except KeyboardInterrupt:
        pass
    print("Daemon stopped cleanly.")

if __name__ == "__main__":
    main()
