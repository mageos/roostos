"""Edge Ingress and endpoint helper for WireGuard tunnels, routes, and Nginx reverse proxy."""

import os
import re
import uuid
from typing import Any, List, Optional
from roostos_engine.models.edge import IngressRoute


def provision_ingress_route(
    config: Any, repo: Any, domain: str, target_port: int
) -> Optional[str]:
    """Helper to provision IngressRoute on active Edge Gateway."""
    gateways = getattr(config.network, "edge_gateways", None) or getattr(config, "edge_gateways", None)
    if not gateways:
        return None
    gw = gateways[0]
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


def generate_nginx_config(routes: List[IngressRoute]) -> str:
    """Generates Nginx reverse proxy configuration blocks for active IngressRoutes."""
    if not routes:
        return (
            "# RoostOS Edge Ingress Proxy\n"
            "server { listen 80 default_server; server_name _; return 404 'RoostOS Edge Gateway: No routes configured\\n'; }\n"
        )

    blocks: List[str] = ["# RoostOS Ingress Reverse Proxy Configuration\n"]
    for r in routes:
        ssl_block = ""
        if r.ssl_enabled:
            ssl_block = (
                f"    ssl_certificate /etc/roostos/certs/{r.domain}/fullchain.pem;\n"
                f"    ssl_certificate_key /etc/roostos/certs/{r.domain}/privkey.pem;\n"
            )

        server_block = (
            f"server {{\n"
            f"    listen 80;\n"
            f"    {'listen 443 ssl http2;' if r.ssl_enabled else ''}\n"
            f"    server_name {r.domain};\n"
            f"{ssl_block}\n"
            f"    location / {{\n"
            f"        proxy_pass http://{r.target_ip}:{r.target_port};\n"
            f"        proxy_set_header Host $host;\n"
            f"        proxy_set_header X-Real-IP $remote_addr;\n"
            f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            f"        proxy_set_header X-Forwarded-Proto $scheme;\n"
            f"        proxy_http_version 1.1;\n"
            f"        proxy_set_header Upgrade $http_upgrade;\n"
            f"        proxy_set_header Connection \"upgrade\";\n"
            f"    }}\n"
            f"}}\n"
        )
        blocks.append(server_block)

    return "\n".join(blocks)


def compile_lockdown_rules(wan_interface: str = "eth0") -> List[str]:
    """Generates nftables rules to restrict port 8000 to internal tunnel/localhost."""
    return [
        f"# RoostOS Attack Surface Hardening: Drop public port 8000 on {wan_interface}",
        f'add rule inet filter input iifname "{wan_interface}" tcp dport 8000 drop',
    ]


def update_peer_endpoint_file(
    endpoint_host: str,
    port: int = 51820,
    network_dir: Optional[str] = None,
) -> bool:
    """Updates the Endpoint directive in 50-wg-edge.netdev with domain or IP."""
    net_dir = network_dir or os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
    fpath = os.path.join(net_dir, "50-wg-edge.netdev")
    if not os.path.exists(fpath):
        return False

    with open(fpath, "r") as f:
        content = f.read()

    new_endpoint = f"Endpoint={endpoint_host}:{port}"
    if re.search(r"^\s*Endpoint\s*=.*$", content, flags=re.MULTILINE):
        updated = re.sub(r"^\s*Endpoint\s*=.*$", new_endpoint, content, flags=re.MULTILINE)
    elif "[WireGuardPeer]" in content:
        updated = content.replace("[WireGuardPeer]\n", f"[WireGuardPeer]\n{new_endpoint}\n")
    else:
        updated = f"{content}\n[WireGuardPeer]\n{new_endpoint}\n"

    mode = 0o600
    with open(os.open(fpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode), "w") as f:
        f.write(updated)
    return True


def persist_gateway_config(
    config_dir: str,
    vps_ip: str,
    gw_tunnel: str,
    home_tunnel: str,
    pub_key: str,
    port: int = 51820,
    domain: Optional[str] = None,
) -> None:
    """Helper to persist edge gateway record in network.yaml."""
    net_yaml = os.path.join(config_dir, "network.yaml")
    try:
        os.makedirs(config_dir, exist_ok=True)
        import yaml
        ydata = {}
        if os.path.exists(net_yaml):
            with open(net_yaml, "r") as f:
                ydata = yaml.safe_load(f) or {}

        gw_record = {
            "id": "edge-01",
            "name": "VPS Edge Gateway",
            "public_ip": vps_ip,
            "listen_port": port,
            "domain": domain,
            "tunnel_ip_gateway": gw_tunnel,
            "tunnel_ip_home": home_tunnel,
            "public_key": pub_key,
            "status": "connected",
            "ingress_routes": [],
        }
        top_gws = ydata.get("edge_gateways", [])
        net_section = ydata.setdefault("network", {})
        net_gws = net_section.setdefault("edge_gateways", [])
        existing = top_gws or net_gws
        for g in existing:
            if g.get("id") == "edge-01" and g.get("ingress_routes"):
                gw_record["ingress_routes"] = g["ingress_routes"]
                break

        updated_gws = [g for g in existing if g.get("id") != "edge-01"] + [gw_record]
        ydata["edge_gateways"] = updated_gws
        net_section["edge_gateways"] = updated_gws

        with open(net_yaml, "w") as f:
            yaml.dump(ydata, f, default_flow_style=False, sort_keys=False)

        staged_yaml = "/var/lib/roostos/staged_config/network.yaml" if config_dir == "/etc/roostos" else ""
        if staged_yaml and os.path.exists(staged_yaml):
            with open(staged_yaml, "r") as sf:
                sdata = yaml.safe_load(sf) or {}
            sdata["edge_gateways"] = updated_gws
            sdata.setdefault("network", {})["edge_gateways"] = updated_gws
            with open(staged_yaml, "w") as sf:
                yaml.dump(sdata, sf, default_flow_style=False, sort_keys=False)
    except Exception as e:
        import sys
        print(f"Warning: Failed to persist Edge Gateway in network.yaml: {e}", file=sys.stderr)


