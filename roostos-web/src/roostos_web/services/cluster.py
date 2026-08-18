from typing import List, Dict, Any, Optional
from injector import inject

from roostos_engine.models.node import NodeConfig, NodesConfigFile, NodeRole, NodeInterface
from roostos_engine.models.system import SystemConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class ClusterService:
    @inject
    def __init__(self, repo: ConfigRepository, dbus: RoostClient):
        self.repo = repo
        self.dbus = dbus

    async def get_cluster_status(self) -> Dict[str, Any]:
        """Returns the cluster status, active roles, and node roster."""
        try:
            return await self.dbus.get_cluster_status()
        except Exception:
            # Fallback direct read from repo
            config = self.repo.get_config()
            node_id = "node-01"
            if config.system and config.system.cluster and config.system.cluster.node_id:
                node_id = config.system.cluster.node_id
            current_node = next((n for n in config.nodes if n.id == node_id), None)
            roles = [r.value if hasattr(r, "value") else str(r) for r in (current_node.roles if current_node else [NodeRole.GATEWAY_ROUTER])]
            is_controller = "controller" in roles
            return {
                "role": "controller" if is_controller and len(config.nodes) > 1 else ("standalone" if is_controller else "node"),
                "is_controller": is_controller,
                "node_id": node_id,
                "node_name": current_node.name if current_node else config.system.hostname,
                "roles": roles,
                "controller_url": config.system.cluster.controller_url if config.system.cluster else None,
                "connected_to_controller": True,
                "registered_nodes_count": len(config.nodes),
                "nodes": [n.model_dump() for n in config.nodes],
            }

    async def get_nodes(self) -> List[Dict[str, Any]]:
        """Returns the list of cluster nodes."""
        try:
            return await self.dbus.get_nodes()
        except Exception:
            config = self.repo.get_config()
            return [n.model_dump() for n in config.nodes]

    async def save_node(self, node_data: Dict[str, Any]) -> None:
        """Adds or updates a node configuration in nodes.yaml."""
        config = self.repo.get_config()
        node_id = node_data.get("id")
        existing_nodes = [n.model_dump() for n in config.nodes]
        
        idx = next((i for i, n in enumerate(existing_nodes) if n["id"] == node_id), None)
        if idx is not None:
            existing_nodes[idx] = node_data
        else:
            existing_nodes.append(node_data)

        nodes_config = NodesConfigFile(nodes=[NodeConfig.model_validate(n) for n in existing_nodes])
        self.repo.save_nodes_config(nodes_config)
        try:
            await self.dbus.save_nodes(existing_nodes)
        except Exception:
            pass

    async def remove_node(self, node_id: str) -> None:
        """Decommissions a node from nodes.yaml."""
        config = self.repo.get_config()
        filtered = [n.model_dump() for n in config.nodes if n.id != node_id]
        nodes_config = NodesConfigFile(nodes=[NodeConfig.model_validate(n) for n in filtered])
        self.repo.save_nodes_config(nodes_config)
        try:
            await self.dbus.save_nodes(filtered)
        except Exception:
            pass

    async def generate_join_token(self) -> str:
        """Generates a pairing join token."""
        try:
            return await self.dbus.generate_join_token()
        except Exception:
            import secrets
            return f"roost-{secrets.token_hex(4)}"

    async def discover_controllers(self) -> List[Dict[str, Any]]:
        """Discovers controllers on the local network via mDNS."""
        try:
            return await self.dbus.discover_controllers()
        except Exception:
            return []

    async def get_detected_hardware(self) -> List[Dict[str, Any]]:
        """Returns detected host network hardware interfaces."""
        try:
            return await self.dbus.get_detected_hardware()
        except Exception:
            from roostos_engine.hardware_inspector import HardwareInspector
            detected = HardwareInspector.inspect_network_interfaces(mock=True)
            return [d.model_dump() for d in detected]
