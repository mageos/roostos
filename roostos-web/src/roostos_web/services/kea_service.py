"""ISC Kea DHCP 2.4 configuration compiler, lease parser, and static reservation service."""

import ipaddress
import os
from typing import Any, Dict, List, Optional

from roostos_engine.config import NetworkConfig, DevicesConfig, DeviceConfig, NetworkBridge, NetworkVlan
from roostos_engine.repository import ConfigRepository, YAMLConfigRepository, StagingConfigRepository
from roostos_engine.state_db import StateDB
from roostos_sdk.client import RoostClient
from roostos_web.schemas.dhcp import (
    DhcpScopeDTO,
    DhcpLeaseDTO,
    DhcpReservationDTO,
    HaModeEnum,
)


class KeaService:
    """Service for managing multi-subnet Kea DHCP scopes, leases, and reservations."""

    def __init__(self, repo: ConfigRepository, dbus: Optional[RoostClient] = None):
        self.repo = repo
        self.dbus = dbus

    def _is_mock_mode(self) -> bool:
        return (
            os.environ.get("ROOSTOS_MOCK") == "1"
            or getattr(self.dbus, "mock", False)
            or not isinstance(self.repo, (YAMLConfigRepository, StagingConfigRepository))
        )

    def _calculate_pool_size(self, pool_start: str, pool_end: str) -> int:
        """Calculates total number of IP addresses in a pool range."""
        try:
            start_int = int(ipaddress.IPv4Address(pool_start))
            end_int = int(ipaddress.IPv4Address(pool_end))
            return max(0, (end_int - start_int) + 1)
        except Exception:
            return 0

    def _build_scope_dto(
        self, iface_obj: Any, is_vlan: bool, active_leases: List[DhcpLeaseDTO], node_id: str = "roost-router"
    ) -> Optional[DhcpScopeDTO]:
        """Constructs a DhcpScopeDTO from a bridge or VLAN model object."""
        if not getattr(iface_obj, "dhcp_enabled", True) or not getattr(iface_obj, "ip", None):
            return None
        try:
            iface = ipaddress.ip_interface(iface_obj.ip)
            subnet_str, gateway_str = str(iface.network), str(iface.ip)
        except Exception:
            return None

        prefix = gateway_str.rsplit(".", 1)[0]
        start = getattr(iface_obj, "dhcp_pool_start", None) or f"{prefix}.100"
        end = getattr(iface_obj, "dhcp_pool_end", None) or (f"{prefix}.240" if is_vlan else f"{prefix}.250")
        name_tag = iface_obj.name.replace("vlan-", "").replace("br-", "").upper()

        matching = sum(
            1 for l in active_leases
            if l.network_interface == iface_obj.name or self._ip_in_subnet(l.ip, subnet_str)
        )

        ttl = getattr(iface_obj, "lease_time", 604800 if "iot" in iface_obj.name else (7200 if is_vlan else 86400))
        return DhcpScopeDTO(
            id=f"scope-{iface_obj.name}",
            name=f"{name_tag} {'Zone' if is_vlan else 'Network'}",
            node_id=node_id,
            ha_mode=HaModeEnum.STANDALONE,
            interface=iface_obj.name,
            subnet=subnet_str,
            gateway=gateway_str,
            enabled=getattr(iface_obj, "dhcp_enabled", True),
            pool_start=start,
            pool_end=end,
            lease_time_seconds=ttl,
            dns_servers=[gateway_str],
            domain_name=f"{iface_obj.name.replace('br-', '').replace('vlan-', '')}.roost",
            authoritative=True,
            active_leases_count=matching,
            pool_size=self._calculate_pool_size(start, end),
        )

    async def get_scopes(self) -> List[DhcpScopeDTO]:
        """Returns all configured multi-subnet DHCP scopes with live lease counts."""
        config = self.repo.get_config()
        node_id = getattr(config.system, "hostname", "roost-router") if config.system else "roost-router"
        net_cfg = config.network
        inner_net = getattr(net_cfg, "network", None) or net_cfg
        active_leases = await self.get_leases()

        scopes: List[DhcpScopeDTO] = []
        for b in getattr(inner_net, "bridges", []):
            scope = self._build_scope_dto(b, is_vlan=False, active_leases=active_leases, node_id=node_id)
            if scope:
                scopes.append(scope)

        for v in getattr(inner_net, "vlans", []):
            scope = self._build_scope_dto(v, is_vlan=True, active_leases=active_leases, node_id=node_id)
            if scope:
                scopes.append(scope)

        if not scopes and self._is_mock_mode():
            scopes.append(DhcpScopeDTO(
                id="scope-lan",
                name="Household LAN",
                node_id=node_id,
                interface="br-lan",
                subnet="192.168.1.0/24",
                gateway="192.168.1.1",
                enabled=True,
                pool_start="192.168.1.100",
                pool_end="192.168.1.250",
                lease_time_seconds=86400,
                dns_servers=["192.168.1.1"],
                domain_name="lan.roost",
                authoritative=True,
                active_leases_count=len(active_leases),
                pool_size=151,
            ))
        return scopes

    async def update_scope(self, scope_data: DhcpScopeDTO) -> DhcpScopeDTO:
        """Updates an existing DHCP scope parameters and commits changes."""
        config = self.repo.get_config()
        net_cfg = config.network
        inner_net = getattr(net_cfg, "network", None) or net_cfg

        updated = False
        candidates = list(getattr(inner_net, "bridges", [])) + list(getattr(inner_net, "vlans", []))
        for item in candidates:
            if item.name == scope_data.interface or f"scope-{item.name}" == scope_data.id:
                item.dhcp_enabled = scope_data.enabled
                item.dhcp_pool_start = scope_data.pool_start
                item.dhcp_pool_end = scope_data.pool_end
                item.lease_time = scope_data.lease_time_seconds
                updated = True
                break

        if updated:
            self.repo.save_network_config(net_cfg)
            await self._trigger_reload()
        return scope_data

    async def create_scope(self, scope_data: DhcpScopeDTO) -> DhcpScopeDTO:
        """Creates a new bridge/vlan network scope and enables Kea DHCP."""
        config = self.repo.get_config()
        net_cfg = config.network
        inner_net = getattr(net_cfg, "network", None) or net_cfg

        new_bridge = NetworkBridge(
            name=scope_data.interface,
            ip=f"{scope_data.gateway}/{scope_data.subnet.split('/')[-1]}",
            dhcp_enabled=scope_data.enabled,
            dhcp_pool_start=scope_data.pool_start,
            dhcp_pool_end=scope_data.pool_end,
        )
        inner_net.bridges.append(new_bridge)
        self.repo.save_network_config(net_cfg)
        await self._trigger_reload()
        return scope_data

    async def get_leases(self, node_id: Optional[str] = None) -> List[DhcpLeaseDTO]:
        """Fetches active dynamic leases from CSV, D-Bus, or mock fallback."""
        raw_leases: List[Dict[str, Any]] = []
        try:
            raw_leases = await self.dbus.get_active_leases()
        except Exception:
            pass

        if not raw_leases:
            raw_leases = StateDB._read_kea_leases_csv()

        if not raw_leases and self._is_mock_mode():
            raw_leases = [
                {"ip": "192.168.1.101", "mac": "10:9a:dd:33:44:55", "hostname": "Dads-MacBook-Pro", "interface": "br-lan", "expires": 67320, "vendor": "Apple Inc."},
                {"ip": "192.168.1.102", "mac": "22:33:44:55:66:77", "hostname": "Moms-iPhone-15", "interface": "br-lan", "expires": 76200, "vendor": "Apple Inc."},
                {"ip": "192.168.1.103", "mac": "33:44:55:66:77:88", "hostname": "Alices-iPad", "interface": "br-lan", "expires": 33300, "vendor": "Apple Inc."},
                {"ip": "192.168.1.104", "mac": "44:55:66:77:88:99", "hostname": "Bobs-Chromebook", "interface": "br-lan", "expires": 50700, "vendor": "Google LLC"},
                {"ip": "192.168.10.51", "mac": "88:99:aa:bb:cc:dd", "hostname": "Guest-Pixel-7", "interface": "vlan-guest", "expires": 4320, "vendor": "Google LLC"},
                {"ip": "192.168.20.101", "mac": "99:aa:bb:cc:dd:ee", "hostname": "hue-bridge-hub", "interface": "vlan-iot", "expires": 554400, "vendor": "Signify"}
            ]

        results: List[DhcpLeaseDTO] = []
        for rl in raw_leases:
            mac_val = rl.get("mac") or rl.get("hw-address") or ""
            ip_val = rl.get("ip") or rl.get("ip-address") or ""
            if not mac_val or not ip_val:
                continue
            results.append(DhcpLeaseDTO(
                ip=ip_val,
                mac=mac_val,
                hostname=rl.get("hostname") or "Unknown",
                network_interface=rl.get("interface") or rl.get("network") or "br-lan",
                expires_in_seconds=int(rl.get("expires") or rl.get("valid_lft") or 86400),
                vendor=rl.get("vendor"),
            ))
        return results

    async def get_reservations(self) -> List[DhcpReservationDTO]:
        """Returns all static IP reservations defined across devices."""
        config = self.repo.get_config()
        reservations: List[DhcpReservationDTO] = []
        for dev in getattr(config, "devices", []):
            if dev.static_ip:
                zone = "iot" if "iot" in getattr(dev, "tags", []) else "lan"
                reservations.append(DhcpReservationDTO(
                    mac=dev.mac,
                    reserved_ip=dev.static_ip,
                    hostname=dev.name,
                    zone=zone,
                    description=f"Assigned to {dev.owner}" if dev.owner else None,
                ))
        return reservations

    async def convert_lease_to_static(self, mac: str, hostname: Optional[str] = None, description: Optional[str] = None) -> Optional[DhcpReservationDTO]:
        """Converts an active dynamic lease into a permanent static MAC reservation."""
        norm_mac = mac.strip().lower()
        leases = await self.get_leases()
        target_lease = next((l for l in leases if l.mac.lower() == norm_mac), None)
        if not target_lease:
            return None

        config = self.repo.get_config()
        dev = next((d for d in config.devices if d.mac.lower() == norm_mac), None)
        host_name = hostname or target_lease.hostname or f"Device-{norm_mac.replace(':', '')[-4:]}"

        if dev:
            dev.static_ip = target_lease.ip
            if hostname:
                dev.name = hostname
        else:
            new_dev = DeviceConfig(
                mac=norm_mac,
                name=host_name,
                static_ip=target_lease.ip,
                tags=["converted_reservation"],
            )
            config.devices.append(new_dev)

        self.repo.save_devices_config(DevicesConfig(
            people=config.people,
            buildings=config.buildings,
            rooms=config.rooms,
            devices=config.devices
        ))
        await self._trigger_reload()

        return DhcpReservationDTO(
            mac=norm_mac,
            reserved_ip=target_lease.ip,
            hostname=host_name,
            zone="lan",
            description=description or "Converted from dynamic lease",
        )

    def _ip_in_subnet(self, ip_str: str, subnet_str: str) -> bool:
        """Helper to test if an IP address belongs to a subnet CIDR."""
        try:
            return ipaddress.ip_address(ip_str) in ipaddress.ip_network(subnet_str, strict=False)
        except Exception:
            return False

    async def _trigger_reload(self) -> None:
        """Triggers daemon config reload over D-Bus."""
        try:
            if hasattr(self.dbus, "reload_config"):
                await self.dbus.reload_config()
            else:
                await self.dbus.get_config()
        except Exception:
            pass
