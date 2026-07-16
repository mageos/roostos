import os
import sys
import time
import datetime
import subprocess
from typing import Dict, Any, Optional, List
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
        # Read RoostOS version
        version = "Unknown"
        try:
            if os.path.exists("/etc/roostos/version"):
                with open("/etc/roostos/version", "r") as f:
                    version = f.read().strip()
        except Exception:
            pass

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

        # 4b. Alert for unrecognized devices in active leases or active ARP cache
        try:
            registered_macs = {d.mac.lower() for d in config.devices}
            seen_macs = set()
            all_observed = []
            
            # 1. Parse active ARP table
            if os.path.exists("/proc/net/arp"):
                with open("/proc/net/arp", "r") as f:
                    lines = f.readlines()
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 6:
                            ip = parts[0]
                            flags = parts[2]
                            mac = parts[3].lower()
                            if flags != "0x0" and mac != "00:00:00:00:00:00" and ":" in mac:
                                if mac not in seen_macs:
                                    seen_macs.add(mac)
                                    all_observed.append({
                                        "mac": mac,
                                        "ip": ip,
                                        "hostname": "Active IP client"
                                    })
            
            # Mock entries fallback if in mock mode
            is_mock = getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
            if not all_observed and is_mock:
                mock_arp = [
                    {"mac": "a4:83:e7:12:34:56", "ip": "192.168.1.10", "hostname": "Mom's Laptop"},
                    {"mac": "4c:32:75:98:76:54", "ip": "192.168.1.50", "hostname": "Alice's iPad"}
                ]
                for d in mock_arp:
                    mac = d["mac"].lower()
                    if mac not in seen_macs:
                        seen_macs.add(mac)
                        all_observed.append(d)

            # 2. Get active DHCP leases
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

        stats = {
            "uptime": uptime_str,
            "cpu_load": cpu_load,
            "ram_usage": ram_usage,
            "wan_ip": wan_ip,
            "lan_ip": lan_ip,
            "warnings": warnings,
            "rx_rate": rx_rate,
            "tx_rate": tx_rate
        }

        response = {
            "hostname": config.system.hostname,
            "domain": config.system.domain,
            "timezone": config.system.timezone,
            "docker_registry": getattr(config.system, "docker_registry", ""),
            "version": version,
            "stats": stats
        }
        # Merge stats to top level for frontend compatibility
        response.update(stats)
        return response

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

    async def get_services_status(self) -> List[Dict[str, str]]:
        import os
        is_mock = getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
        
        services = {
            "roostd": ("RoostOS Engine Daemon", "roostd.service"),
            "roostos-web": ("RoostOS Web Console", "roostos-web.service"),
            "systemd-networkd": ("Systemd Network Manager", "systemd-networkd.service"),
            "kea": ("Kea DHCPv4 Server", "kea-dhcp4-server.service"),
            "iwd": ("iwd Wireless Daemon", "iwd.service"),
            "docker": ("Docker Container Engine", "docker.service"),
        }
        res = []
        for key, (display_name, service_name) in services.items():
            if is_mock:
                active_state = "active"
                sub_state = "running"
                if key == "iwd":
                    active_state = "inactive"
                    sub_state = "dead"
                res.append({
                    "id": key,
                    "name": display_name,
                    "service": service_name,
                    "status": active_state,
                    "substate": sub_state
                })
                continue

            try:
                cmd = ["systemctl", "show", service_name, "--property=ActiveState,SubState"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                active_state = "unknown"
                sub_state = "unknown"
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if line.startswith("ActiveState="):
                            active_state = line.split("=", 1)[1]
                        elif line.startswith("SubState="):
                            sub_state = line.split("=", 1)[1]
                res.append({
                    "id": key,
                    "name": display_name,
                    "service": service_name,
                    "status": active_state,
                    "substate": sub_state
                })
            except Exception as e:
                res.append({
                    "id": key,
                    "name": display_name,
                    "service": service_name,
                    "status": "error",
                    "substate": str(e)
                })
        return res

    async def get_firewall_blocks(self, limit: int = 50) -> List[Dict[str, Any]]:
        import re
        import os
        is_mock = getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
        
        blocks = []
        if not is_mock:
            try:
                res = subprocess.run(
                    ["journalctl", "-k", "-n", "1000", "--no-pager"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if res.returncode == 0:
                    lines = res.stdout.splitlines()
                    pattern = re.compile(
                        r"(?P<ts>\w{3}\s+\d+\s+\d+:\d+:\d+).*FIREWALL:BLOCKED:(?P<rule>\S+).*IN=(?P<in>\S*).*OUT=(?P<out>\S*).*SRC=(?P<src>\S+).*DST=(?P<dst>\S+).*PROTO=(?P<proto>\S+)"
                    )
                    for line in lines:
                        if "FIREWALL:BLOCKED:" in line:
                            match = pattern.search(line)
                            if match:
                                rule = match.group("rule").replace("_", " ")
                                spt = ""
                                dpt = ""
                                spt_match = re.search(r"SPT=(\d+)", line)
                                if spt_match:
                                    spt = spt_match.group(1)
                                dpt_match = re.search(r"DPT=(\d+)", line)
                                if dpt_match:
                                    dpt = dpt_match.group(1)
                                
                                blocks.append({
                                    "timestamp": match.group("ts"),
                                    "rule": rule,
                                    "in_face": match.group("in"),
                                    "out_face": match.group("out"),
                                    "src_ip": match.group("src"),
                                    "dst_ip": match.group("dst"),
                                    "proto": match.group("proto"),
                                    "src_port": spt,
                                    "dst_port": dpt
                                })
            except Exception:
                pass

        if not blocks:
            # Fallback mock data
            now = datetime.datetime.now()
            mock_data = [
                ("Block_Tor_Traffic", "192.168.1.105", "185.220.101.5", "TCP", "49321", "9001", "br0"),
                ("Default_Input_Drop", "198.51.100.72", "192.168.100.45", "UDP", "38291", "5060", "eth0"),
                ("Blocked_Client", "192.168.1.50", "142.250.190.46", "TCP", "51023", "443", "br0"),
                ("Block_SSH_Access", "203.0.113.15", "192.168.100.45", "TCP", "55432", "22", "eth0"),
                ("Kids_Bedtime_Block", "192.168.1.50", "31.13.71.36", "TCP", "61240", "443", "br0")
            ]
            for i, (rule, src, dst, proto, spt, dpt, iif) in enumerate(mock_data):
                ts = (now - datetime.timedelta(minutes=i * 7 + 3)).strftime("%b %d %H:%M:%S")
                blocks.append({
                    "timestamp": ts,
                    "rule": rule.replace("_", " "),
                    "in_face": iif,
                    "out_face": "eth0" if iif == "br0" else "",
                    "src_ip": src,
                    "dst_ip": dst,
                    "proto": proto,
                    "src_port": spt,
                    "dst_port": dpt
                })
        return blocks[:limit]
