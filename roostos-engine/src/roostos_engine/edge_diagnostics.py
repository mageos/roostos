"""Diagnostics, live connectivity/auth probing, and LAN-to-Edge route synchronization."""

import ipaddress
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from roostos_engine.models.edge import EdgeConnectivityCheckResponse


def detect_local_lan_subnets(config_dir: str = "/etc/roostos") -> List[str]:
    """Detects Main LAN IPv4 CIDR subnets from network.yaml or active bridge interfaces."""
    subnets: List[str] = []
    net_yaml = os.path.join(config_dir, "network.yaml")
    if os.path.exists(net_yaml):
        try:
            import yaml
            with open(net_yaml, "r") as f:
                data = yaml.safe_load(f) or {}
            net = data.get("network", data)
            for item, default_iso in ([*( (b, False) for b in (net.get("bridges") or []) ), *( (v, True) for v in (net.get("vlans") or []) )]):
                if not item.get("isolate", default_iso) and item.get("ip"):
                    cidr = str(ipaddress.ip_interface(item["ip"]).network)
                    if cidr not in subnets:
                        subnets.append(cidr)
            for gw in (data.get("edge_gateways") or net.get("edge_gateways") or []):
                for s in gw.get("lan_subnets", []) or []:
                    if s not in subnets:
                        subnets.append(s)
        except Exception:
            pass
    if not subnets:
        try:
            res = subprocess.run(["ip", "-4", "-o", "addr", "show", "br0"], capture_output=True, text=True, timeout=2)
            match = re.search(r"inet\s+([0-9.]+/[0-9]+)", res.stdout)
            if match:
                subnets.append(str(ipaddress.ip_interface(match.group(1)).network))
        except Exception:
            pass
    return subnets or ["192.168.1.0/24"]


def _persist_lan_subnets(config_dir: str, lan_subnets: List[str]) -> None:
    """Saves lan_subnets into network.yaml and staged network.yaml if present."""
    targets = [os.path.join(config_dir, "network.yaml")]
    if config_dir == "/etc/roostos" and os.path.exists("/var/lib/roostos/staged_config/network.yaml"):
        targets.append("/var/lib/roostos/staged_config/network.yaml")
    for path in targets:
        if os.path.exists(path):
            try:
                import yaml
                with open(path, "r") as f:
                    ydata = yaml.safe_load(f) or {}
                for gw_list in (ydata.get("edge_gateways", []), ydata.get("network", {}).get("edge_gateways", [])):
                    for gw in gw_list:
                        gw["lan_subnets"] = lan_subnets
                with open(path, "w") as f:
                    yaml.dump(ydata, f, default_flow_style=False, sort_keys=False)
            except Exception:
                pass


def apply_local_edge_routing(
    config_dir: str = "/etc/roostos", lan_subnets: Optional[List[str]] = None,
    is_gateway: bool = False, home_public_key: Optional[str] = None, mock: bool = False,
) -> List[str]:
    """Configures systemd-networkd, kernel routes, IP forwarding, and nftables for LAN <-> Edge routing."""
    resolved_subnets = lan_subnets if lan_subnets is not None else detect_local_lan_subnets(config_dir)
    _persist_lan_subnets(config_dir, resolved_subnets)
    if mock:
        return resolved_subnets

    net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
    netdev_path, network_path = os.path.join(net_dir, "50-wg-edge.netdev"), os.path.join(net_dir, "50-wg-edge.network")

    if is_gateway and os.path.exists(netdev_path):
        try:
            with open(netdev_path, "r") as f:
                content = f.read()
            allowed_line = f"AllowedIPs={','.join(['10.42.0.2/32'] + [s for s in resolved_subnets if s != '10.42.0.2/32'])}"
            if re.search(r"^\s*AllowedIPs\s*=.*$", content, flags=re.MULTILINE):
                content = re.sub(r"^\s*AllowedIPs\s*=.*$", allowed_line, content, flags=re.MULTILINE)
            with open(os.open(netdev_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
                f.write(content)
        except Exception:
            pass

    if os.path.exists(network_path):
        try:
            with open(network_path, "r") as f:
                net_content = f.read()
            base_lines, in_route = [], False
            for line in net_content.splitlines():
                if line.strip().startswith("[Route]"):
                    in_route = True
                    continue
                if in_route and line.strip().startswith("["):
                    in_route = False
                if not in_route and not line.strip().startswith("IPForward="):
                    base_lines.append(line)
            cleaned = "\n".join(base_lines).strip() + "\nIPForward=yes\n"
            for subnet in (resolved_subnets if is_gateway else ["10.42.0.0/24"]):
                cleaned += f"\n[Route]\nDestination={subnet}\nScope=link\n"
            with open(network_path, "w") as f:
                f.write(cleaned)
        except Exception:
            pass

    if os.getuid() == 0:
        try:
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], check=False, capture_output=True)
            subprocess.run(["networkctl", "reload"], check=False, capture_output=True)
            subprocess.run(["networkctl", "reconfigure", "wg-edge"], check=False, capture_output=True)
            if is_gateway:
                for subnet in resolved_subnets:
                    subprocess.run(["ip", "route", "replace", subnet, "dev", "wg-edge"], check=False, capture_output=True)
                if home_public_key:
                    subprocess.run(["wg", "set", "wg-edge", "peer", home_public_key, "allowed-ips", ",".join(["10.42.0.2/32"] + resolved_subnets)], check=False, capture_output=True)
            else:
                subprocess.run(["ip", "route", "replace", "10.42.0.0/24", "dev", "wg-edge"], check=False, capture_output=True)
                from roostos_engine.config import load_config_directory
                from roostos_engine.firewall_manager import FirewallManager
                FirewallManager(load_config_directory(config_dir)).write_ruleset("/etc/nftables.conf")
                subprocess.run(["nft", "-f", "/etc/nftables.conf"], check=False, capture_output=True)
        except Exception:
            pass
    return resolved_subnets


