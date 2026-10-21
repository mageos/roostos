"""Shared Device, People, and Topology domain service for RoostOS."""

import os
from typing import List, Dict, Any, Optional
from roostos_engine.config import (
    DevicesConfig,
    DeviceConfig,
    PersonConfig,
    BuildingConfig,
    RoomConfig,
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class DeviceService:
    """Application service for managing registered devices, household members, and locations."""

    def __init__(self, repo: ConfigRepository, dbus: RoostClient) -> None:
        self.repo = repo
        self.dbus = dbus

    def get_devices_config(self) -> DevicesConfig:
        config = self.repo.get_config()
        return DevicesConfig(
            people=config.people,
            buildings=config.buildings,
            rooms=config.rooms,
            devices=config.devices,
        )

    def save_devices_config(self, devices_config: DevicesConfig) -> None:
        self.repo.save_devices_config(devices_config)

    def register_device(
        self,
        mac: str,
        name: str,
        owner: str = "",
        location: str = "",
        tags: Optional[List[str]] = None,
        static_ip: str = "",
        upnp_trusted: bool = False,
        max_upload_kbps: Optional[int] = None,
        max_download_kbps: Optional[int] = None,
        hostname: Optional[str] = None,
    ) -> DeviceConfig:
        """Registers or updates a device profile, validating linkages and persisting via repository."""
        config = self.get_devices_config()
        norm_mac = DeviceConfig.normalize_mac(mac)
        tags_list = tags or []

        if owner and not any(p.id == owner for p in config.people):
            raise ValueError(f"Owner '{owner}' does not exist.")
        if location and not any(r.id == location for r in config.rooms):
            raise ValueError(f"Location '{location}' does not exist.")

        device = next((d for d in config.devices if d.mac == norm_mac), None)
        if device:
            device.name = name
            if hostname:
                device.hostname = hostname
            device.owner = owner if owner else None
            device.location = location if location else None
            device.tags = tags_list
            device.static_ip = static_ip if static_ip else None
            device.upnp_trusted = upnp_trusted
            device.max_upload_kbps = max_upload_kbps
            device.max_download_kbps = max_download_kbps
            target_device = device
        else:
            target_device = DeviceConfig(
                mac=norm_mac,
                name=name,
                hostname=hostname,
                owner=owner if owner else None,
                location=location if location else None,
                tags=tags_list,
                static_ip=static_ip if static_ip else None,
                upnp_trusted=upnp_trusted,
                max_upload_kbps=max_upload_kbps,
                max_download_kbps=max_download_kbps,
            )
            config.devices.append(target_device)

        self.save_devices_config(config)
        return target_device

    def delete_device(self, mac: str) -> bool:
        """Deregisters a device by MAC address."""
        config = self.get_devices_config()
        norm_mac = DeviceConfig.normalize_mac(mac)
        original_len = len(config.devices)
        config.devices = [d for d in config.devices if d.mac != norm_mac]
        if len(config.devices) == original_len:
            return False
        self.save_devices_config(config)
        return True

    def register_person(
        self,
        name: str,
        avatar: str = "",
        role: str = "family_member",
        notes: str = "",
    ) -> PersonConfig:
        """Registers a household person profile."""
        config = self.get_devices_config()
        clean_id = name.lower().replace(" ", "-")
        existing_ids = {p.id for p in config.people}
        person_id = clean_id
        counter = 1
        while person_id in existing_ids:
            person_id = f"{clean_id}-{counter}"
            counter += 1

        person = PersonConfig(id=person_id, name=name, avatar=avatar or "", role=role, notes=notes or "")
        config.people.append(person)
        self.save_devices_config(config)
        return person

    def delete_person(self, person_id: str) -> bool:
        """Deletes a person profile and unlinks their associated devices."""
        config = self.get_devices_config()
        person = next((p for p in config.people if p.id == person_id), None)
        if not person:
            return False
        config.people = [p for p in config.people if p.id != person_id]
        for dev in config.devices:
            if dev.owner == person_id:
                dev.owner = None
        self.save_devices_config(config)
        return True

    async def get_active_leases(self) -> List[Dict[str, Any]]:
        if self.dbus:
            try:
                leases = await self.dbus.get_active_leases()
                if leases:
                    return leases
            except Exception:
                pass
        from roostos_engine.state_db import StateDB
        return StateDB._read_kea_leases_csv()

    def get_active_arp(self) -> List[Dict[str, Any]]:
        devices = []
        wan_interfaces = set()
        try:
            config = self.repo.get_config()
            for interface in config.network.interfaces:
                if getattr(interface, "role", None) == "wan" or getattr(interface, "network", None) == "wan":
                    wan_interfaces.add(interface.name)
                    if interface.vlan_tag:
                        wan_interfaces.add(f"{interface.name}.{interface.vlan_tag}")
        except Exception:
            pass

        try:
            if os.path.exists("/proc/net/arp"):
                import socket
                with open("/proc/net/arp", "r") as f:
                    lines = f.readlines()
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 6:
                            ip = parts[0]
                            flags = parts[2]
                            mac = parts[3].lower()
                            iface = parts[5]
                            is_wan = iface in wan_interfaces or iface.startswith("ppp")
                            if flags != "0x0" and mac != "00:00:00:00:00:00" and ":" in mac and not is_wan:
                                host = None
                                try:
                                    host = socket.gethostbyaddr(ip)[0]
                                except Exception:
                                    pass
                                devices.append({"ip": ip, "mac": mac, "interface": iface, "hostname": host})
        except Exception:
            pass

        if not devices:
            is_mock = getattr(self.dbus, "mock", False) or os.environ.get("ROOSTOS_MOCK", "false").lower() in ("true", "1")
            if is_mock:
                devices = [
                    {"ip": "192.168.1.10", "mac": "a4:83:e7:12:34:56", "interface": "br0", "hostname": "smart-tv"},
                    {"ip": "192.168.1.50", "mac": "4c:32:75:98:76:54", "interface": "br0", "hostname": "game-console"},
                ]
        return devices

    async def trigger_config_reload(self) -> None:
        """Compatibility trigger; repository mutations dispatch events automatically."""
        if self.dbus:
            try:
                if hasattr(self.dbus, "reload_config"):
                    await self.dbus.reload_config()
                elif hasattr(self.dbus, "get_config"):
                    await self.dbus.get_config()
            except Exception:
                pass
