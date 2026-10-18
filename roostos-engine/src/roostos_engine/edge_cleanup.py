"""Edge Gateway disconnect and teardown cleaner for WireGuard, routes, and certificates."""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from roostos_engine.models.node import NodeRole, NodesConfigFile
from roostos_engine.repository import ConfigRepository


def disconnect_and_cleanup_edge_gateway(
    repo: ConfigRepository,
    gateway_id: Optional[str] = None,
    mock: bool = False,
) -> Dict[str, Any]:
    """Tears down Edge Gateway WireGuard interface, deletes networkd configs, and purges certificates."""
    config = repo.get_config()
    cfg_dir = getattr(repo, "config_dir", "/etc/roostos")
    cleaned_certs: List[str] = []

    # 1. Identify target gateways
    all_gateways = list(getattr(config.network, "edge_gateways", []) or getattr(config, "edge_gateways", []))
    if gateway_id:
        targets = [gw for gw in all_gateways if gw.id == gateway_id]
        remaining_gateways = [gw for gw in all_gateways if gw.id != gateway_id]
    else:
        targets = all_gateways
        remaining_gateways = []

    # 2. Cleanup associated SSL/ACME domain certificates
    domains_to_clean = set()
    for gw in targets:
        if gw.domain:
            domains_to_clean.add(gw.domain.strip().lower())
        for r in getattr(gw, "ingress_routes", []):
            if r.domain:
                domains_to_clean.add(r.domain.strip().lower())

    certs_base_dir = os.path.join(cfg_dir, "certs", "domains")
    for domain in domains_to_clean:
        domain_dir = os.path.join(certs_base_dir, domain)
        if os.path.exists(domain_dir):
            try:
                shutil.rmtree(domain_dir)
                cleaned_certs.append(domain)
            except Exception as e:
                print(f"Warning: Failed to remove certificate dir {domain_dir}: {e}")

    # Also clean up from acme_settings.json if present
    acme_settings_file = os.path.join(cfg_dir, "certs", "acme_settings.json")
    if os.path.exists(acme_settings_file):
        try:
            import json
            with open(acme_settings_file, "r") as f:
                acme_data = json.load(f)
            if "certificates" in acme_data and isinstance(acme_data["certificates"], dict):
                for domain in domains_to_clean:
                    acme_data["certificates"].pop(domain, None)
                with open(acme_settings_file, "w") as f:
                    json.dump(acme_data, f, indent=2)
        except Exception:
            pass

    # 3. Cleanup systemd-networkd files
    net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
    networkd_removed = False
    for fname in ("50-wg-edge.netdev", "50-wg-edge.network"):
        fpath = os.path.join(net_dir, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                networkd_removed = True
            except Exception as e:
                print(f"Warning: Failed removing {fpath}: {e}")

    # 4. Tear down wg-edge interface and flush routes
    interface_removed = False
    if not mock and os.getuid() == 0:
        try:
            subprocess.run(["ip", "link", "delete", "dev", "wg-edge"], check=False, capture_output=True)
            subprocess.run(["ip", "route", "del", "10.42.0.0/24", "dev", "wg-edge"], check=False, capture_output=True)
            subprocess.run(["networkctl", "reload"], check=False, capture_output=True)
            interface_removed = True
        except Exception:
            pass

    # 5. Cleanup key and token state files
    for key_name in ("edge_server.key", "edge_invite.json"):
        key_path = os.path.join(cfg_dir, key_name)
        if os.path.exists(key_path):
            try:
                os.remove(key_path)
            except Exception:
                pass

    # 6. Update repository config (network.yaml and nodes.yaml)
    config.network.edge_gateways = remaining_gateways
    config.edge_gateways = remaining_gateways

    # Clean VPN configs referencing edge gateway
    if hasattr(config.network, "vpns"):
        config.network.vpns = [v for v in config.network.vpns if not v.id.startswith("edge-") and v.id != "wg-edge"]
    if hasattr(config, "vpns"):
        config.vpns = [v for v in config.vpns if not v.id.startswith("edge-") and v.id != "wg-edge"]

    # Clean any dedicated edge gateway role in nodes
    if hasattr(config, "nodes"):
        updated_nodes = []
        for node in config.nodes:
            roles = [r.value if hasattr(r, "value") else str(r) for r in node.roles]
            if "edge_gateway" in roles:
                filtered_roles = [r for r in node.roles if (r.value if hasattr(r, "value") else str(r)) != "edge_gateway"]
                if filtered_roles:
                    node.roles = filtered_roles
                    updated_nodes.append(node)
                # If edge_gateway was its only role, node is omitted
            else:
                updated_nodes.append(node)
        config.nodes = updated_nodes
        try:
            repo.save_nodes_config(NodesConfigFile(nodes=config.nodes))
        except Exception:
            pass

    try:
        repo.save_network_config(config.network)
    except Exception as e:
        print(f"Warning: Failed saving network config after edge disconnect: {e}")

    return {
        "status": "success",
        "message": "Edge Gateway disconnected and cleaned up successfully.",
        "cleaned_certificates": cleaned_certs,
        "networkd_removed": networkd_removed,
        "interface_removed": interface_removed,
        "remaining_gateways": len(remaining_gateways),
    }
