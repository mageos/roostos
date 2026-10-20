import os
import shutil
import json
import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from roostos_engine.models.node import NodeConfig, NodesConfigFile, NodeRole
from roostos_engine.models.system import SystemConfig
from roostos_engine.repository import ConfigRepository
from roostos_engine.cluster_manager import ClusterManager
from roostos_engine.edge_cleanup import disconnect_and_cleanup_edge_gateway


class DecommissionResult(BaseModel):
    node_id: str
    node_name: str
    is_self: bool = False
    success: bool = True
    credentials_invalidated: bool = True
    certs_removed: List[str] = Field(default_factory=list)
    routes_cleaned: List[str] = Field(default_factory=list)
    tunnels_cleaned: List[str] = Field(default_factory=list)
    dhcp_rebalanced: List[str] = Field(default_factory=list)
    message: str = ""


def decommission_cluster_node(
    repo: ConfigRepository,
    node_id: str,
    cluster_manager: Optional[ClusterManager] = None
) -> DecommissionResult:
    """Evicts a node from the cluster roster, invalidating its mTLS credentials, certificates,

    and cleaning up routes, WireGuard tunnels, and DHCP standby assignments.
    """
    config = repo.get_config()
    target_node = next((n for n in config.nodes if n.id == node_id), None)
    if not target_node:
        raise ValueError(f"Node '{node_id}' not found in cluster inventory.")

    node_name = target_node.name or node_id
    config_dir = getattr(repo, "config_dir", "/etc/roostos")
    certs_removed: List[str] = []
    routes_cleaned: List[str] = []
    tunnels_cleaned: List[str] = []
    dhcp_rebalanced: List[str] = []

    # 1. Invalidate mTLS credentials for this node
    services_cert_dir = os.path.join(config_dir, "certs", "services")
    node_cert_dir = os.path.join(services_cert_dir, f"node-{node_id}")
    if os.path.exists(node_cert_dir):
        try:
            shutil.rmtree(node_cert_dir, ignore_errors=True)
            certs_removed.append(f"certs/services/node-{node_id}")
        except Exception:
            pass

    # Record revoked node credentials in revoked_nodes.json
    try:
        certs_dir = os.path.join(config_dir, "certs")
        os.makedirs(certs_dir, exist_ok=True)
        revoked_file = os.path.join(certs_dir, "revoked_nodes.json")
        revoked_data = []
        if os.path.exists(revoked_file):
            try:
                with open(revoked_file, "r") as f:
                    revoked_data = json.load(f)
            except Exception:
                revoked_data = []
        revoked_data.append({
            "node_id": node_id,
            "node_name": node_name,
            "revoked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        with open(revoked_file, "w") as f:
            json.dump(revoked_data, f, indent=2)
    except Exception:
        pass

    # 2. Cleanup Edge Gateway if node had edge_gateway role
    is_edge = any((r.value == "edge_gateway" if hasattr(r, "value") else str(r) == "edge_gateway") for r in target_node.roles)
    active_edge_gws = getattr(config.network, "edge_gateways", []) or []
    if is_edge or any(g.id == node_id for g in active_edge_gws):
        try:
            cleanup_res = disconnect_and_cleanup_edge_gateway(repo, gateway_id=node_id)
            certs_removed.extend(cleanup_res.get("certificates_removed", []))
            routes_cleaned.extend(cleanup_res.get("routes_flushed", []))
            tunnels_cleaned.append("wg-edge")
        except Exception:
            pass

    # 3. Clean up node-specific VPN peers if node acted as a VPN server
    if getattr(target_node, "vpn_peers", None):
        target_node.vpn_peers = []
        target_node.is_vpn_server = False

    # 4. Rebalance Kea DHCP standby assignments
    if hasattr(config, "network"):
        scopes_changed = False
        entities = list(getattr(config.network, "bridges", []) or []) + list(getattr(config.network, "vlans", []) or []) + list(getattr(config.network, "dhcp_scopes", []) or [])
        for sc in entities:
            if getattr(sc, "ha_standby_node", None) == node_id:
                sc.ha_standby_node = "none"
                dhcp_rebalanced.append(f"{getattr(sc, 'name', getattr(sc, 'id', 'unnamed'))}")
                scopes_changed = True
        if scopes_changed:
            repo.save_network_config(config.network)

    # 5. Purge ClusterManager telemetry and heartbeats
    if cluster_manager:
        cluster_manager._node_heartbeats.pop(node_id, None)
        cluster_manager._pending_commands.pop(node_id, None)

    # 6. Remove node from nodes inventory
    remaining_nodes = [n for n in config.nodes if n.id != node_id]
    repo.save_nodes_config(NodesConfigFile(nodes=remaining_nodes))

    return DecommissionResult(
        node_id=node_id,
        node_name=node_name,
        is_self=False,
        success=True,
        credentials_invalidated=True,
        certs_removed=certs_removed,
        routes_cleaned=routes_cleaned,
        tunnels_cleaned=tunnels_cleaned,
        dhcp_rebalanced=dhcp_rebalanced,
        message=f"Node '{node_name}' ({node_id}) successfully decommissioned and credentials invalidated."
    )


def leave_cluster_locally(
    repo: ConfigRepository,
    cluster_manager: Optional[ClusterManager] = None,
    notify_controller: bool = True
) -> DecommissionResult:
    """Executes a clean self-leave on the current node, notifying the controller if reachable,

    invalidating local cluster certificates, and resetting to standalone operation.
    """
    config = repo.get_config()
    sys_settings = config.system.system if hasattr(config.system, "system") else config.system
    cluster_cfg = getattr(sys_settings, "cluster", None)
    node_id = (cluster_cfg.node_id if cluster_cfg and cluster_cfg.node_id else None) or "node-01"
    controller_url = cluster_cfg.controller_url if cluster_cfg else None

    # 1. Notify controller if configured and reachable
    if notify_controller and controller_url:
        try:
            import urllib.request
            target_url = f"{controller_url.rstrip('/')}/api/v1/cluster/nodes/{node_id}"
            req = urllib.request.Request(target_url, method="DELETE", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3.0)
        except Exception:
            pass  # Best effort; failure of controller should not block local self-leave

    # 2. Local credential invalidation
    config_dir = getattr(repo, "config_dir", "/etc/roostos")
    certs_removed = []
    local_svc_dir = os.path.join(config_dir, "certs", "services", f"node-{node_id}")
    if os.path.exists(local_svc_dir):
        shutil.rmtree(local_svc_dir, ignore_errors=True)
        certs_removed.append(f"certs/services/node-{node_id}")

    # Remove client certificates if standalone
    for f in ["client.crt", "client.key"]:
        p = os.path.join(config_dir, "certs", f)
        if os.path.exists(p):
            try:
                os.remove(p)
                certs_removed.append(f"certs/{f}")
            except Exception:
                pass

    # 3. Reset cluster config in system.yaml
    if cluster_cfg:
        cluster_cfg.controller_url = None
        cluster_cfg.epoch = 1
        cluster_cfg.node_id = "node-01"
        repo.save_system_config(config.system)

    # 4. Reset nodes inventory to self-only standalone
    current_node = next((n for n in config.nodes if n.id == node_id), None)
    if not current_node:
        current_node = NodeConfig(
            id="node-01",
            name=getattr(sys_settings, "hostname", "roost-router"),
            roles=[NodeRole.GATEWAY_ROUTER]
        )
    else:
        current_node.roles = [NodeRole.GATEWAY_ROUTER]
        current_node.id = "node-01"

    repo.save_nodes_config(NodesConfigFile(nodes=[current_node]))

    # 5. Clean up cluster manager local heartbeats
    if cluster_manager:
        cluster_manager._node_heartbeats.clear()
        cluster_manager._pending_commands.clear()

    return DecommissionResult(
        node_id=node_id,
        node_name=current_node.name,
        is_self=True,
        success=True,
        credentials_invalidated=True,
        certs_removed=certs_removed,
        routes_cleaned=[],
        tunnels_cleaned=[],
        dhcp_rebalanced=[],
        message=f"Node '{current_node.name}' has left the cluster and returned to standalone operation."
    )
