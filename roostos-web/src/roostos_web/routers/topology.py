"""FastAPI router for Network Topology visualization and inter-network link routing."""

from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from roostos_engine.models.networks import Network, NetworkLink
from roostos_engine.models.network import ZoneConfig
from roostos_engine.repository import ConfigRepository
from roostos_web.auth import get_current_admin, get_current_parent, UserSession
from roostos_web.di import Injected

router = APIRouter(prefix="/api/network/topology", tags=["Topology"])


class TopologyResponse(BaseModel):
    networks: List[Network]
    links: List[NetworkLink]
    zones: List[ZoneConfig]
    visual_nodes: List[Dict[str, Any]]
    visual_edges: List[Dict[str, Any]]


class UpsertNetworkRequest(BaseModel):
    id: Optional[str] = None
    name: str
    subnet: str
    gateway_ip: Optional[str] = None
    network_type: str = "lan"
    interface: Optional[str] = None
    zone_id: Optional[str] = "lan"
    isolate: bool = False


class UpsertLinkRequest(BaseModel):
    id: Optional[str] = None
    source_network_id: str
    target_network_id: str
    connection_type: str = "wireguard_tunnel"
    routing_mode: str = "routed"
    firewall_policy: str = "source_to_target_only"
    allowed_ports: List[str] = Field(default_factory=list)
    gateway_ip: Optional[str] = None
    description: Optional[str] = None


def _default_networks() -> List[Network]:
    return [
        Network(id="lab-lan", name="RoostOS Lab Network", subnet="192.168.1.0/24", gateway_ip="192.168.1.1", network_type="lan", interface="br-lan", zone_id="lab"),
        Network(id="home-lan", name="Upstream Home Network", subnet="192.168.5.0/24", gateway_ip="192.168.5.1", network_type="wan_upstream", interface="eth0", zone_id="home"),
        Network(id="wg-overlay", name="WireGuard Overlay Hub", subnet="10.42.0.0/24", gateway_ip="10.42.0.1", network_type="vpn_overlay", interface="wg-edge", zone_id="vpn"),
        Network(id="vps-vpc", name="Cloud VPS Private VPC", subnet="172.26.0.0/20", gateway_ip="172.26.2.49", network_type="cloud_vpc", interface="vps-eth0", zone_id="vps"),
    ]


def _default_links() -> List[NetworkLink]:
    return [
        NetworkLink(id="link-lab-home", source_network_id="lab-lan", target_network_id="home-lan", connection_type="physical_wan", routing_mode="nat_masquerade", firewall_policy="source_to_target_only", description="Lab WAN uplink through parent home router with stateful conntrack", status="active"),
        NetworkLink(id="link-lab-wg", source_network_id="lab-lan", target_network_id="wg-overlay", connection_type="wireguard_tunnel", routing_mode="routed", firewall_policy="bidirectional_allow", description="Encrypted site-to-site mesh tunnel linking Lab to VPS Hub", status="active"),
        NetworkLink(id="link-wg-vps", source_network_id="wg-overlay", target_network_id="vps-vpc", connection_type="vpc_peering", routing_mode="routed", firewall_policy="restricted", allowed_ports=["80", "443", "22"], description="Forwarded reverse-proxy and ingress routing to VPS cloud internal network", status="active"),
    ]