def update_gateway_endpoint(
    config_dir: str,
    endpoint_host: str,
    port: int = 51820,
    is_domain: bool = True,
) -> None:
    """Updates the domain or IP and port for edge-01 in network.yaml."""
    targets = [os.path.join(config_dir, "network.yaml")]
    if config_dir == "/etc/roostos" and os.path.exists("/var/lib/roostos/staged_config/network.yaml"):
        targets.append("/var/lib/roostos/staged_config/network.yaml")
    for net_yaml in targets:
        if not os.path.exists(net_yaml):
            continue
        try:
            import yaml
            with open(net_yaml, "r") as f:
                ydata = yaml.safe_load(f) or {}
            gws = ydata.get("edge_gateways") or ydata.get("network", {}).get("edge_gateways", [])
            for gw in gws:
                if gw.get("id") == "edge-01":
                    if is_domain:
                        gw["domain"] = endpoint_host
                    else:
                        gw["public_ip"] = endpoint_host
                    gw["listen_port"] = port
            with open(net_yaml, "w") as f:
                yaml.dump(ydata, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            import sys
            print(f"Warning: Failed to update endpoint in {net_yaml}: {e}", file=sys.stderr)


def detect_systemd_wg_edge() -> Optional[Any]:
    """Detects an active wg-edge tunnel from /etc/systemd/network/50-wg-edge.netdev if present."""
    from roostos_engine.models.edge import EdgeGatewayConfig
    net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
    netdev_path = os.path.join(net_dir, "50-wg-edge.netdev")
    network_path = os.path.join(net_dir, "50-wg-edge.network")
    if not os.path.exists(netdev_path):
        return None
    try:
        endpoint_host, listen_port, pub_key, domain = "10.42.0.1", 51820, None, None
        with open(netdev_path, "r") as f:
            for line in f:
                s = line.strip()
                if s.startswith("Endpoint="):
                    ep = s.split("=", 1)[1].strip()
                    host_part = ep.rsplit(":", 1)[0]
                    if ":" in ep:
                        try:
                            listen_port = int(ep.rsplit(":", 1)[1])
                        except ValueError:
                            pass
                    if any(c.isalpha() for c in host_part):
                        domain = host_part
                    endpoint_host = host_part
                elif s.startswith("ListenPort="):
                    try:
                        listen_port = int(s.split("=", 1)[1].strip())
                    except ValueError:
                        pass
                elif s.startswith("PublicKey="):
                    pub_key = s.split("=", 1)[1].strip()
        tunnel_home = "10.42.0.2/24"
        if os.path.exists(network_path):
            with open(network_path, "r") as nf:
                for line in nf:
                    if line.strip().startswith("Address="):
                        tunnel_home = line.strip().split("=", 1)[1].strip()
                        break
        return EdgeGatewayConfig(
            id="edge-01", name="VPS Edge Gateway", public_ip=endpoint_host,
            domain=domain, listen_port=listen_port, tunnel_ip_gateway="10.42.0.1/24",
            tunnel_ip_home=tunnel_home, public_key=pub_key, status="connected",
        )
    except Exception:
        return None


def read_wg_edge_traffic() -> dict:
    """Reads live Rx/Tx byte counters for the wg-edge interface from /proc/net/dev."""
    try:
        if os.path.exists("/proc/net/dev"):
            with open("/proc/net/dev", "r") as f:
                for line in f.readlines()[2:]:
                    parts = line.replace(":", " ").split()
                    if parts and parts[0] == "wg-edge":
                        rx_b, tx_b = int(parts[1]), int(parts[9])
                        def _fmt(b: int) -> str:
                            if b >= 1024 ** 3: return f"{b / (1024 ** 3):.2f} GB"
                            if b >= 1024 ** 2: return f"{b / (1024 ** 2):.1f} MB"
                            if b >= 1024: return f"{b / 1024:.1f} KB"
                            return f"{b} B"
                        return {"rx_bytes": _fmt(rx_b), "tx_bytes": _fmt(tx_b)}
    except Exception:
        pass
    return {"rx_bytes": "0 B", "tx_bytes": "0 B"}


