import sys
from typing import List
from fastapi import APIRouter, Depends, Body, Response
from pydantic import BaseModel

from roostos_engine.config import (
    NetworkSettings, WifiSettings, VPNConfig, NetworkConfig,
    SystemDNSConfig, SystemConfig, NetworkBridge, WifiAccessPoint
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_parent, get_current_admin, UserSession
from roostos_web.services import NetworkService, get_repository, get_dbus_client

router = APIRouter(tags=["network"])

class DNSConfigSchema(BaseModel):
    forwarders: List[str]
    ad_blocking_enabled: bool

@router.get("/api/network")
async def get_network_config(
    current_user: UserSession = Depends(get_current_parent),
    network_service: NetworkService = Depends()
):
    """Returns unified network, wifi, and VPN configurations."""
    config = network_service.get_network_config()
    vpns = network_service.get_vpns()
    return {
        "network": config.network.model_dump(exclude_none=True, by_alias=True) if config.network else {},
        "wifi": config.wifi.model_dump(exclude_none=True, by_alias=True) if config.wifi else {},
        "vpns": [v.model_dump(by_alias=True) for v in vpns]
    }

@router.post("/api/network")
async def update_network_config(
    network: NetworkSettings = Body(...),
    wifi: WifiSettings = Body(...),
    vpns: List[VPNConfig] = Body([]),
    current_user: UserSession = Depends(get_current_admin),
    network_service: NetworkService = Depends()
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
    repo: ConfigRepository = Depends(get_repository),
    dbus: RoostClient = Depends(get_dbus_client)
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
    repo: ConfigRepository = Depends(get_repository)
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
    repo: ConfigRepository = Depends(get_repository),
    dbus: RoostClient = Depends(get_dbus_client)
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
