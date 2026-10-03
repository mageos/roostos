"""Edge Ingress helper for provisioning routes for applications."""

import uuid
from typing import Any, Optional
from roostos_engine.models.edge import IngressRoute


def provision_ingress_route(
    config: Any, repo: Any, domain: str, target_port: int
) -> Optional[str]:
    """Helper to provision IngressRoute on active Edge Gateway."""
    if not getattr(config.network, "edge_gateways", None):
        return None
    gw = config.network.edge_gateways[0]
    target_ip = (
        config.network.bridges[0].ip.split("/")[0]
        if config.network.bridges
        else "192.168.1.1"
    )
    route_id = f"route-{uuid.uuid4().hex[:6]}"
    gw.ingress_routes.append(
        IngressRoute(
            id=route_id,
            domain=domain.strip().lower(),
            target_ip=target_ip,
            target_port=target_port,
            ssl_enabled=True,
            edge_gateway_id=gw.id,
        )
    )
    try:
        repo.save_network_config(config.network)
    except Exception:
        pass
    return route_id
