"""RoostOS Orphaned Records Detector and Diagnostic Cleaner.

Detects lingering credentials, dangling DHCP standby assignments, obsolete VPN peer targets,
orphaned device linkages, and residual network interface files across the cluster.
"""

import os
import yaml
import shutil
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from roostos_engine.config import load_config_directory, RoostConfig
from roostos_engine.repository import ConfigRepository, YAMLConfigRepository
from roostos_engine.models.devices import DevicesConfig
from roostos_engine.models.node import NodesConfigFile
from roostos_engine.models.network import NetworkConfig


class OrphanedRecord(BaseModel):
    category: str  # "certificate", "domain_certificate", "dhcp_standby", "vpn_peer", "device_linkage", "network_interface"
    identifier: str
    description: str
    suggested_action: str = "remove"
    location: Optional[str] = None


class OrphanScanResult(BaseModel):
    total_orphans: int = 0
    orphans: List[OrphanedRecord] = Field(default_factory=list)
    healthy: bool = True
    summary: str = "No orphaned records detected."


def _load_raw_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def scan_orphaned_records(
    config_dir: str = "/etc/roostos",
    config: Optional[RoostConfig] = None
) -> OrphanScanResult:
    """Scans configuration and disk state for orphaned records."""
    nodes = []
    bridges = []
    vlans = []
    edge_gateways = []
    devices = []
    people = []
    buildings = []
    rooms = []

    if config:
        nodes = config.nodes or []
        if config.network:
            bridges = getattr(config.network, "bridges", []) or []
            vlans = getattr(config.network, "vlans", []) or []
            edge_gateways = getattr(config.network, "edge_gateways", []) or []
        devices = config.devices or []
        people = config.people or []
        buildings = config.buildings or []
        rooms = config.rooms or []
    else:
        try:
            cfg = load_config_directory(config_dir)
            nodes = cfg.nodes or []
            if cfg.network:
                bridges = getattr(cfg.network, "bridges", []) or []
                vlans = getattr(cfg.network, "vlans", []) or []
                edge_gateways = getattr(cfg.network, "edge_gateways", []) or []
            devices = cfg.devices or []
            people = cfg.people or []
            buildings = cfg.buildings or []
            rooms = cfg.rooms or []
        except Exception:
            # Fall back to component files to inspect inconsistent/broken state
            try:
                nd = _load_raw_yaml(os.path.join(config_dir, "nodes.yaml"))
                if nd: nodes = NodesConfigFile.model_validate(nd).nodes
            except Exception: pass
            try:
                nt = _load_raw_yaml(os.path.join(config_dir, "network.yaml"))
                if nt and (p_net := NetworkConfig.model_validate(nt)).network:
                    bridges = getattr(p_net.network, "bridges", []) or []
                    vlans = getattr(p_net.network, "vlans", []) or []
                    edge_gateways = getattr(p_net.network, "edge_gateways", []) or []
            except Exception: pass
            try:
                dv = _load_raw_yaml(os.path.join(config_dir, "devices.yaml"))
                if dv:
                    p_dev = DevicesConfig.model_validate(dv)
                    devices = p_dev.devices or []
                    people, buildings, rooms = p_dev.people or [], p_dev.buildings or [], p_dev.rooms or []
            except Exception: pass

    orphans: List[OrphanedRecord] = []
    known_node_ids = {n.id for n in nodes}

    # 1. Check for orphaned node service certificates
    services_dir = os.path.join(config_dir, "certs", "services")
    if os.path.exists(services_dir):
        for entry in os.listdir(services_dir):
            stem = entry[5:] if entry.startswith("node-") else entry
            if entry not in known_node_ids and stem not in known_node_ids:
                orphans.append(OrphanedRecord(
                    category="certificate",
                    identifier=entry,
                    description=f"mTLS certificate and key for decommissioned node '{stem}' still present on disk.",
                    suggested_action="purge",
                    location=os.path.join(services_dir, entry)
                ))

    # 2. Check for orphaned ACME domain certificates
    domains_dir = os.path.join(config_dir, "certs", "domains")
    if os.path.exists(domains_dir):
        active_domains = set()
        for gw in edge_gateways:
            for r in getattr(gw, "ingress_routes", []) or []:
                if getattr(r, "domain", None):
                    active_domains.add(r.domain)
        for d in os.listdir(domains_dir):
            if d not in active_domains:
                orphans.append(OrphanedRecord(
                    category="domain_certificate",
                    identifier=d,
                    description=f"Domain certificate for '{d}' exists on disk but is not mapped to any active ingress route.",
                    suggested_action="purge",
                    location=os.path.join(domains_dir, d)
                ))

    # 3. Check for orphaned DHCP standby node assignments
    for ent in list(bridges) + list(vlans):
        standby = getattr(ent, "ha_standby_node", None)
        if standby and standby != "none" and standby not in known_node_ids:
            orphans.append(OrphanedRecord(
                category="dhcp_standby",
                identifier=f"{ent.name}:{standby}",
                description=f"DHCP high-availability standby on interface '{ent.name}' references non-existent node '{standby}'.",
                suggested_action="reset_to_none",
                location="network.yaml"
            ))

    # 4. Check for orphaned VPN peers referencing non-existent server nodes
    active_servers = known_node_ids | {"edge"}
    for gw in edge_gateways:
        for p in getattr(gw, "peers", []) or []:
            target_server = getattr(p, "server_node_id", None)
            if target_server and target_server not in active_servers:
                orphans.append(OrphanedRecord(
                    category="vpn_peer",
                    identifier=p.id,
                    description=f"WireGuard peer '{p.name}' ({p.id}) is targeted to non-existent VPN server node '{target_server}'.",
                    suggested_action="reassign_or_revoke",
                    location="network.yaml"
                ))

    # 5. Check for orphaned device linkages (owner / location)
    known_people = {p.id for p in people}
    known_locations = {b.id for b in buildings} | {r.id for r in rooms}
    for dev in devices:
        if dev.owner and dev.owner not in known_people:
            orphans.append(OrphanedRecord(
                category="device_linkage",
                identifier=f"{dev.mac}:owner:{dev.owner}",
                description=f"Device '{dev.name}' ({dev.mac}) references non-existent owner ID '{dev.owner}'.",
                suggested_action="clear_owner",
                location="devices.yaml"
            ))
        if dev.location and dev.location not in known_locations:
            orphans.append(OrphanedRecord(
                category="device_linkage",
                identifier=f"{dev.mac}:location:{dev.location}",
                description=f"Device '{dev.name}' ({dev.mac}) references non-existent location ID '{dev.location}'.",
                suggested_action="clear_location",
                location="devices.yaml"
            ))

    # 6. Check for orphaned systemd network files
    wg_netdev = "/etc/systemd/network/50-wg-edge.netdev"
    if os.path.exists(wg_netdev) and not any("edge_gateway" in getattr(n, "roles", []) for n in nodes):
        orphans.append(OrphanedRecord(
            category="network_interface",
            identifier="50-wg-edge.netdev",
            description="WireGuard edge network netdev file remains on disk with no active edge gateway node configured.",
            suggested_action="delete",
            location=wg_netdev
        ))

    total = len(orphans)
    healthy = (total == 0)
    summary = "No orphaned records detected." if healthy else f"{total} orphaned record(s) detected across cluster state."

    return OrphanScanResult(
        total_orphans=total,
        orphans=orphans,
        healthy=healthy,
        summary=summary
    )


