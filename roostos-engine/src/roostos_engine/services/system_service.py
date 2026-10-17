import datetime
import os
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional

from roostos_engine.config import SystemConfig, SystemSettings
from roostos_engine.repository import ConfigRepository, YAMLConfigRepository, StagingConfigRepository
from roostos_engine.services.system_diagnostics import collect_firewall_blocks, run_system_diagnostics
from roostos_sdk.client import RoostClient


class SystemService:
    def __init__(self, repo: ConfigRepository, dbus: Optional[RoostClient] = None):
        self.repo = repo
        self.dbus = dbus
        self._last_traffic_stats: Dict[str, tuple] = {}
        self._last_traffic_time: float = 0.0

    def _is_mock_mode(self) -> bool:
        return (
            getattr(self.dbus, "mock", False)
            or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
            or not isinstance(self.repo, (YAMLConfigRepository, StagingConfigRepository))
        )

    def _detect_outbound_ip(self) -> Optional[str]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            ip_val = s.getsockname()[0]
            s.close()
            return ip_val
        except Exception:
            return None

    async def get_system_config(self) -> Dict[str, Any]:
        config = self.repo.get_config()
        is_mock = self._is_mock_mode()

        # 1. Read RoostOS version
        version = "Unknown"
        try:
            if os.path.exists("/etc/roostos/version"):
                with open("/etc/roostos/version", "r") as f:
                    version = f.read().strip()
            if not version or version == "Unknown":
                from roostos_web import __version__
                version = __version__
        except Exception:
            pass

        # 2. Uptime
        uptime_str = "Unknown"
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                uptime_str = str(datetime.timedelta(seconds=int(uptime_seconds)))
        except Exception:
            pass

        # 3. CPU Load & RAM Usage
        cpu_load = 0.0
        ram_usage = 0.0
        try:
            with open("/proc/loadavg", "r") as f:
                cpu_load = float(f.read().split()[0]) * 100.0
            with open("/proc/meminfo", "r") as f:
                mem_total = 0
                mem_available = 0
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1])
                if mem_total > 0:
                    ram_usage = ((mem_total - mem_available) / mem_total) * 100.0
        except Exception:
            pass

        # 4. WAN & LAN gateway status/IPs
        wan_ip = "-"
        lan_ip = "-"
        if config.network:
            for iface in getattr(config.network, "interfaces", []):
                role_val = getattr(iface, "role", None)
                ip_val = getattr(iface, "ip", None)
                if role_val == "wan" and isinstance(ip_val, str) and ip_val not in ("", "-", "dhcp"):
                    wan_ip = ip_val.split("/")[0]
                elif role_val == "lan" and lan_ip == "-" and isinstance(ip_val, str) and ip_val not in ("", "-", "dhcp"):
                    lan_ip = ip_val.split("/")[0]

            for bridge in getattr(config.network, "bridges", []):
                b_ip = getattr(bridge, "ip", None)
                if isinstance(b_ip, str) and b_ip and (bridge.name in ("br0", "br-lan") or lan_ip == "-"):
                    lan_ip = b_ip.split("/")[0]

        if wan_ip == "-":
            detected_ip = self._detect_outbound_ip()
            if detected_ip:
                wan_ip = detected_ip
            elif is_mock:
                wan_ip = "192.168.100.45 (mock)"

        if lan_ip == "-" and wan_ip != "-" and not wan_ip.endswith("(mock)"):
            lan_ip = wan_ip

        # 5. Running sidecars and active warnings
        warnings: List[str] = []
        try:
            if self.dbus:
                plugins = await self.dbus.get_plugins()
                for plugin in plugins:
                    for container in plugin.get("containers", []):
                        c_status = container.get("status", "Missing")
                        if c_status in ["Stopped", "Errored", "Missing"]:
                            warnings.append(f"Plugin container '{container.get('name')}' is {c_status.upper()}")
        except Exception:
            pass

        # 5b. Alert for unrecognized devices in active leases or active ARP cache
        try:
            registered_macs = {d.mac.lower() for d in config.devices}
            seen_macs = set()
            all_observed = []

            wan_interfaces = set()
            try:
                for interface in config.network.interfaces:
                    if getattr(interface, "role", None) == "wan":
                        wan_interfaces.add(interface.name)
                        if interface.vlan_tag:
                            wan_interfaces.add(f"{interface.name}.{interface.vlan_tag}")
            except Exception:
                pass

            if os.path.exists("/proc/net/arp"):
                with open("/proc/net/arp", "r") as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 6:
                            ip, flags, mac, iface = parts[0], parts[2], parts[3].lower(), parts[5]
                            is_wan = iface in wan_interfaces or iface.startswith("ppp")
                            if flags != "0x0" and mac != "00:00:00:00:00:00" and ":" in mac and not is_wan:
                                if mac not in seen_macs:
                                    seen_macs.add(mac)
                                    all_observed.append({"mac": mac, "ip": ip, "hostname": "Active IP client"})

            if not all_observed and (getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK") == "1"):
                for d in [
                    {"mac": "a4:83:e7:12:34:56", "ip": "192.168.1.10", "hostname": "Mom's Laptop"},
                    {"mac": "4c:32:75:98:76:54", "ip": "192.168.1.50", "hostname": "Alice's iPad"},
                ]:
                    mac = d["mac"].lower()
                    if mac not in seen_macs:
                        seen_macs.add(mac)
                        all_observed.append(d)

            if self.dbus:
                leases = await self.dbus.get_active_leases()
                for l in leases:
                    mac = l.get("mac", "").lower()
                    if mac and mac not in seen_macs:
                        seen_macs.add(mac)
                        all_observed.append({
                            "mac": mac,
                            "ip": l.get("ip", ""),
                            "hostname": l.get("hostname", "Unknown")
                        })

            for device in all_observed:
                mac = device["mac"]
                if mac not in registered_macs:
                    hostname = device.get("hostname") or "Unknown"
                    ip = device.get("ip", "")
                    ip_str = f" ({ip})" if ip else ""
                    warnings.append(f"Unrecognized device connected to network: {hostname}{ip_str} [MAC: {mac.upper()}]")
        except Exception:
            pass

        # 6. Interface traffic rate computation
        rx_rate = 0
        tx_rate = 0
        try:
            wan_interface = next(
                (iface.name for iface in config.network.interfaces if getattr(iface, "role", None) == "wan"),
                None
            )
            with open("/proc/net/dev", "r") as f:
                for line in f.readlines()[2:]:
                    parts = line.replace(":", " ").split()
                    if not parts:
                        continue
                    iface_name = parts[0]
                    if iface_name == "lo":
                        continue
                    if wan_interface and iface_name != wan_interface:
                        continue
                    rx_bytes, tx_bytes = int(parts[1]), int(parts[9])
                    curr_time = time.time()
                    prev = self._last_traffic_stats.get(iface_name)
                    if prev and self._last_traffic_time > 0:
                        elapsed = curr_time - self._last_traffic_time
                        if elapsed > 0:
                            rx_rate = max(0, int((rx_bytes - prev[0]) / elapsed))
                            tx_rate = max(0, int((tx_bytes - prev[1]) / elapsed))
                    self._last_traffic_stats[iface_name] = (rx_bytes, tx_bytes)
                    self._last_traffic_time = curr_time
                    break
        except Exception:
            pass

        stats = {
            "uptime": uptime_str,
            "cpu_load": cpu_load,
            "ram_usage": ram_usage,
            "wan_ip": wan_ip,
            "lan_ip": lan_ip,
            "warnings": warnings,
            "rx_rate": rx_rate,
            "tx_rate": tx_rate,
        }
        response = {
            "hostname": config.system.hostname,
            "domain": config.system.domain,
            "timezone": config.system.timezone,
            "docker_registry": getattr(config.system, "docker_registry", ""),
            "version": version,
            "stats": stats,
        }
        response.update(stats)
        return response

    async def update_system_config(self, hostname: str, domain: str, timezone: str, docker_registry: Optional[str] = "") -> None:
        config = self.repo.get_config()
        system_settings = SystemSettings(
            hostname=hostname,
            domain=domain,
            timezone=timezone,
            docker_registry=docker_registry,
        )
        self.repo.save_system_config(SystemConfig(system=system_settings, users=config.users))
        if self.dbus:
            try:
                await self.dbus.get_config()
            except Exception:
                pass

    async def run_diagnostics(self) -> Dict[str, Any]:
        return run_system_diagnostics()

    async def reboot_router(self) -> None:
        if self.dbus and not getattr(self.dbus, "mock", False):
            subprocess.Popen(["sudo", "reboot"])

    async def get_services_status(self) -> List[Dict[str, str]]:
        is_mock = getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
        services = {
            "roostd": ("RoostOS Engine Daemon", "roostos-engine.service"),
            "roostos-node": ("RoostOS Node Agent", "roostos-node.service"),
            "roostos-web": ("RoostOS Web Console", "roostos-node.service"),
            "systemd-networkd": ("Systemd Network Manager", "systemd-networkd.service"),
            "kea": ("Kea DHCPv4 Server", "kea-dhcp4-server.service"),
            "iwd": ("iwd Wireless Daemon", "iwd.service"),
            "docker": ("Docker Container Engine", "docker.service"),
        }
        res: List[Dict[str, str]] = []
        for key, (display_name, service_name) in services.items():
            if is_mock:
                active_state = "inactive" if key == "iwd" else "active"
                sub_state = "dead" if key == "iwd" else "running"
                res.append({"id": key, "name": display_name, "service": service_name, "status": active_state, "substate": sub_state})
                continue
            try:
                cmd = ["systemctl", "show", service_name, "--property=ActiveState,SubState"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                active_state, sub_state = "unknown", "unknown"
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if line.startswith("ActiveState="):
                            active_state = line.split("=", 1)[1]
                        elif line.startswith("SubState="):
                            sub_state = line.split("=", 1)[1]
                res.append({"id": key, "name": display_name, "service": service_name, "status": active_state, "substate": sub_state})
            except Exception as e:
                res.append({"id": key, "name": display_name, "service": service_name, "status": "error", "substate": str(e)})
        return res

    async def get_firewall_blocks(self, limit: int = 50) -> List[Dict[str, Any]]:
        return collect_firewall_blocks(is_mock=self._is_mock_mode(), limit=limit)
