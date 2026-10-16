import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Body, Response
from pydantic import BaseModel

from roostos_engine.config import (
    NetworkSettings, WifiSettings, VPNConfig, NetworkConfig,
    SystemDNSConfig, SystemConfig, NetworkBridge, WifiAccessPoint
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_parent, get_current_admin, UserSession
from roostos_web.services import NetworkService
from roostos_web.di import Injected
from roostos_web.services.network_discovery import get_live_interface_stats

router = APIRouter(tags=["network"])


@router.get("/api/v1/network")
async def get_network_config(
    current_user: UserSession = Depends(get_current_parent),
    network_service: NetworkService = Injected(NetworkService)
) -> Dict[str, Any]:
    """Returns unified network, wifi, and VPN configurations enriched with live interface status."""
    config = network_service.get_network_config()
    vpns = network_service.get_vpns()
    net_data = config.network.model_dump(exclude_none=True, by_alias=True) if config.network else {}

    live_stats = get_live_interface_stats()
    if live_stats:
        interfaces = net_data.setdefault("interfaces", [])
        seen_names = set()
        for iface in interfaces:
            name = iface.get("name")
            seen_names.add(name)
            if name in live_stats:
                st = live_stats[name]
                iface["mac"] = st.get("mac") or iface.get("mac")
                iface["status"] = st.get("status") or iface.get("status", "unknown")
                iface["mtu"] = st.get("mtu") or iface.get("mtu", 1500)
                iface["speed"] = st.get("speed") or iface.get("speed", "Unknown")
                iface["duplex"] = st.get("duplex") or iface.get("duplex", "Unknown")
                if not iface.get("ip") and st.get("ip"):
                    iface["ip"] = st["ip"]

        for name, st in live_stats.items():
            if name not in seen_names:
                iface_type = st.get("iface_type", "physical")
                role = "unassigned"
                if iface_type == "wireguard":
                    role = "vpn"
                elif iface_type == "bridge":
                    role = "lan"
                elif iface_type == "container":
                    role = "container"

                interfaces.append({
                    "name": name,
                    "role": role,
                    "status": st.get("status", "unknown"),
                    "mac": st.get("mac"),
                    "mtu": st.get("mtu", 1500),
                    "speed": st.get("speed", "Unknown"),
                    "duplex": st.get("duplex", "Unknown"),
                    "ip": st.get("ip", ""),
                    "iface_type": iface_type,
                })

    return {
        "network": net_data,
        "wifi": config.wifi.model_dump(exclude_none=True, by_alias=True) if config.wifi else {},
        "vpns": [v.model_dump(by_alias=True) for v in vpns]
    }

@router.post("/api/v1/network")
async def update_network_config(
    network: NetworkSettings = Body(...),
    wifi: WifiSettings = Body(...),
    vpns: List[VPNConfig] = Body([]),
    current_user: UserSession = Depends(get_current_admin),
    network_service: NetworkService = Injected(NetworkService)
):
    await network_service.save_network_config(network, wifi, vpns)
    return {"status": "success", "message": "Network configuration updated successfully."}

class GuestNetworkSchema(BaseModel):
    ssid: str
    passphrase: str
    subnet: str = "192.168.10.0/24"

@router.post("/api/v1/wifi/guest/create")
async def create_guest_network(
    data: GuestNetworkSchema,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Dynamically registers an isolated Guest AP and guest bridge network."""
    import ipaddress
    try:
        net = ipaddress.ip_network(data.subnet, strict=False)
        gateway_ip = str(list(net.hosts())[0])
        hosts = list(net.hosts())
        if len(hosts) < 200:
            raise ValueError("Subnet is too small. Need at least /24 range.")
        dhcp_start = str(hosts[99])
        dhcp_end = str(hosts[-2])
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid subnet address pool: {e}")

    config = repo.get_config()
    net_settings = config.network.network or NetworkSettings()
    wifi_settings = config.network.wifi or WifiSettings()
    vpns = config.network.vpns or []

    guest_bridge_name = "br-guest"
    existing_bridge = next((b for b in net_settings.bridges if b.name == guest_bridge_name), None)
    if not existing_bridge:
        new_bridge = NetworkBridge(
            name=guest_bridge_name,
            ip=f"{gateway_ip}/{net.prefixlen}",
            isolate=True,
            dhcp_enabled=True,
            dhcp_pool_start=dhcp_start,
            dhcp_pool_end=dhcp_end
        )
        net_settings.bridges.append(new_bridge)

    existing_ap = next((ap for ap in wifi_settings.access_points if ap.ssid == data.ssid), None)
    if not existing_ap:
        new_ap = WifiAccessPoint(
            name="Guest Wi-Fi",
            ssid=data.ssid,
            passphrase=data.passphrase,
            security="wpa2-psk",
            radio="wlan0",
            bridge=guest_bridge_name
        )
        wifi_settings.access_points.append(new_ap)

    network_config_obj = NetworkConfig(
        network=net_settings,
        wifi=wifi_settings,
        vpns=vpns
    )
    repo.save_network_config(network_config_obj)
    await dbus.get_config()

    return {"status": "success", "message": f"Guest Wi-Fi network '{data.ssid}' created successfully."}
