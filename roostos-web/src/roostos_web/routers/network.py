import sys
from typing import List
from fastapi import APIRouter, Depends, Body, Response
from pydantic import BaseModel

from roostos_engine.config import (
    NetworkSettings, WifiSettings, VPNConfig, NetworkConfig,
    SystemDNSConfig, SystemConfig
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
        "network": config.network.model_dump(exclude_none=True) if config.network else {},
        "wifi": config.wifi.model_dump(exclude_none=True) if config.wifi else {},
        "vpns": [v.model_dump() for v in vpns]
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
