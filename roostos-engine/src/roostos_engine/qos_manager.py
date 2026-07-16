import os
import sys
import subprocess
from typing import List, Dict, Any, Optional
from roostos_engine.config import RoostConfig

class QoSManager:
    """Manages Linux Traffic Control (tc) for bandwidth shaping and QoS prioritization."""

    def __init__(self, config: RoostConfig, mock: bool = False, active_leases: Optional[List[Dict[str, Any]]] = None):
        self.config = config
        self.mock = mock
        self.active_leases = active_leases or []

    def _get_wan_interface(self) -> str:
        """Locates active WAN interface name. Defaults to 'eth0'."""
        if hasattr(self.config, "network") and self.config.network:
            for interface in self.config.network.interfaces:
                if interface.network == "wan":
                    return interface.name
        return "eth0"

    def _get_lan_interfaces(self) -> List[str]:
        """Locates active LAN interfaces/bridges."""
        lan_ifs = []
        if hasattr(self.config, "network") and self.config.network:
            for bridge in self.config.network.bridges:
                lan_ifs.append(bridge.name)
        if not lan_ifs:
            lan_ifs = ["br0"]
        return lan_ifs

    def _resolve_device_ip(self, mac: str, static_ip: Optional[str]) -> Optional[str]:
        """Resolves the current IP address of a device by MAC address."""
        if static_ip:
            if "/" in static_ip:
                return static_ip.split("/")[0]
            return static_ip
        
        normalized_mac = mac.lower().replace("-", ":")
        for lease in self.active_leases:
            lease_mac = lease.get("mac", "").lower().replace("-", ":")
            if lease_mac == normalized_mac and lease.get("ip"):
                return lease.get("ip")
        return None

    def execute_cmd(self, args: List[str]) -> None:
        """Executes a system command or prints it in mock/dev mode."""
        cmd_str = " ".join(args)
        if self.mock:
            print(f"[QoS MOCK] Executing command: {cmd_str}")
            return

        if os.getuid() != 0:
            print(f"Warning: Cannot run tc command (not root): {cmd_str}", file=sys.stderr)
            return

        try:
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            # Silence expected errors (like trying to delete a qdisc that doesn't exist yet)
            if "delete" not in args:
                print(f"Warning: QoS command failed: {cmd_str} ({e})", file=sys.stderr)

    def update_qos(self) -> None:
        """Configures traffic shaping on WAN (upload) and LAN (download) interfaces."""
        wan_if = self._get_wan_interface()
        lan_ifs = self._get_lan_interfaces()

        # 1. Clear any existing root disciplines on WAN and LANs
        self.execute_cmd(["tc", "qdisc", "del", "dev", wan_if, "root"])
        for lan in lan_ifs:
            self.execute_cmd(["tc", "qdisc", "del", "dev", lan, "root"])

        qos_settings = None
        if hasattr(self.config, "network") and self.config.network and self.config.network.qos:
            qos_settings = self.config.network.qos

        if not qos_settings or not qos_settings.enabled:
            print("QoS is disabled. Traffic shaping cleared.")
            return

        print(f"Applying QoS traffic shaping. WAN: {wan_if}, LANs: {lan_ifs}")

        # 2. Configure WAN Egress (Upload Shaping)
        # Use HTB (Hierarchical Token Bucket) with fq_codel leaves
        wan_rate = qos_settings.wan_upload_kbps or 1000000  # Default 1Gbps if unspecified
        
        self.execute_cmd(["tc", "qdisc", "add", "dev", wan_if, "root", "handle", "1:", "htb", "default", "12"])
        self.execute_cmd(["tc", "class", "add", "dev", wan_if, "parent", "1:", "classid", "1:1", "htb", "rate", f"{wan_rate}kbit"])
        
        # Class 1:10 - High Priority (VoIP / Gaming tags)
        # Class 1:12 - Default Class
        self.execute_cmd(["tc", "class", "add", "dev", wan_if, "parent", "1:1", "classid", "1:10", "htb", "rate", f"{int(wan_rate * 0.3)}kbit", "ceil", f"{wan_rate}kbit", "prio", "1"])
        self.execute_cmd(["tc", "qdisc", "add", "dev", wan_if, "parent", "1:10", "handle", "10:", "fq_codel"])

        self.execute_cmd(["tc", "class", "add", "dev", wan_if, "parent", "1:1", "classid", "1:12", "htb", "rate", f"{int(wan_rate * 0.7)}kbit", "ceil", f"{wan_rate}kbit", "prio", "2"])
        self.execute_cmd(["tc", "qdisc", "add", "dev", wan_if, "parent", "1:12", "handle", "12:", "fq_codel"])

        # 3. Configure LAN Egress (Download Shaping)
        # We set up HTB root classes on LAN bridges to shape download limits per local IP
        for lan in lan_ifs:
            lan_rate = qos_settings.wan_download_kbps or 1000000
            self.execute_cmd(["tc", "qdisc", "add", "dev", lan, "root", "handle", "1:", "htb", "default", "12"])
            self.execute_cmd(["tc", "class", "add", "dev", lan, "parent", "1:", "classid", "1:1", "htb", "rate", f"{lan_rate}kbit"])
            self.execute_cmd(["tc", "class", "add", "dev", lan, "parent", "1:1", "classid", "1:12", "htb", "rate", f"{lan_rate}kbit", "prio", "2"])
            self.execute_cmd(["tc", "qdisc", "add", "dev", lan, "parent", "1:12", "handle", "12:", "fq_codel"])

        # 4. Map Prioritized tags
        # If device matches prioritized tag, direct its traffic to Class 1:10
        # Iterate through registered devices to apply tag priority and individual caps
        tag_priorities = set(qos_settings.prioritize_tags)
        
        class_id_counter = 100
        for device in getattr(self.config, "devices", []):
            device_ip = self._resolve_device_ip(device.mac, device.static_ip)
            if not device_ip:
                continue

            # Prioritize tags: map to high-priority WAN class
            has_priority_tag = any(t in tag_priorities for t in device.tags)
            if has_priority_tag:
                # Add filter on WAN egress (Upload)
                self.execute_cmd([
                    "tc", "filter", "add", "dev", wan_if, "protocol", "ip",
                    "parent", "1:", "prio", "1", "u32", "match", "ip", "src", device_ip,
                    "flowid", "1:10"
                ])

            # Apply individual bandwidth limit classes if defined
            if device.max_upload_kbps:
                cid = f"1:{class_id_counter}"
                self.execute_cmd([
                    "tc", "class", "add", "dev", wan_if, "parent", "1:1", "classid", cid,
                    "htb", "rate", f"{device.max_upload_kbps}kbit", "ceil", f"{device.max_upload_kbps}kbit"
                ])
                self.execute_cmd(["tc", "qdisc", "add", "dev", wan_if, "parent", cid, "handle", f"{class_id_counter}:", "fq_codel"])
                self.execute_cmd([
                    "tc", "filter", "add", "dev", wan_if, "protocol", "ip",
                    "parent", "1:", "prio", "2", "u32", "match", "ip", "src", device_ip,
                    "flowid", cid
                ])
                class_id_counter += 1

            if device.max_download_kbps:
                for lan in lan_ifs:
                    cid = f"1:{class_id_counter}"
                    self.execute_cmd([
                        "tc", "class", "add", "dev", lan, "parent", "1:1", "classid", cid,
                        "htb", "rate", f"{device.max_download_kbps}kbit", "ceil", f"{device.max_download_kbps}kbit"
                    ])
                    self.execute_cmd(["tc", "qdisc", "add", "dev", lan, "parent", cid, "handle", f"{class_id_counter}:", "fq_codel"])
                    self.execute_cmd([
                        "tc", "filter", "add", "dev", lan, "protocol", "ip",
                        "parent", "1:", "prio", "2", "u32", "match", "ip", "dst", device_ip,
                        "flowid", cid
                    ])
                class_id_counter += 1
