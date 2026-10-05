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

router = APIRouter(tags=["network"])


def _get_live_interface_stats() -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    net_dir = "/sys/class/net"
    if not os.path.exists(net_dir):
        return stats

    ip_map: Dict[str, str] = {}
    if shutil.which("ip"):
        try:
            res = subprocess.run(["ip", "-j", "addr", "show"], capture_output=True, text=True, timeout=1)
            if res.returncode == 0:
                for item in json.loads(res.stdout):
                    ifname = item.get("ifname", "")
                    for addr in item.get("addr_info", []):
                        if addr.get("family") == "inet":
                            ip_map[ifname] = f"{addr.get('local')}/{addr.get('prefixlen')}"
                            break
        except Exception:
            pass

    try:
        entries = os.listdir(net_dir)
    except Exception:
        return stats

    for name in entries:
        if name == "lo" or name.startswith(("veth", "docker", "virbr", "tap", "tun", "wg")):
            continue
        dev_path = os.path.join(net_dir, name)

        mac: Optional[str] = None
        addr_file = os.path.join(dev_path, "address")
        if os.path.exists(addr_file):
            try:
                with open(addr_file, "r") as f:
                    mac = f.read().strip().lower()
            except Exception:
                pass

        status = "unknown"
        oper_file = os.path.join(dev_path, "operstate")
        if os.path.exists(oper_file):
            try:
                with open(oper_file, "r") as f:
                    status = f.read().strip()
            except Exception:
                pass

        mtu = 1500
        mtu_file = os.path.join(dev_path, "mtu")
        if os.path.exists(mtu_file):
            try:
                with open(mtu_file, "r") as f:
                    mtu = int(f.read().strip())
            except Exception:
                pass

        speed = "Unknown"
        speed_file = os.path.join(dev_path, "speed")
        if os.path.exists(speed_file):
            try:
                with open(speed_file, "r") as f:
                    sp = f.read().strip()
                    if sp.isdigit() and int(sp) > 0:
                        speed = f"{sp} Mbps"
            except Exception:
                pass

        duplex = "Unknown"
        duplex_file = os.path.join(dev_path, "duplex")
        if os.path.exists(duplex_file):
            try:
                with open(duplex_file, "r") as f:
                    dp = f.read().strip()
                    if dp:
                        duplex = dp.capitalize()
            except Exception:
                pass

        stats[name] = {
            "mac": mac,
            "status": status,
            "mtu": mtu,
            "speed": speed,
            "duplex": duplex,
            "ip": ip_map.get(name, ""),
        }
    return stats


class DNSConfigSchema(BaseModel):
    forwarders: List[str]
    ad_blocking_enabled: bool


@router.get("/api/network")
async def get_network_config(
    current_user: UserSession = Depends(get_current_parent),
    network_service: NetworkService = Injected(NetworkService)
) -> Dict[str, Any]:
    """Returns unified network, wifi, and VPN configurations enriched with live interface status."""
    config = network_service.get_network_config()
    vpns = network_service.get_vpns()
    net_data = config.network.model_dump(exclude_none=True, by_alias=True) if config.network else {}

    live_stats = _get_live_interface_stats()
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
            if name not in seen_names and not name.startswith("br"):
                interfaces.append({
                    "name": name,
                    "role": "unassigned",
                    "status": st.get("status", "unknown"),
                    "mac": st.get("mac"),
                    "mtu": st.get("mtu", 1500),
                    "speed": st.get("speed", "Unknown"),
                    "duplex": st.get("duplex", "Unknown"),
                    "ip": st.get("ip", ""),
                })

    return {
        "network": net_data,
        "wifi": config.wifi.model_dump(exclude_none=True, by_alias=True) if config.wifi else {},
        "vpns": [v.model_dump(by_alias=True) for v in vpns]
    }

@router.post("/api/network")
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

@router.post("/api/wifi/guest/create")
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


@router.get("/api/dns/config")
async def get_dns_config(
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository)
):
    """Retrieves basic DNS configs (forwarders, ad blocking status) from config."""
    config = repo.get_config()
    dns_settings = config.system.dns or SystemDNSConfig()
    return {
        "forwarders": dns_settings.forwarders,
        "ad_blocking_enabled": dns_settings.ad_blocking_enabled
    }

@router.post("/api/dns/config")
async def update_dns_config(
    dns_data: DNSConfigSchema,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Updates basic DNS configurations and sets them over D-Bus proxy if active."""
    config = repo.get_config()
    
    dns_settings = SystemDNSConfig(
        forwarders=dns_data.forwarders,
        ad_blocking_enabled=dns_data.ad_blocking_enabled
    )
    
    config.system.dns = dns_settings
    
    system_config_obj = SystemConfig(
        system=config.system,
        users=config.users
    )
    repo.save_system_config(system_config_obj)
    await dbus.get_config()
    
    try:
        if dbus._bus:
            introspection = await dbus._bus.introspect("org.roostos.DNSResolver", "/org/roostos/DNSResolver")
            proxy_object = dbus._bus.get_proxy_object("org.roostos.DNSResolver", "/org/roostos/DNSResolver", introspection)
            dns_interface = proxy_object.get_interface("org.roostos.DNSResolver")
            if dns_interface:
                await dns_interface.call_set_global_forwarders(dns_data.forwarders)
                await dns_interface.call_set_ad_blocking_enabled(dns_data.ad_blocking_enabled)
                print("Successfully propagated DNS settings over D-Bus to DNSResolver service.")
    except Exception as e:
        print(f"Warning: Failed to propagate DNS configuration over D-Bus (DNSResolver might be offline): {e}", file=sys.stderr)
        
    return {"status": "success", "message": "DNS configurations updated successfully."}