@router.get("", response_model=TopologyResponse)
async def get_network_topology(
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> TopologyResponse:
    """Retrieves full topology model including subnets, links, and visual graph coordinates."""
    config = repo.get_config()
    net_cfg = getattr(config, "network", None)
    inner_cfg = getattr(net_cfg, "network", None) if net_cfg else None

    raw_nets = getattr(inner_cfg, "networks", None) if inner_cfg else None
    if not raw_nets or not isinstance(raw_nets, list):
        raw_nets = getattr(net_cfg, "networks", None) if net_cfg else None
    networks: List[Network] = list(raw_nets) if (raw_nets and isinstance(raw_nets, list)) else _default_networks()

    raw_links = getattr(inner_cfg, "links", None) if inner_cfg else None
    if not raw_links or not isinstance(raw_links, list):
        raw_links = getattr(net_cfg, "links", None) if net_cfg else None
    links: List[NetworkLink] = list(raw_links) if (raw_links and isinstance(raw_links, list)) else _default_links()

    raw_zones = getattr(inner_cfg, "zones", None) if inner_cfg else None
    if not raw_zones or not isinstance(raw_zones, list):
        raw_zones = getattr(net_cfg, "zones", None) if net_cfg else None
    zones: List[ZoneConfig] = list(raw_zones) if (raw_zones and isinstance(raw_zones, list)) else []

    visual_nodes = [
        {"id": n.id, "name": n.name, "subnet": n.subnet, "gateway_ip": n.gateway_ip, "network_type": n.network_type, "interface": n.interface or "unassigned", "zone_id": n.zone_id or "lan"}
        for n in networks
    ]
    visual_edges = [
        {"id": l.id, "source": l.source_network_id, "target": l.target_network_id, "connection_type": l.connection_type, "routing_mode": l.routing_mode, "firewall_policy": l.firewall_policy, "allowed_ports": l.allowed_ports, "status": l.status, "description": l.description or ""}
        for l in links
    ]
    return TopologyResponse(networks=networks, links=links, zones=zones, visual_nodes=visual_nodes, visual_edges=visual_edges)


@router.post("/subnets", response_model=Network)
async def upsert_network_subnet(
    payload: UpsertNetworkRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Network:
    """Creates or updates a managed subnet in the topology."""
    config = repo.get_config()
    net_cfg = getattr(config, "network", None)
    inner_cfg = getattr(net_cfg, "network", None) or net_cfg
    networks = list(getattr(inner_cfg, "networks", []) or getattr(net_cfg, "networks", []) or []) or _default_networks()

    target_id = payload.id or f"net-{uuid.uuid4().hex[:6]}"
    existing = next((n for n in networks if n.id == target_id), None)
    if existing:
        existing.name = payload.name.strip()
        existing.subnet = payload.subnet.strip()
        existing.gateway_ip = payload.gateway_ip.strip() if payload.gateway_ip else None
        existing.network_type = payload.network_type
        existing.interface = payload.interface
        existing.zone_id = payload.zone_id
        existing.isolate = payload.isolate
        saved = existing
    else:
        saved = Network(
            id=target_id, name=payload.name.strip(), subnet=payload.subnet.strip(),
            gateway_ip=payload.gateway_ip.strip() if payload.gateway_ip else None,
            network_type=payload.network_type, interface=payload.interface,
            zone_id=payload.zone_id, isolate=payload.isolate,
        )
        networks.append(saved)

    if hasattr(inner_cfg, "networks"):
        inner_cfg.networks = networks
    if hasattr(net_cfg, "networks"):
        net_cfg.networks = networks
    try:
        repo.save_network_config(net_cfg)
    except Exception as e:
        print(f"Warning: Failed to save subnet: {e}")
    return saved


@router.delete("/subnets/{network_id}")
async def delete_network_subnet(
    network_id: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, str]:
    """Deletes a subnet from the topology and removes connected links."""
    config = repo.get_config()
    net_cfg = getattr(config, "network", None)
    inner_cfg = getattr(net_cfg, "network", None) or net_cfg
    networks = list(getattr(inner_cfg, "networks", []) or getattr(net_cfg, "networks", []) or [])
    links = list(getattr(inner_cfg, "links", []) or getattr(net_cfg, "links", []) or [])

    new_nets = [n for n in networks if n.id != network_id]
    new_links = [l for l in links if l.source_network_id != network_id and l.target_network_id != network_id]

    if hasattr(inner_cfg, "networks"):
        inner_cfg.networks = new_nets
    if hasattr(net_cfg, "networks"):
        net_cfg.networks = new_nets
    if hasattr(inner_cfg, "links"):
        inner_cfg.links = new_links
    if hasattr(net_cfg, "links"):
        net_cfg.links = new_links
    try:
        repo.save_network_config(net_cfg)
    except Exception as e:
        print(f"Warning: Failed to delete subnet: {e}")
    return {"status": "success", "message": f"Subnet '{network_id}' removed."}


@router.post("/links", response_model=NetworkLink)
async def upsert_network_link(
    payload: UpsertLinkRequest,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> NetworkLink:
    """Configures an inter-network routing link with connection type, routing mode, and firewall policy."""
    config = repo.get_config()
    net_cfg = getattr(config, "network", None)
    inner_cfg = getattr(net_cfg, "network", None) or net_cfg
    links = list(getattr(inner_cfg, "links", []) or getattr(net_cfg, "links", []) or []) or _default_links()

    target_id = payload.id or f"link-{uuid.uuid4().hex[:6]}"
    existing = next((l for l in links if l.id == target_id), None)
    if existing:
        existing.source_network_id = payload.source_network_id
        existing.target_network_id = payload.target_network_id
        existing.connection_type = payload.connection_type
        existing.routing_mode = payload.routing_mode
        existing.firewall_policy = payload.firewall_policy
        existing.allowed_ports = payload.allowed_ports
        existing.gateway_ip = payload.gateway_ip
        existing.description = payload.description
        saved = existing
    else:
        saved = NetworkLink(
            id=target_id, source_network_id=payload.source_network_id,
            target_network_id=payload.target_network_id, connection_type=payload.connection_type,
            routing_mode=payload.routing_mode, firewall_policy=payload.firewall_policy,
            allowed_ports=payload.allowed_ports, gateway_ip=payload.gateway_ip,
            description=payload.description, status="active",
        )
        links.append(saved)

    if hasattr(inner_cfg, "links"):
        inner_cfg.links = links
    if hasattr(net_cfg, "links"):
        net_cfg.links = links
    try:
        repo.save_network_config(net_cfg)
    except Exception as e:
        print(f"Warning: Failed to save link: {e}")
    return saved


@router.delete("/links/{link_id}")
async def delete_network_link(
    link_id: str,
    current_user: UserSession = Depends(get_current_admin),
    repo: ConfigRepository = Injected(ConfigRepository),
) -> Dict[str, str]:
    """Revokes and deletes an inter-network link."""
    config = repo.get_config()
    net_cfg = getattr(config, "network", None)
    inner_cfg = getattr(net_cfg, "network", None) or net_cfg
    links = list(getattr(inner_cfg, "links", []) or getattr(net_cfg, "links", []) or [])

    new_links = [l for l in links if l.id != link_id]
    if hasattr(inner_cfg, "links"):
        inner_cfg.links = new_links
    if hasattr(net_cfg, "links"):
        net_cfg.links = new_links
    try:
        repo.save_network_config(net_cfg)
    except Exception as e:
        print(f"Warning: Failed to delete link: {e}")
    return {"status": "success", "message": f"Link '{link_id}' deleted."}
