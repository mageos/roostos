from typing import List
from injector import inject

from roostos_engine.config import NetworkConfig, VPNConfig, NetworkSettings, WifiSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class NetworkService:
    @inject
    def __init__(self, repo: ConfigRepository, dbus: RoostClient):
        self.repo = repo
        self.dbus = dbus

    def get_network_config(self) -> NetworkConfig:
        config = self.repo.get_config()
        return NetworkConfig(
            network=config.network,
            wifi=config.wifi,
            vpns=self.get_vpns(),
            edge_gateways=getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []),
        )

    async def save_network_config(self, network: NetworkSettings, wifi: WifiSettings, vpns: List[VPNConfig]):
        persisted_vpns = [v for v in vpns if not v.id.startswith("edge-")]
        network_config_obj = NetworkConfig(
            network=network,
            wifi=wifi,
            vpns=persisted_vpns,
        )
        self.repo.save_network_config(network_config_obj)
        await self.dbus.get_config()

    def get_vpns(self) -> List[VPNConfig]:
        config = self.repo.get_config()
        vpns = list(config.vpns or [])
        edge_gws = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
        if not edge_gws:
            for node in getattr(config, "nodes", []):
                roles = [r.value if hasattr(r, "value") else str(r) for r in node.roles]
                if "edge_gateway" in roles:
                    from roostos_engine.models.edge import EdgeGatewayConfig
                    edge_gws.append(EdgeGatewayConfig(
                        id="edge-01",
                        name=node.name or "VPS Edge Gateway",
                        public_ip=node.management_ip or "10.42.0.1",
                        listen_port=51820,
                        tunnel_ip_gateway="10.42.0.1/24",
                        tunnel_ip_home="10.42.0.2/24",
                        status="connected",
                    ))
                    break

        for gw in edge_gws:
            vpn_id = f"edge-{gw.id}"
            if not any(v.id in (vpn_id, gw.id) for v in vpns):
                vpns.append(VPNConfig(
                    id=vpn_id,
                    name=f"{gw.name} (Edge Gateway Tunnel)",
                    type="wireguard",
                    role="client",
                    enabled=gw.status == "connected",
                    config={
                        "endpoint": f"{gw.public_ip}:{gw.listen_port}",
                        "local_ip": gw.tunnel_ip_home,
                        "remote_ip": gw.tunnel_ip_gateway,
                        "allowed_ips": "10.42.0.0/24",
                        "public_key": gw.public_key or "",
                        "status": gw.status,
                    }
                ))
        return vpns