def cleanup_orphaned_records(
    repo: ConfigRepository,
    categories: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Purges detected orphaned records and updates configuration files accordingly."""
    config_dir = getattr(repo, "config_dir", "/etc/roostos")
    scan_result = scan_orphaned_records(config_dir=config_dir)
    cleaned = []
    errors = []

    target_categories = set(categories) if categories else None

    net_obj = None
    dev_obj = None
    try:
        full_cfg = repo.get_config()
        net_obj = full_cfg.network
        dev_obj = DevicesConfig(
            people=full_cfg.people or [], buildings=full_cfg.buildings or [],
            rooms=full_cfg.rooms or [], devices=full_cfg.devices or [],
        )
    except Exception:
        try:
            raw_net = _load_raw_yaml(os.path.join(config_dir, "network.yaml"))
            if raw_net: net_obj = NetworkConfig.model_validate(raw_net).network
        except Exception: pass
        try:
            raw_dev = _load_raw_yaml(os.path.join(config_dir, "devices.yaml"))
            if raw_dev: dev_obj = DevicesConfig.model_validate(raw_dev)
        except Exception: pass

    net_modified = False
    dev_modified = False

    for orphan in scan_result.orphans:
        if target_categories and orphan.category not in target_categories:
            continue

        try:
            if orphan.category in ("certificate", "domain_certificate") and orphan.location and os.path.exists(orphan.location):
                shutil.rmtree(orphan.location, ignore_errors=True)
                cleaned.append(f"{orphan.category}: {orphan.identifier}")

            elif orphan.category == "dhcp_standby" and net_obj:
                for ent in list(getattr(net_obj, "bridges", []) or []) + list(getattr(net_obj, "vlans", []) or []):
                    if getattr(ent, "ha_standby_node", None) and orphan.identifier.startswith(f"{ent.name}:"):
                        ent.ha_standby_node = "none"
                        net_modified = True
                        cleaned.append(f"dhcp_standby: reset {ent.name} to none")

            elif orphan.category == "device_linkage" and dev_obj:
                for dev in dev_obj.devices:
                    if orphan.identifier.startswith(f"{dev.mac}:owner:"):
                        dev.owner = None
                        dev_modified = True
                        cleaned.append(f"device_linkage: cleared owner on {dev.name}")
                    elif orphan.identifier.startswith(f"{dev.mac}:location:"):
                        dev.location = None
                        dev_modified = True
                        cleaned.append(f"device_linkage: cleared location on {dev.name}")

            elif orphan.category == "network_interface" and orphan.location and os.path.exists(orphan.location):
                os.remove(orphan.location)
                cleaned.append(f"network_interface: removed {orphan.location}")

        except Exception as e:
            errors.append(f"Failed to clean {orphan.identifier}: {e}")

    if net_modified and net_obj:
        repo.save_network_config(net_obj)
    if dev_modified and dev_obj:
        repo.save_devices_config(dev_obj)

    return {
        "status": "success" if not errors else "partial",
        "cleaned_count": len(cleaned),
        "cleaned_records": cleaned,
        "errors": errors
    }