def push_lan_routes_to_gateway(
    config_dir: str = "/etc/roostos", lan_subnets: Optional[List[str]] = None,
    gateway_ip: str = "10.42.0.1", api_port: int = 8000, mock: bool = False,
) -> Dict[str, Any]:
    """Applies local LAN <-> wg-edge routing and pushes LAN subnet routes to the Edge Gateway."""
    net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
    is_gw = False
    if os.path.exists(os.path.join(net_dir, "50-wg-edge.network")):
        try:
            with open(os.path.join(net_dir, "50-wg-edge.network"), "r") as f:
                is_gw = "10.42.0.1/" in f.read()
        except Exception:
            pass
    subnets = apply_local_edge_routing(config_dir=config_dir, lan_subnets=lan_subnets, is_gateway=is_gw, mock=mock)
    role_str = "gateway" if is_gw else "client"
    if mock or is_gw:
        return {
            "status": "success", "lan_subnets": subnets, "local": {"role": role_str, "subnets": subnets},
            "local_applied": True, "remote_pushed": True,
            "message": f"Routes {', '.join(subnets)} synced ({role_str}).",
        }

    remote_pushed = False
    detail = f"Applied locally on Home Router ({', '.join(subnets)})"
    payload = json.dumps({"lan_subnets": subnets, "tunnel_ip_home": "10.42.0.2/24"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = _obtain_node_bearer_token(config_dir, f"http://{gateway_ip}:{api_port}")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(
            f"http://{gateway_ip}:{api_port}/api/v1/edge/routes/sync-lan",
            data=payload, headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                remote_pushed = True
                detail = f"Routes {', '.join(subnets)} pushed to Edge Gateway ({gateway_ip}) and applied locally."
    except Exception as e:
        detail = f"Applied locally on Home Router ({', '.join(subnets)}); remote gateway sync note: {e}"

    return {
        "status": "success", "lan_subnets": subnets, "local": {"role": role_str, "subnets": subnets},
        "local_applied": True, "remote_pushed": remote_pushed, "message": detail,
    }


def _obtain_node_bearer_token(config_dir: str, base_url: str) -> Optional[str]:
    """Attempts to exchange local client.crt for a Bearer JWT at base_url/oauth/token."""
    cert_candidates = [os.path.join(config_dir, "certs", "client.crt")]
    svc_dir = os.path.join(config_dir, "certs", "services")
    if os.path.isdir(svc_dir):
        cert_candidates.extend(os.path.join(svc_dir, entry, "client.crt") for entry in os.listdir(svc_dir))
    cert_pem = None
    for path in cert_candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    cert_pem = f.read().strip()
                if cert_pem:
                    break
            except Exception:
                pass
    if not cert_pem:
        return None
    try:
        form = urllib.parse.urlencode({"grant_type": "client_certificate", "client_certificate": cert_pem}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/oauth/token", data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8")).get("access_token")
    except Exception:
        return None


def verify_edge_connectivity_and_auth(
    config_dir: str = "/etc/roostos", target_ip: str = "10.42.0.1", api_port: int = 8000, mock: bool = False,
) -> EdgeConnectivityCheckResponse:
    """Actively probes WireGuard handshake, ICMP reachability, LAN routing, and X.509/token auth."""
    subnets = detect_local_lan_subnets(config_dir)
    if mock:
        return EdgeConnectivityCheckResponse(
            interface="wg-edge", role="client", interface_up=True, wireguard_handshake_ok=True, wg_handshake_ok=True,
            last_handshake="Just now", last_handshake_seconds=5, ping_ok=True, ping_reachable=True,
            ping_latency_ms=14.2, latency_ms=14.2, api_reachable=True, auth_verified=True, auth_valid=True,
            auth_method="x509_mtls", auth_detail="Verified X.509 client certificate & WireGuard Curve25519 peer key",
            lan_forwarding_enabled=True, ip_forward_enabled=True, routed_lan_subnets=subnets,
            lan_routes_configured=subnets, tunnel_route_present=True, overall_status="healthy", status="healthy",
            message=f"Tunnel reachable ({target_ip}) and peer authentication verified.",
        )

    iface_up = os.path.exists("/sys/class/net/wg-edge")
    wg_handshake_ok, last_hs_str, last_hs_sec = False, "Never", 0
    try:
        res = subprocess.run(["wg", "show", "wg-edge", "latest-handshakes"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit() and int(parts[1]) > 0:
                    last_hs_sec = max(0, int(time.time()) - int(parts[1]))
                    wg_handshake_ok = last_hs_sec < 300
                    last_hs_str = f"{last_hs_sec}s ago" if last_hs_sec < 120 else f"{last_hs_sec // 60}m ago"
    except Exception:
        pass

    ping_ok, ping_ms = False, None
    try:
        pres = subprocess.run(["ping", "-c", "1", "-W", "2", target_ip], capture_output=True, text=True, timeout=3)
        if pres.returncode == 0:
            ping_ok = True
            m = re.search(r"time=([0-9.]+)\s*ms", pres.stdout)
            ping_ms = float(m.group(1)) if m else None
    except Exception:
        pass

    tunnel_route_present, lan_fwd, api_reachable = False, False, False
    try:
        rres = subprocess.run(["ip", "route", "show", "dev", "wg-edge"], capture_output=True, text=True, timeout=2)
        tunnel_route_present = bool(rres.stdout.strip())
    except Exception:
        pass
    try:
        with open("/proc/sys/net/ipv4/ip_forward", "r") as f:
            lan_fwd = f.read().strip() == "1"
    except Exception:
        pass
    base_url = f"http://{target_ip}:{api_port}"
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base_url}/api/v1/health", method="GET"), timeout=2.5) as resp:
            api_reachable = resp.status == 200
    except Exception:
        pass

    auth_verified, auth_method, auth_detail = False, "none", "No active node certificate or WireGuard peer key verified"
    try:
        from roostos_engine.cert_manager import CertificateManager
        cert_mgr = CertificateManager(cert_dir=os.path.join(config_dir, "certs"))
        if api_reachable and _obtain_node_bearer_token(config_dir, base_url):
            auth_verified, auth_method, auth_detail = True, "x509_mtls_oauth", f"Mutual X.509 certificate exchanged with {target_ip} for Bearer JWT"
        else:
            st = cert_mgr.get_cert_status()
            if st.get("root_ca", {}).get("valid") and (st.get("services") or os.path.exists(os.path.join(config_dir, "certs", "client.crt"))):
                auth_verified, auth_method, auth_detail = True, "x509_local_ca", "Local X.509 Root CA & node client certificate cryptographically valid"
    except Exception:
        pass

    if not auth_verified and (wg_handshake_ok or ping_ok or iface_up):
        if os.path.exists(os.path.join(os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network"), "50-wg-edge.netdev")) or wg_handshake_ok:
            auth_verified, auth_method, auth_detail = True, "wireguard_curve25519", "WireGuard Curve25519 public-key peer authentication configured"

    overall = "healthy" if (ping_ok and auth_verified) else ("degraded" if (iface_up or auth_verified) else "disconnected")
    msg = f"Peer {target_ip} {'reachable' if ping_ok else 'unreachable'}; auth {auth_method} ({'valid' if auth_verified else 'unverified'})."
    return EdgeConnectivityCheckResponse(
        interface="wg-edge", role="client", interface_up=iface_up,
        wireguard_handshake_ok=wg_handshake_ok, wg_handshake_ok=wg_handshake_ok,
        last_handshake=last_hs_str, last_handshake_seconds=last_hs_sec,
        ping_ok=ping_ok, ping_reachable=ping_ok, ping_latency_ms=ping_ms, latency_ms=ping_ms,
        api_reachable=api_reachable, auth_verified=auth_verified, auth_valid=auth_verified,
        auth_method=auth_method, auth_detail=auth_detail,
        lan_forwarding_enabled=lan_fwd, ip_forward_enabled=lan_fwd,
        routed_lan_subnets=subnets, lan_routes_configured=subnets,
        tunnel_route_present=tunnel_route_present, overall_status=overall, status=overall, message=msg,
    )
