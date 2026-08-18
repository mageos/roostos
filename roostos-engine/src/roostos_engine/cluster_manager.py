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
        }

    def inspect_and_check_new_hardware(
        self,
        current_node: Optional[NodeConfig]
    ) -> List[DetectedHardwareInterface]:
        """Scans hardware and returns any unconfigured interfaces."""
        return HardwareInspector.detect_new_hardware(current_node, mock=self.mock)
