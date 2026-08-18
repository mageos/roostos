import os
import re
import subprocess
from typing import List, Dict, Optional, Set
from roostos_engine.models.node import (
    DetectedHardwareInterface,
    InterfaceType,
    NodeConfig,
    NodeInterface,
)


class HardwareInspector:
    """Introspects host network adapters and identifies physical/virtual interfaces and deltas."""

    @staticmethod
    def inspect_network_interfaces(mock: bool = False) -> List[DetectedHardwareInterface]:
        """Scans local network interfaces and returns detailed hardware descriptors."""
        if mock or not os.path.exists("/sys/class/net"):
            return HardwareInspector._get_mock_interfaces()

        detected = []
        net_dir = "/sys/class/net"

        try:
            entries = os.listdir(net_dir)
        except Exception:
            return HardwareInspector._get_mock_interfaces()

        # Find wireless interfaces via iw if available
        wireless_devs = HardwareInspector._detect_wireless_devices()

        for name in entries:
            if name == "lo":
                continue  # Skip loopback

            dev_path = os.path.join(net_dir, name)
            mac = HardwareInspector._read_sysfs_file(os.path.join(dev_path, "address"))
            operstate = HardwareInspector._read_sysfs_file(os.path.join(dev_path, "operstate")) or "unknown"
            speed_str = HardwareInspector._read_sysfs_file(os.path.join(dev_path, "speed"))
            
            speed_mbps = None
            if speed_str and speed_str.isdigit() and int(speed_str) > 0:
                speed_mbps = int(speed_str)

            # Determine interface type
            iface_type = InterfaceType.ETHERNET
            is_wireless = False
            wireless_bands: List[str] = []

            if name in wireless_devs or os.path.exists(os.path.join(dev_path, "wireless")) or os.path.exists(os.path.join(dev_path, "phy80211")):
                iface_type = InterfaceType.WIFI_RADIO
                is_wireless = True
                wireless_bands = wireless_devs.get(name, ["2.4ghz", "5ghz"])
            elif os.path.exists(os.path.join(dev_path, "bridge")):
                iface_type = InterfaceType.BRIDGE
            elif "." in name or os.path.exists(os.path.join(dev_path, "link")):
                iface_type = InterfaceType.VLAN
            elif name.startswith("wwan") or name.startswith("cdc-wdm") or name.startswith("ppp"):
                iface_type = InterfaceType.CELLULAR
            elif "sfp" in name.lower() or name.startswith("sfp"):
                iface_type = InterfaceType.SFP

            # Read kernel driver
            driver = None
            device_symlink = os.path.join(dev_path, "device", "driver")
            if os.path.exists(device_symlink):
                try:
                    driver = os.path.basename(os.readlink(device_symlink))
                except Exception:
                    pass

            detected.append(
                DetectedHardwareInterface(
                    name=name,
                    mac_address=mac.lower() if mac else None,
                    type=iface_type,
                    speed_mbps=speed_mbps,
                    driver=driver,
                    operstate=operstate,
                    is_wireless=is_wireless,
                    wireless_bands=wireless_bands,
                )
            )

        return detected

    @staticmethod
    def detect_new_hardware(
        configured_node: Optional[NodeConfig],
        mock: bool = False
    ) -> List[DetectedHardwareInterface]:
        """Compares current physical adapters with configured interfaces on the node."""
        all_hardware = HardwareInspector.inspect_network_interfaces(mock=mock)
        if not configured_node or not configured_node.interfaces:
            return all_hardware

        configured_names = {iface.name for iface in configured_node.interfaces}
        configured_macs = {iface.mac_address.lower() for iface in configured_node.interfaces if iface.mac_address}

        newly_discovered = []
        for hw in all_hardware:
            # Check if this hardware is already registered by name or MAC
            by_name = hw.name in configured_names
            by_mac = hw.mac_address and hw.mac_address in configured_macs
            if not by_name and not by_mac:
                newly_discovered.append(hw)

        return newly_discovered

    @staticmethod
    def _read_sysfs_file(path: str) -> Optional[str]:
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _detect_wireless_devices() -> Dict[str, List[str]]:
        wireless = {}
        try:
            output = subprocess.check_output(["iw", "dev"], stderr=subprocess.DEVNULL, text=True)
            current_iface = None
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("Interface"):
                    current_iface = line.split()[1]
                    wireless[current_iface] = ["2.4ghz", "5ghz"]
        except Exception:
            pass
        return wireless

    @staticmethod
    def _get_mock_interfaces() -> List[DetectedHardwareInterface]:
        return [
            DetectedHardwareInterface(
                name="eth0",
                mac_address="52:54:00:12:34:56",
                type=InterfaceType.ETHERNET,
                speed_mbps=1000,
                driver="virtio_net",
                operstate="up",
                is_wireless=False,
                wireless_bands=[],
            ),
            DetectedHardwareInterface(
                name="eth1",
                mac_address="52:54:00:56:78:9a",
                type=InterfaceType.ETHERNET,
                speed_mbps=1000,
                driver="virtio_net",
                operstate="up",
                is_wireless=False,
                wireless_bands=[],
            ),
            DetectedHardwareInterface(
                name="wlan0",
                mac_address="a4:83:e7:99:88:77",
                type=InterfaceType.WIFI_RADIO,
                speed_mbps=866,
                driver="ath10k_pci",
                operstate="up",
                is_wireless=True,
                wireless_bands=["2.4ghz", "5ghz", "6ghz"],
            ),
        ]
