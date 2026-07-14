import os
import sys
import time
import datetime
import subprocess
from typing import Dict, Any, Optional
from fastapi import Depends

from roostos_engine.config import SystemConfig, SystemSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.services.base import get_repository, get_dbus_client

class SystemService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository), dbus: RoostClient = Depends(get_dbus_client)):
        self.repo = repo
        self.dbus = dbus
        self._last_traffic_stats: Dict[str, tuple] = {}
        self._last_traffic_time: float = 0.0

    async def get_system_config(self) -> Dict[str, Any]:
        config = self.repo.get_config()
        
        # 1. Uptime
        uptime_str = "Unknown"
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                uptime_str = str(datetime.timedelta(seconds=int(uptime_seconds)))
        except Exception:
            pass

        # 2. CPU Load & RAM Usage
        cpu_load = 0.0
        ram_usage = 0.0
        try:
            with open("/proc/loadavg", "r") as f:
                cpu_load = float(f.read().split()[0]) * 100.0
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
                mem_total = 0
                mem_available = 0
                for line in lines:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1])
                if mem_total > 0:
                    ram_usage = ((mem_total - mem_available) / mem_total) * 100.0
        except Exception:
            pass

        # 3. WAN & LAN gateway status/IPs
        wan_ip = "-"
        lan_ip = "-"
        if config.network:
            for iface in config.network.interfaces:
                if iface.role == "wan":
                    try:
                        import socket
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.connect(("8.8.8.8", 80))
                        wan_ip = s.getsockname()[0]
                        s.close()
                    except Exception:
                        wan_ip = "192.168.100.45 (mock)"
            for bridge in config.network.bridges:
                if bridge.name == "br0":
                    lan_ip = bridge.ip.split("/")[0]

        # 4. Running sidecars and active warnings
        warnings = []
        try:
            plugins = await self.dbus.get_plugins()
            for plugin in plugins:
                for container in plugin.get("containers", []):
                    status = container.get("status", "Missing")
                    if status in ["Stopped", "Errored", "Missing"]:
                        warnings.append(f"Plugin container '{container.get('name')}' is {status.upper()}")
        except Exception:
            pass

        # 5. Interface traffic rate computation
        rx_rate = 0
        tx_rate = 0
        try:
            wan_interface = next((iface.name for iface in config.network.interfaces if iface.role == "wan"), "eth0")
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
                for line in lines:
                    if wan_interface in line:
                        parts = line.split()
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        curr_time = time.time()
                        
                        prev = self._last_traffic_stats.get(wan_interface)
                        if prev and self._last_traffic_time > 0:
                            elapsed = curr_time - self._last_traffic_time
                            if elapsed > 0:
                                rx_rate = int((rx_bytes - prev[0]) / elapsed)
                                tx_rate = int((tx_bytes - prev[1]) / elapsed)
                        
                        self._last_traffic_stats[wan_interface] = (rx_bytes, tx_bytes)
                        self._last_traffic_time = curr_time
                        break
        except Exception:
            pass

        return {
            "hostname": config.system.hostname,
            "domain": config.system.domain,
            "timezone": config.system.timezone,
            "docker_registry": getattr(config.system, "docker_registry", ""),
            "stats": {
                "uptime": uptime_str,
                "cpu_load": cpu_load,
                "ram_usage": ram_usage,
                "wan_ip": wan_ip,
                "lan_ip": lan_ip,
                "warnings": warnings,
                "rx_rate": rx_rate,
                "tx_rate": tx_rate
            }
        }

    async def update_system_config(self, hostname: str, domain: str, timezone: str, docker_registry: Optional[str] = ""):
        config = self.repo.get_config()
        
        system_settings = SystemSettings(
            hostname=hostname,
            domain=domain,
            timezone=timezone,
            docker_registry=docker_registry
        )
        
        system_config_obj = SystemConfig(
            system=system_settings,
            users=config.users
        )
        self.repo.save_system_config(system_config_obj)
        await self.dbus.get_config()

    async def run_diagnostics(self) -> Dict[str, Any]:
        checks = []
        
        # 1. IPv4 Forwarding
        ip_forward_ok = False
        ip_forward_msg = ""
        try:
            with open("/proc/sys/net/ipv4/ip_forward", "r") as f:
                val = f.read().strip()
                if val == "1":
                    ip_forward_ok = True
                    ip_forward_msg = "IPv4 forwarding is enabled in the kernel."
                else:
                    ip_forward_msg = "IPv4 forwarding is disabled. LAN clients will not have internet access."
        except Exception as e:
            ip_forward_msg = f"Failed to check IPv4 forwarding: {e}"
        checks.append({"name": "IPv4 Packet Forwarding", "status": "PASS" if ip_forward_ok else "FAIL", "message": ip_forward_msg})

        # 2. nftables / NAT Masquerading
        nft_ok = False
        nft_msg = ""
        try:
            ruleset = subprocess.check_output(["nft", "list", "ruleset"], text=True)
            if "masquerade" in ruleset:
                nft_ok = True
                nft_msg = "NAT masquerading is active in nftables ruleset."
            else:
                nft_msg = "NAT masquerading is not active in nftables ruleset."
        except Exception as e:
            nft_msg = f"Failed to query nftables ruleset: {e}"
        checks.append({"name": "NAT Masquerading (nftables)", "status": "PASS" if nft_ok else "FAIL", "message": nft_msg})

        # 3. D-Bus Security Policy for DNSResolver
        dbus_ok = False
        dbus_msg = ""
        policy_path = "/etc/dbus-1/system.d/org.roostos.conf"
        if os.path.exists(policy_path):
            try:
                with open(policy_path, "r") as f:
                    content = f.read()
                    if "org.roostos.DNSResolver" in content and "allow own" in content:
                        dbus_ok = True
                        dbus_msg = "D-Bus security policy permits org.roostos.DNSResolver ownership."
                    else:
                        dbus_msg = "D-Bus policy configuration is missing the DNSResolver ownership allowance."
            except Exception as e:
                dbus_msg = f"Failed to read D-Bus policy file: {e}"
        else:
            dbus_msg = f"D-Bus policy file {policy_path} does not exist."
        checks.append({"name": "D-Bus DNSResolver Policy", "status": "PASS" if dbus_ok else "FAIL", "message": dbus_msg})

        # 4. AppArmor Exception for Kea DHCP Hook
        apparmor_ok = True
        apparmor_msg = "AppArmor is inactive or no policy exceptions are required."
        aa_path = "/etc/apparmor.d/local/usr.sbin.kea-dhcp4"
        if os.path.exists(aa_path):
            try:
                res = subprocess.run(["systemctl", "is-active", "--quiet", "apparmor"])
                if res.returncode == 0:
                    with open(aa_path, "r") as f:
                        content = f.read()
                        if "roost-dhcp-hook ux" in content:
                            apparmor_ok = True
                            apparmor_msg = "AppArmor Kea policy override hook exception is active."
                        else:
                            apparmor_ok = False
                            apparmor_msg = "AppArmor override file usr.sbin.kea-dhcp4 is missing the hook exception."
            except Exception as e:
                apparmor_msg = f"Failed to verify AppArmor status: {e}"
        checks.append({"name": "AppArmor DHCP Hook Exception", "status": "PASS" if apparmor_ok else "FAIL", "message": apparmor_msg})

        # 5. Kea DHCP Service Status
        kea_ok = False
        kea_msg = ""
        try:
            res = subprocess.run(["systemctl", "is-active", "--quiet", "kea-dhcp4-server"])
            if res.returncode == 0:
                kea_ok = True
                kea_msg = "Kea DHCP4 Server service is running."
            else:
                kea_msg = "Kea DHCP4 Server service is stopped or failed."
        except Exception as e:
            kea_msg = f"Failed to check Kea DHCP service status: {e}"
        checks.append({"name": "Kea DHCPv4 Daemon", "status": "PASS" if kea_ok else "FAIL", "message": kea_msg})

        # 6. Docker Daemon Status
        docker_ok = False
        docker_msg = ""
        try:
            res = subprocess.run(["systemctl", "is-active", "--quiet", "docker"])
            if res.returncode == 0:
                docker_ok = True
                docker_msg = "Docker Daemon service is running."
            else:
                docker_msg = "Docker Daemon service is stopped or failed."
        except Exception as e:
            docker_msg = f"Failed to check Docker service status: {e}"
        checks.append({"name": "Docker Daemon", "status": "PASS" if docker_ok else "FAIL", "message": docker_msg})

        # 7. WAN Gateway Connection Ping
        wan_ping_ok = False
        wan_ping_msg = ""
        try:
            res = subprocess.run(["ping", "-c", "1", "-W", "2", "1.1.1.1"], capture_output=True, text=True)
            if res.returncode == 0:
                wan_ping_ok = True
                wan_ping_msg = "Successfully pinged public target (1.1.1.1) over WAN."
            else:
                wan_ping_msg = "Failed to ping public target over WAN (connectivity issue)."
        except Exception as e:
            wan_ping_msg = f"Ping command execution failed: {e}"
        checks.append({"name": "WAN Internet Reachability", "status": "PASS" if wan_ping_ok else "FAIL", "message": wan_ping_msg})

        # 8. Kea run-script hook library existence
        hook_lib_ok = False
        hook_lib_msg = ""
        hook_lib_path = "/usr/lib/x86_64-linux-gnu/kea/hooks/libdhcp_run_script.so"
        hook_lib_path_arm = "/usr/lib/aarch64-linux-gnu/kea/hooks/libdhcp_run_script.so"
        if os.path.exists(hook_lib_path) or os.path.exists(hook_lib_path_arm):
            hook_lib_ok = True
            hook_lib_msg = "Kea run-script hook library (libdhcp_run_script.so) is installed."
        else:
            hook_lib_msg = "Kea run-script hook library is missing. Active leases list will not update. Install 'kea-hook-run-script' package."
        checks.append({"name": "Kea Run-Script Hook Library", "status": "PASS" if hook_lib_ok else "FAIL", "message": hook_lib_msg})

        overall_status = "PASS"
        if any(c["status"] == "FAIL" for c in checks):
            overall_status = "FAIL"
            
        return {
            "status": overall_status,
            "checks": checks
        }

    async def reboot_router(self):
        if not self.dbus.mock:
            subprocess.Popen(["sudo", "reboot"])
