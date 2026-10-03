"""System environment and hardware inspector for RoostOS."""

import os
import platform
import shutil
import subprocess
from typing import List, Optional, Tuple

from roostos_cli.models import InterfaceInfo, SystemEnvironment, NodeRole


class EnvironmentInspector:
    """Introspects host hardware, physical network interfaces, and chassis type."""

    @classmethod
    def inspect(cls, mock_data: Optional[SystemEnvironment] = None) -> SystemEnvironment:
        """Inspects current host environment or returns mock data if provided."""
        if mock_data:
            return mock_data

        arch = platform.machine().lower()
        cpu_cores = os.cpu_count() or 1
        mem_total, mem_free = cls._read_memory()
        disk_total, disk_free = cls._read_disk_space()
        interfaces = cls._scan_interfaces()
        is_laptop = cls._check_is_laptop()

        env = SystemEnvironment(
            arch=arch,
            cpu_cores=cpu_cores,
            memory_total_mb=mem_total,
            memory_free_mb=mem_free,
            disk_total_gb=disk_total,
            disk_free_gb=disk_free,
            interfaces=interfaces,
            is_laptop=is_laptop,
        )

        role, reason = cls.recommend_role(env)
        env.recommended_role = role
        env.recommendation_reason = reason
        return env

    @classmethod
    def recommend_role(cls, env: SystemEnvironment) -> Tuple[NodeRole, str]:
        """Derives the most appropriate default role based on hardware topology."""
        if env.is_laptop:
            return (
                NodeRole.WORKSTATION,
                "Detected laptop form factor (battery/chassis). Recommended: Client Workstation."
            )

        physical_eth = [
            i for i in env.interfaces
            if not i.is_wireless and i.name != "lo"
        ]
        has_existing_gateway = len(env.discovered_gateways) > 0

        # Dedicated Edge Gateway: Low RAM (<= 2GB) and multiple physical ethernet ports
        if len(physical_eth) >= 2 and env.memory_total_mb <= 2500:
            return (
                NodeRole.GATEWAY,
                f"Detected {len(physical_eth)} Ethernet interfaces and {env.memory_total_mb}MB RAM. "
                "Optimal for dedicated Edge Gateway Router."
            )

        # Standalone All-in-One: Multi-NIC and sufficient RAM
        if len(physical_eth) >= 2 and not has_existing_gateway:
            return (
                NodeRole.STANDALONE,
                f"Detected {len(physical_eth)} Ethernet interfaces and {env.memory_total_mb}MB RAM. "
                "Capable of running full Standalone Router & Controller stack."
            )

        # Controller / App Server: Single NIC, decent RAM, or existing Gateway present
        if env.memory_total_mb >= 3500:
            return (
                NodeRole.CONTROLLER,
                f"Detected {env.memory_total_mb}MB RAM suitable for containerized controller workloads."
            )

        if len(physical_eth) >= 2:
            return NodeRole.GATEWAY, f"Detected {len(physical_eth)} Ethernet interfaces for routing."

        return NodeRole.COMPUTE, "Detected single interface. Recommended as a Compute/Application node."

    @staticmethod
    def _read_memory() -> Tuple[int, int]:
        """Reads total and available memory in MB from /proc/meminfo."""
        total_mb, free_mb = 1024, 512
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                for line in lines:
                    if line.startswith("MemTotal:"):
                        total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        free_mb = int(line.split()[1]) // 1024
            except Exception:
                pass
        return total_mb, free_mb

    @staticmethod
    def _read_disk_space() -> Tuple[float, float]:
        """Reads total and free disk space on root in GB."""
        try:
            stat = shutil.disk_usage("/")
            total_gb = round(stat.total / (1024 ** 3), 1)
            free_gb = round(stat.free / (1024 ** 3), 1)
            return total_gb, free_gb
        except Exception:
            return 16.0, 8.0

    @classmethod
    def _scan_interfaces(cls) -> List[InterfaceInfo]:
        """Discovers physical and wireless network interfaces from sysfs."""
        results: List[InterfaceInfo] = []
        net_dir = "/sys/class/net"
        if not os.path.exists(net_dir):
            return [
                InterfaceInfo(name="eth0", operstate="up", speed_mbps=1000),
                InterfaceInfo(name="eth1", operstate="down", speed_mbps=1000),
            ]

        try:
            entries = os.listdir(net_dir)
        except Exception:
            return results

        for name in entries:
            if name == "lo" or name.startswith(("veth", "br", "docker", "virbr", "tap", "tun")):
                continue

            dev_path = os.path.join(net_dir, name)
            mac = cls._read_file(os.path.join(dev_path, "address"))
            operstate = cls._read_file(os.path.join(dev_path, "operstate")) or "unknown"
            speed_str = cls._read_file(os.path.join(dev_path, "speed"))
            speed = int(speed_str) if speed_str and speed_str.isdigit() and int(speed_str) > 0 else None

            is_wireless = (
                os.path.exists(os.path.join(dev_path, "wireless")) or
                os.path.exists(os.path.join(dev_path, "phy80211"))
            )

            driver = None
            driver_link = os.path.join(dev_path, "device", "driver")
            if os.path.exists(driver_link):
                try:
                    driver = os.path.basename(os.readlink(driver_link))
                except Exception:
                    pass

            results.append(InterfaceInfo(
                name=name,
                mac_address=mac.lower() if mac else None,
                operstate=operstate,
                speed_mbps=speed,
                is_wireless=is_wireless,
                driver=driver,
            ))

        return sorted(results, key=lambda x: x.name)

    @staticmethod
    def _check_is_laptop() -> bool:
        """Determines if the system is a portable laptop."""
        # 1. Check for battery
        power_supply = "/sys/class/power_supply"
        if os.path.exists(power_supply):
            try:
                for entry in os.listdir(power_supply):
                    if entry.startswith(("BAT", "battery")):
                        return True
            except Exception:
                pass

        # 2. Check DMI chassis type
        chassis_file = "/sys/devices/virtual/dmi/id/chassis_type"
        if os.path.exists(chassis_file):
            try:
                with open(chassis_file, "r") as f:
                    chassis_id = f.read().strip()
                # 8: Portable, 9: Laptop, 10: Notebook, 11: Handheld, 14: Sub-notebook, 31: Convertible, 32: Detachable
                if chassis_id in {"8", "9", "10", "11", "14", "31", "32"}:
                    return True
            except Exception:
                pass

        return False

    @staticmethod
    def _read_file(path: str) -> Optional[str]:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None
