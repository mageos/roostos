"""VPN server resolution, peer provisioning, and multi-node WireGuard coordination."""

import datetime
import io
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from roostos_engine.edge_manager import EdgeManager
from roostos_engine.edge_peer_helper import (
    compile_hub_network_file,
    compile_server_multi_peer_netdev,
    generate_client_wireguard_config,
)
from roostos_engine.models.edge import (
    CreatePeerRequest,
    EdgeGatewayConfig,
    EdgePeer,
    EdgePeerType,
    UpdateVpnServerRequest,
    VpnServerInfo,
)
from roostos_engine.models.node import NodeConfig, NodeRole, NodesConfigFile
from roostos_engine.repository import ConfigRepository


def get_vpn_servers(repo: ConfigRepository) -> List[VpnServerInfo]:
    """Resolves all available VPN server candidates across Edge Gateways and Cluster Nodes."""
    config = repo.get_config()
    servers: List[VpnServerInfo] = []

    # 1. Edge Gateways
    gateways = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
    for gw in gateways:
        servers.append(
            VpnServerInfo(
                id=gw.id,
                name=gw.name or "VPS Edge Gateway",
                node_type="edge_gateway",
                is_vpn_server=True,
                hostname=gw.domain or gw.public_ip,
                port=gw.listen_port or 51820,
                tunnel_ip=gw.tunnel_ip_gateway or "10.42.0.1/24",
                public_key=gw.public_key,
                status=gw.status or "connected",
                peers_count=len(gw.peers),
            )
        )

    # 2. Cluster Nodes
    mgr = EdgeManager()
    nodes_updated = False
    for node in getattr(config, "nodes", []):
        roles_str = [r.value if hasattr(r, "value") else str(r) for r in node.roles]
        is_server = node.is_vpn_server or ("vpn_server" in roles_str) or ("gateway_router" in roles_str and not gateways)
        if not node.vpn_public_key and is_server:
            _, pub = mgr.generate_wireguard_keypair()
            node.vpn_public_key = pub
            nodes_updated = True

        raw_peers = getattr(node, "vpn_peers", []) or []
        servers.append(
            VpnServerInfo(
                id=node.id,
                name=f"{node.name} (Router)" if "gateway_router" in roles_str else node.name,
                node_type="cluster_node",
                is_vpn_server=is_server,
                hostname=node.vpn_hostname or node.management_ip or "127.0.0.1",
                port=node.vpn_port or 51820,
                tunnel_ip=node.vpn_tunnel_ip or "10.43.0.1/24",
                public_key=node.vpn_public_key,
                status="online",
                peers_count=len(raw_peers),
            )
        )

    if nodes_updated:
        try:
            repo.save_nodes_config(NodesConfigFile(nodes=config.nodes))
        except Exception:
            pass

    return servers


def update_vpn_server(
    repo: ConfigRepository, server_id: str, payload: UpdateVpnServerRequest
) -> VpnServerInfo:
    """Updates VPN server status, public hostname, or WireGuard port for an Edge Gateway or Node."""
    config = repo.get_config()
    gateways = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
    for gw in gateways:
        if gw.id == server_id:
            if payload.hostname is not None:
                gw.domain = payload.hostname.strip()
            if payload.port is not None:
                gw.listen_port = payload.port
            repo.save_network_config(config.network)
            return VpnServerInfo(
                id=gw.id, name=gw.name, node_type="edge_gateway", is_vpn_server=True,
                hostname=gw.domain or gw.public_ip, port=gw.listen_port,
                tunnel_ip=gw.tunnel_ip_gateway, public_key=gw.public_key,
                status=gw.status, peers_count=len(gw.peers),
            )

    for node in getattr(config, "nodes", []):
        if node.id == server_id:
            if payload.hostname is not None:
                node.vpn_hostname = payload.hostname.strip()
            if payload.port is not None:
                node.vpn_port = payload.port
            if payload.is_vpn_server is not None:
                node.is_vpn_server = payload.is_vpn_server
                if node.is_vpn_server:
                    if NodeRole.VPN_SERVER not in node.roles:
                        node.roles.append(NodeRole.VPN_SERVER)
                else:
                    node.roles = [r for r in node.roles if (r.value if hasattr(r, "value") else str(r)) != "vpn_server"]
            if not node.vpn_public_key:
                _, pub = EdgeManager().generate_wireguard_keypair()
                node.vpn_public_key = pub
            repo.save_nodes_config(NodesConfigFile(nodes=config.nodes))
            return VpnServerInfo(
                id=node.id, name=node.name, node_type="cluster_node",
                is_vpn_server=node.is_vpn_server, hostname=node.vpn_hostname or node.management_ip,
                port=node.vpn_port, tunnel_ip=node.vpn_tunnel_ip, public_key=node.vpn_public_key,
                status="online", peers_count=len(getattr(node, "vpn_peers", []) or []),
            )

    raise ValueError(f"VPN server '{server_id}' not found.")


