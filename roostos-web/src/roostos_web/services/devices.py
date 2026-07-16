from typing import List, Dict, Any
from fastapi import Depends

from roostos_engine.config import DevicesConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.services.base import get_repository, get_dbus_client

class DeviceService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository), dbus: RoostClient = Depends(get_dbus_client)):
        self.repo = repo
        self.dbus = dbus

    def get_devices_config(self) -> DevicesConfig:
        config = self.repo.get_config()
        return DevicesConfig(
            people=config.people,
            buildings=config.buildings,
            rooms=config.rooms,
            devices=config.devices
        )

    def save_devices_config(self, devices_config: DevicesConfig):
        self.repo.save_devices_config(devices_config)

    async def get_active_leases(self) -> List[Dict[str, Any]]:
        try:
            return await self.dbus.get_active_leases()
        except Exception:
            return []

    def get_active_arp(self) -> List[Dict[str, Any]]:
        import os
        devices = []
        try:
            if os.path.exists("/proc/net/arp"):
                with open("/proc/net/arp", "r") as f:
                    lines = f.readlines()
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 6:
                            ip = parts[0]
                            flags = parts[2]
                            mac = parts[3].lower()
                            iface = parts[5]
                            if flags != "0x0" and mac != "00:00:00:00:00:00" and ":" in mac:
                                devices.append({
                                    "ip": ip,
                                    "mac": mac,
                                    "interface": iface
                                })
        except Exception:
            pass

        # Fallback mock data in case of development/mock mode or no host devices found
        if not devices:
            is_mock = getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
            if is_mock:
                devices = [
                    {"ip": "192.168.1.10", "mac": "a4:83:e7:12:34:56", "interface": "br0"},
                    {"ip": "192.168.1.50", "mac": "4c:32:75:98:76:54", "interface": "br0"}
                ]
        return devices

    async def trigger_config_reload(self):
        await self.dbus.get_config()
