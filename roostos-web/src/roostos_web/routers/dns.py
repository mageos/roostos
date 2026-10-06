"""DNS service configuration, subsystem selection, and dependency endpoints."""

import sys
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field

from roostos_engine.config import SystemDNSConfig, SystemConfig
from roostos_engine.models.plugins import (
    PluginsConfig,
    PluginConfig,
    ContainerConfig,
    PortMapping,
    VolumeMount,
)
from roostos_engine.repository import ConfigRepository
from roostos_engine.pkg_manager import (
    detect_package_manager,
    check_feature_dependencies,
    get_feature_dependencies,
)
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_parent, get_current_admin, UserSession
from roostos_web.di import Injected
from roostos_web.audit import log_config_change

router = APIRouter(tags=["dns"])


class DNSConfigSchema(BaseModel):
    subsystem: str = "local"  # "local" | "technitium"
    forwarders: List[str] = Field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    ad_blocking_enabled: bool = False
    auto_install_dependencies: bool = False


@router.get("/api/dns/config")
async def get_dns_config(
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, Any]:
    """Retrieves DNS service status, active subsystem, forwarders, and dependencies."""
    config = repo.get_config()
    dns_settings = config.system.dns or SystemDNSConfig()
    subsystem = getattr(dns_settings, "subsystem", "technitium" if dns_settings.ad_blocking_enabled else "local")

    feature_key = "dns_technitium" if subsystem == "technitium" else "dns_local"
    dep_report = check_feature_dependencies(feature_key)

    service_url = None
    if subsystem == "technitium":
        service_url = "http://127.0.0.1:5380"

    return {
        "subsystem": subsystem,
        "forwarders": dns_settings.forwarders,
        "ad_blocking_enabled": dns_settings.ad_blocking_enabled,
        "dependencies": dep_report.model_dump(),
        "service_url": service_url,
    }


@router.post("/api/dns/config")
async def update_dns_config(
    request: Request,
    dns_data: DNSConfigSchema,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> Dict[str, Any]:
    """Configures DNS resolver subsystem, forwarders, plugins, and installs missing dependencies if requested."""
    config = repo.get_config()
    subsystem = dns_data.subsystem.lower()
    is_tech = subsystem == "technitium"

    if dns_data.auto_install_dependencies:
        feature_key = "dns_technitium" if is_tech else "dns_local"
        needed = get_feature_dependencies(feature_key)
        if needed:
            res = detect_package_manager().install_packages(needed)
            if not res.success:
                raise HTTPException(status_code=500, detail=f"Failed to install required dependencies: {res.message}")

    # 1. Update system.yaml DNS settings
    ad_block = True if is_tech else dns_data.ad_blocking_enabled
    dns_settings = SystemDNSConfig(
        forwarders=dns_data.forwarders,
        ad_blocking_enabled=ad_block,
        subsystem=subsystem,
    )
    config.system.dns = dns_settings
    system_config_obj = SystemConfig(system=config.system, users=config.users)
    repo.save_system_config(system_config_obj)

    # 2. Update plugins.yaml
    plugins_cfg = config.plugins or PluginsConfig()
    existing_tech = next((p for p in plugins_cfg.plugins if p.id == "technitium-dns"), None)

    if is_tech:
        if not existing_tech:
            new_plugin = PluginConfig(
                id="technitium-dns",
                name="Technitium DNS Server",
                enabled=True,
                target_role="gateway_router",
                known_services=["dnsServer", "dnsFilter"],
                containers=[
                    ContainerConfig(
                        name="dns-server",
                        image="technitium/dns-server:latest",
                        ports=[
                            PortMapping(host_port=53, container_port=53, protocol="udp"),
                            PortMapping(host_port=53, container_port=53, protocol="tcp"),
                            PortMapping(host_port=5380, container_port=5380, protocol="tcp"),
                        ],
                        volumes=[
                            VolumeMount(host_path="/var/lib/roostos/plugins/technitium-dns/config", container_path="/etc/dns", mode="rw")
                        ],
                    )
                ],
            )
            plugins_cfg.plugins.append(new_plugin)
        else:
            existing_tech.enabled = True
    else:
        if existing_tech:
            existing_tech.enabled = False

    repo.save_plugins_config(plugins_cfg)
    await dbus.get_config()

    try:
        if dbus._bus:
            introspection = await dbus._bus.introspect("org.roostos.DNSResolver", "/org/roostos/DNSResolver")
            proxy_object = dbus._bus.get_proxy_object("org.roostos.DNSResolver", "/org/roostos/DNSResolver", introspection)
            dns_interface = proxy_object.get_interface("org.roostos.DNSResolver")
            if dns_interface:
                await dns_interface.call_set_global_forwarders(dns_data.forwarders)
                await dns_interface.call_set_ad_blocking_enabled(ad_block)
    except Exception as e:
        print(f"Warning: Failed to propagate DNS configuration over D-Bus: {e}", file=sys.stderr)

    log_config_change(
        username=current_user.username,
        section="dns",
        action="update_dns_subsystem",
        request=request,
        details=f"subsystem={subsystem}, ad_blocking={ad_block}, forwarders={dns_data.forwarders}",
    )

    feature_key = "dns_technitium" if is_tech else "dns_local"
    dep_report = check_feature_dependencies(feature_key)

    return {
        "status": "success",
        "message": f"DNS subsystem set to '{subsystem}' successfully.",
        "subsystem": subsystem,
        "ad_blocking_enabled": ad_block,
        "forwarders": dns_data.forwarders,
        "dependencies": dep_report.model_dump(),
    }
