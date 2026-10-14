"""
Helper for WireGuard multi-peer VPN hub and client/mobile configuration.
Handles site-to-site inter-LAN routing and road-warrior mobile client configs.
"""

from typing import List, Optional
from roostos_engine.models.edge import EdgePeer


def generate_client_wireguard_config(
    client_private_key: str,
    gateway_public_key: str,
    endpoint: str,
    assigned_ip: str,
    allowed_ips: List[str],
    dns_server: str = "10.42.0.1",
    persistent_keepalive: int = 25,
) -> str:
    """Generates standard WireGuard client .conf file (for mobile QR or desktop import)."""
    allowed_str = ", ".join(allowed_ips) if allowed_ips else "10.42.0.0/24"
    return (
        f"[Interface]\n"
        f"PrivateKey = {client_private_key}\n"
        f"Address = {assigned_ip}\n"
        f"DNS = {dns_server}\n\n"
        f"[Peer]\n"
        f"PublicKey = {gateway_public_key}\n"
        f"Endpoint = {endpoint}\n"
        f"AllowedIPs = {allowed_str}\n"
        f"PersistentKeepalive = {persistent_keepalive}\n"
    )


def compile_server_multi_peer_netdev(
    gateway_private_key: str,
    peers: List[EdgePeer],
    listen_port: int = 51820,
) -> str:
    """Compiles systemd-networkd 50-wg-edge.netdev with multi-peer cryptokey routing."""
    sections = [
        "[NetDev]\n"
        "Name=wg-edge\n"
        "Kind=wireguard\n"
        "Description=RoostOS Edge Gateway Multi-Peer VPN Hub\n\n"
        "[WireGuard]\n"
        f"PrivateKey={gateway_private_key}\n"
        f"ListenPort={listen_port}\n"
    ]

    for p in peers:
        peer_allowed: List[str] = [p.assigned_ip]
        if p.subnets:
            peer_allowed.extend(p.subnets)
        allowed_line = ", ".join(peer_allowed)
        sections.append(
            f"[WireGuardPeer]\n"
            f"# Name: {p.name} ({p.peer_type})\n"
            f"PublicKey={p.public_key}\n"
            f"AllowedIPs={allowed_line}\n"
        )

    return "\n".join(sections)


def compile_hub_network_file(
    tunnel_ip: str = "10.42.0.1/24",
    routes: Optional[List[str]] = None,
) -> str:
    """Compiles systemd-networkd 50-wg-edge.network with IP forwarding enabled."""
    lines = [
        "[Match]\nName=wg-edge\n",
        f"[Network]\nAddress={tunnel_ip}\nIPForward=yes\n",
    ]
    if routes:
        for r in routes:
            lines.append(f"[Route]\nDestination={r}\n")
    return "\n".join(lines)