def list_all_peers(repo: ConfigRepository) -> List[EdgePeer]:
    """Returns all mobile and site VPN peers across Edge Gateway and cluster nodes."""
    config = repo.get_config()
    peers: List[EdgePeer] = []
    for gw in (getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", [])):
        for p in gw.peers:
            if not p.server_node_id:
                p.server_node_id = gw.id
                p.server_node_name = gw.name
            peers.append(p)
    for node in getattr(config, "nodes", []):
        for raw in (getattr(node, "vpn_peers", []) or []):
            p = EdgePeer.model_validate(raw) if isinstance(raw, dict) else raw
            if not p.server_node_id:
                p.server_node_id = node.id
                p.server_node_name = node.name
            peers.append(p)
    return peers


def create_vpn_peer(repo: ConfigRepository, payload: CreatePeerRequest) -> EdgePeer:
    """Enrolls a new mobile device or site router onto the selected VPN server node."""
    servers = get_vpn_servers(repo)
    if not servers:
        raise ValueError("No active VPN servers available.")

    target_server: Optional[VpnServerInfo] = None
    if payload.server_node_id:
        target_server = next((s for s in servers if s.id == payload.server_node_id), None)
        if not target_server:
            raise ValueError(f"Selected VPN server '{payload.server_node_id}' not found.")
    else:
        # Default to active Edge Gateway, or first active VPN server
        target_server = next((s for s in servers if s.is_vpn_server and s.node_type == "edge_gateway"), None)
        if not target_server:
            target_server = next((s for s in servers if s.is_vpn_server), servers[0])

    mgr = EdgeManager()
    client_priv, client_pub = mgr.generate_wireguard_keypair()

    config = repo.get_config()
    is_edge = target_server.node_type == "edge_gateway"
    gw = next((g for g in (getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", [])) if g.id == target_server.id), None) if is_edge else None
    target_node = next((n for n in getattr(config, "nodes", []) if n.id == target_server.id), None) if not is_edge else None

    # Determine unique assigned tunnel IP in subnet (10.42.0.0/24 for edge, 10.43.0.0/24 for node)
    subnet_prefix = "10.42.0" if is_edge else "10.43.0"
    existing_peers = gw.peers if is_edge and gw else [EdgePeer.model_validate(p) if isinstance(p, dict) else p for p in getattr(target_node, "vpn_peers", []) or []]
    used_ips = {p.assigned_ip.split("/")[0] for p in existing_peers}
    used_ips.add(f"{subnet_prefix}.1")
    used_ips.add(f"{subnet_prefix}.2")

    assigned_host = None
    start_octet = 3 if payload.peer_type == EdgePeerType.SITE else 10
    for octet in range(start_octet, 250):
        candidate = f"{subnet_prefix}.{octet}"
        if candidate not in used_ips:
            assigned_host = candidate
            break

    if not assigned_host:
        raise ValueError("VPN subnet address pool exhausted.")

    endpoint_host = target_server.hostname or "127.0.0.1"
    client_allowed_ips = ["0.0.0.0/0", "::/0"] if payload.route_internet else [f"{subnet_prefix}.0/24"]
    for p in existing_peers:
        if p.subnets:
            client_allowed_ips.extend(p.subnets)
    if payload.subnets:
        client_allowed_ips.extend(payload.subnets)

    client_conf = generate_client_wireguard_config(
        client_private_key=client_priv,
        gateway_public_key=target_server.public_key or "",
        endpoint=f"{endpoint_host}:{target_server.port}",
        assigned_ip=f"{assigned_host}/24",
        allowed_ips=list(dict.fromkeys(client_allowed_ips)),
        dns_server=f"{subnet_prefix}.1",
        persistent_keepalive=25,
    )

    qr_svg = None
    try:
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(client_conf, image_factory=qrcode.image.svg.SvgPathImage)
        stream = io.BytesIO()
        img.save(stream)
        qr_svg = stream.getvalue().decode("utf-8")
    except Exception:
        pass

    peer = EdgePeer(
        id=f"peer-{uuid.uuid4().hex[:6]}",
        name=payload.name.strip(),
        peer_type=payload.peer_type,
        public_key=client_pub,
        assigned_ip=f"{assigned_host}/32",
        subnets=payload.subnets,
        route_internet=payload.route_internet,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        client_config=client_conf,
        qr_svg=qr_svg,
        server_node_id=target_server.id,
        server_node_name=target_server.name,
    )

    if is_edge and gw:
        gw.peers.append(peer)
        repo.save_network_config(config.network)
    elif target_node:
        if not hasattr(target_node, "vpn_peers") or target_node.vpn_peers is None:
            target_node.vpn_peers = []
        target_node.vpn_peers.append(peer.model_dump())
        repo.save_nodes_config(NodesConfigFile(nodes=config.nodes))

    return peer


def delete_vpn_peer(repo: ConfigRepository, peer_id: str) -> bool:
    """Revokes a WireGuard peer from its assigned VPN server."""
    config = repo.get_config()
    for gw in (getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", [])):
        initial = len(gw.peers)
        gw.peers = [p for p in gw.peers if p.id != peer_id]
        if len(gw.peers) != initial:
            repo.save_network_config(config.network)
            return True

    for node in getattr(config, "nodes", []):
        raw_peers = getattr(node, "vpn_peers", []) or []
        initial = len(raw_peers)
        node.vpn_peers = [p for p in raw_peers if (p.get("id") if isinstance(p, dict) else p.id) != peer_id]
        if len(node.vpn_peers) != initial:
            repo.save_nodes_config(NodesConfigFile(nodes=config.nodes))
            return True

    return False
