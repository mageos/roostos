"""Helper functions for retrieving and persisting active Edge Gateway configurations."""

from typing import Any, List
from roostos_engine.models.edge import EdgeGatewayConfig
from roostos_engine.ingress_helper import detect_systemd_wg_edge


def save_edge_gateway_record(repo: Any, edge_gw: EdgeGatewayConfig) -> None:
    """Helper to persist edge gateway record in network config."""
    config = repo.get_config()
    existing = [gw for gw in (getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", [])) if gw.id != edge_gw.id]
    config.network.edge_gateways = [*existing, edge_gw]
    config.edge_gateways = [*existing, edge_gw]
    try:
        repo.save_network_config(config.network)
    except Exception as e:
        print(f"Warning: Failed to save edge gateway: {e}")


def get_active_gateways(config: Any, check_systemd: bool = False) -> List[EdgeGatewayConfig]:
    """Resolves active edge gateways from network config, cluster nodes, or systemd."""
    gateways = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
    if not gateways:
        for node in getattr(config, "nodes", []):
            if "edge_gateway" in [r.value if hasattr(r, "value") else str(r) for r in node.roles]:
                return [EdgeGatewayConfig(
                    id="edge-01", name=node.name or "VPS Edge Gateway", public_ip=node.management_ip or "10.42.0.1",
                    listen_port=51820, tunnel_ip_gateway="10.42.0.1/24", tunnel_ip_home="10.42.0.2/24", status="connected",
                )]
        for vpn in (getattr(config, "vpns", []) or []):
            if getattr(vpn, "name", "") == "wg-edge" or getattr(vpn, "interface", "") == "wg-edge":
                ep = getattr(vpn, "endpoint", "10.42.0.1:51820") or "10.42.0.1:51820"
                return [EdgeGatewayConfig(
                    id="edge-01", name="VPS Edge Gateway", public_ip=ep.split(":")[0], listen_port=51820,
                    tunnel_ip_gateway="10.42.0.1/24", tunnel_ip_home="10.42.0.2/24", status="connected",
                )]
        if check_systemd:
            detected = detect_systemd_wg_edge()
            if detected:
                return [detected]
    return gateways
