import os
import json
import time
import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from roostos_engine.models.node import NodeConfig, NodeRole, DetectedHardwareInterface
from roostos_engine.models.system import ClusterSettingsConfig, SystemConfig
from roostos_engine.health import HealthChecker, NodeHealthReport
from roostos_engine.mdns_discovery import MDNSDiscoveryService, DiscoveredController
from roostos_engine.hardware_inspector import HardwareInspector


class ClusterStatusSummary(BaseModel):
    role: str  # "controller", "node", "standalone"
    is_controller: bool
    node_id: str
    node_name: str
    roles: List[str]
    controller_url: Optional[str] = None
    connected_to_controller: bool = False
    registered_nodes_count: int = 0
    nodes: List[Dict[str, Any]] = Field(default_factory=list)


class ClusterManager:
    """Coordinates cluster state, node onboarding, heartbeats, and topology status."""

    def __init__(
        self,
        config_dir: str = "/etc/roostos",
        mock: bool = False,
        health_checker: Optional[HealthChecker] = None,
        mdns_service: Optional[MDNSDiscoveryService] = None,
    ):
        self.config_dir = config_dir
        self.mock = mock
        self.health_checker = health_checker or HealthChecker(config_dir, mock=mock)
        self.mdns_service = mdns_service or MDNSDiscoveryService(mock=mock)
        self._node_heartbeats: Dict[str, Dict[str, Any]] = {}
        self._join_tokens: Dict[str, float] = {}  # token -> expiry timestamp
        self._pending_commands: Dict[str, List[str]] = {}

    def get_cluster_status(
        self,
        system_config: SystemConfig,
        nodes: List[NodeConfig]
    ) -> ClusterStatusSummary:
        """Returns the current node's cluster role, connectivity, and registered nodes."""
        system_settings = system_config.system if hasattr(system_config, "system") else system_config
        node_id = "node-01"
        controller_url = None
        if system_settings and system_settings.cluster:
            node_id = system_settings.cluster.node_id or node_id
            controller_url = system_settings.cluster.controller_url

        # Find current node in nodes list
        current_node = next((n for n in nodes if n.id == node_id), None)
        active_roles = [r.value if isinstance(r, NodeRole) else str(r) for r in (current_node.roles if current_node else [NodeRole.GATEWAY_ROUTER])]
        is_controller = NodeRole.CONTROLLER.value in active_roles or "controller" in active_roles

        primary_role = "node"
        if is_controller:
            primary_role = "controller" if len(nodes) > 1 else "standalone"

        # Build list of nodes with health telemetry for controller
        node_summaries = []
        if is_controller:
            for n in nodes:
                hb = self._node_heartbeats.get(n.id, {})
                last_seen = hb.get("last_seen", "Unknown")
                status = hb.get("status", "healthy" if n.id == node_id else "unknown")
                node_summaries.append({
                    "id": n.id,
                    "name": n.name,
                    "roles": [r.value if isinstance(r, NodeRole) else str(r) for r in n.roles],
                    "management_ip": n.management_ip,
                    "mac_address": n.mac_address,
                    "location_id": n.location_id,
                    "interfaces_count": len(n.interfaces),
                    "status": status,
                    "last_seen": last_seen,
                    "telemetry": hb.get("telemetry", {}),
                })

        return ClusterStatusSummary(
            role=primary_role,
            is_controller=is_controller,
            node_id=node_id,
            node_name=current_node.name if current_node else system_config.system.hostname,
            roles=active_roles,
            controller_url=controller_url,
            connected_to_controller=is_controller or bool(controller_url),
            registered_nodes_count=len(nodes),
            nodes=node_summaries,
        )

    def generate_join_token(self, ttl_seconds: int = 600) -> str:
        """Generates a temporary pre-shared pairing token on the controller."""
        import secrets
        token = f"roost-{secrets.token_hex(4)}"
        self._join_tokens[token] = time.time() + ttl_seconds
        return token

    def validate_join_token(self, token: str) -> bool:
        """Validates a join token during node onboarding."""
        if self.mock and token.startswith("roost-"):
            return True
        expiry = self._join_tokens.get(token)
        if expiry and expiry > time.time():
            del self._join_tokens[token]
            return True
        return False

    def record_heartbeat(self, node_id: str, health_report: Dict[str, Any]) -> None:
        """Records a heartbeat received from a worker node."""
        self._node_heartbeats[node_id] = {
            "last_seen": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": health_report.get("status", "healthy"),
            "telemetry": health_report.get("telemetry", {}),
            "warnings": health_report.get("warnings", []),
            "updates_status": health_report.get("updates_status"),
        }

    def get_node_heartbeat(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Returns the latest heartbeat recorded for a given node."""
        return self._node_heartbeats.get(node_id)

    def get_all_heartbeats(self) -> Dict[str, Dict[str, Any]]:
        """Returns all recorded node heartbeats."""
        return self._node_heartbeats.copy()

    def register_node(
        self,
        join_data: Dict[str, Any],
        nodes: List[NodeConfig]
    ) -> NodeConfig:
        """Registers or updates a joined node in the cluster node list."""
        node_id = join_data.get("node_id") or join_data.get("id")
        existing = next((n for n in nodes if n.id == node_id), None)
        
        # Parse roles
        raw_roles = join_data.get("roles", ["gateway_router"])
        roles = []
        for r in raw_roles:
            if isinstance(r, NodeRole):
                roles.append(r)
            else:
                try:
                    roles.append(NodeRole(r))
                except ValueError:
                    roles.append(NodeRole.GATEWAY_ROUTER)

        new_node = NodeConfig(
            id=node_id,
            name=join_data.get("name", node_id),
            roles=roles,
            management_ip=join_data.get("management_ip"),
            mac_address=join_data.get("mac_address"),
            location_id=join_data.get("location_id"),
            capabilities=join_data.get("capabilities") or getattr(existing, "capabilities", None),
            interfaces=join_data.get("interfaces") or (existing.interfaces if existing else []),
        )
        return new_node

    def get_node_config_slice(
        self,
        node_id: str,
        system_config: Any,
        network_config: Any,
        nodes: List[NodeConfig]
    ) -> Dict[str, Any]:
        """Synthesizes a tailored configuration bundle for a specific node."""
        target_node = next((n for n in nodes if n.id == node_id), None)
        roles = [r.value if isinstance(r, NodeRole) else str(r) for r in (target_node.roles if target_node else [])]
        
        controller_url = None
        dns_servers = []
        if hasattr(system_config, "system"):
            sys = system_config.system
            if hasattr(sys, "cluster") and sys.cluster:
                controller_url = sys.cluster.controller_url
            if hasattr(sys, "dns") and sys.dns and sys.dns.forwarders:
                dns_servers = sys.dns.forwarders

        bridges = []
        vlans = []
        wifi_aps = []
        if network_config:
            net = network_config.network if hasattr(network_config, "network") else network_config
            if hasattr(net, "bridges"):
                bridges = [b.model_dump() if hasattr(b, "model_dump") else b for b in net.bridges]
            if hasattr(net, "vlans"):
                vlans = [v.model_dump() if hasattr(v, "model_dump") else v for v in net.vlans]
            wifi = network_config.wifi if hasattr(network_config, "wifi") else None
            if wifi and hasattr(wifi, "access_points"):
                wifi_aps = [ap.model_dump() if hasattr(ap, "model_dump") else ap for ap in wifi.access_points]

        return {
            "node_id": node_id,
            "name": target_node.name if target_node else node_id,
            "roles": roles,
            "controller_url": controller_url,
            "dns_servers": dns_servers,
            "interfaces": [i.model_dump() if hasattr(i, "model_dump") else i for i in (target_node.interfaces if target_node else [])],
            "bridges": bridges,
            "vlans": vlans,
            "wifi_access_points": wifi_aps,
        }

    def queue_node_command(self, node_id: str, command: str) -> None:
        """Queues an operational command to be delivered to a node on its next heartbeat."""
        self._pending_commands.setdefault(node_id, []).append(command)

    def pop_node_commands(self, node_id: str) -> List[str]:
        """Pops and returns all pending commands queued for a node."""
        return self._pending_commands.pop(node_id, [])

    def get_cluster_updates_summary(self, nodes: List[NodeConfig]) -> Dict[str, Any]:
        """Aggregates OS updates status across all nodes in the cluster."""
        total_updates = 0
        total_security_updates = 0
        nodes_reboot_required = []
        node_summaries = []

        for n in nodes:
            hb = self._node_heartbeats.get(n.id, {})
            up_status = hb.get("updates_status") or {}
            avail = up_status.get("updates_available", 0)
            sec_avail = up_status.get("security_updates_available", 0)
            reboot_req = up_status.get("reboot_required", False)

            total_updates += avail
            total_security_updates += sec_avail
            if reboot_req:
                nodes_reboot_required.append(n.id)

            node_summaries.append({
                "node_id": n.id,
                "name": n.name,
                "roles": [r.value if hasattr(r, "value") else str(r) for r in n.roles],
                "updates_available": avail,
                "security_updates_available": sec_avail,
                "reboot_required": reboot_req,
                "packages": up_status.get("packages", []),
                "last_seen": hb.get("last_seen"),
            })

        return {
            "total_updates": total_updates,
            "total_security_updates": total_security_updates,
            "reboot_required_nodes": nodes_reboot_required,
            "nodes": node_summaries,
        }

    def inspect_and_check_new_hardware(
        self,
        current_node: Optional[NodeConfig]
    ) -> List[DetectedHardwareInterface]:
        """Scans hardware and returns any unconfigured interfaces."""
        return HardwareInspector.detect_new_hardware(current_node, mock=self.mock)

