"""Network interface and subnet live system discovery service.

Discovers live network devices, link statistics, routes, and IP subnets
from the Linux kernel via sysfs and the `ip` utility.
"""

import ipaddress
import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from roostos_engine.models.networks import Network


def get_interface_type(name: str) -> str:
    """Classifies interface name into physical, bridge, wireguard, or container."""
    if name.startswith(("wg", "wireguard")):
        return "wireguard"
    if name.startswith(("br", "bridge")):
        return "bridge"
    if name.startswith(("docker", "cni", "flannel")):
        return "container"
    return "physical"


def get_default_wan_route() -> Tuple[Optional[str], Optional[str]]:
    """Returns (wan_interface_name, gateway_ip) from kernel default route if available."""
    if not shutil.which("ip"):
        return None, None
    try:
        res = subprocess.run(
            ["ip", "-j", "route", "show", "default"],
            capture_output=True, text=True, timeout=1
        )
        if res.returncode == 0:
            routes = json.loads(res.stdout)
            if routes and isinstance(routes, list):
                dev = routes[0].get("dev")
                gw = routes[0].get("gateway")
                return dev, gw
    except Exception:
        pass
    return None, None


def get_live_interface_stats() -> Dict[str, Dict[str, Any]]:
    """Collects hardware and virtual interface states including WireGuard and bridges."""
    stats: Dict[str, Dict[str, Any]] = {}
    net_dir = "/sys/class/net"
    if not os.path.exists(net_dir):
        return stats

    ip_map: Dict[str, str] = {}
    if shutil.which("ip"):
        try:
            res = subprocess.run(
                ["ip", "-j", "addr", "show"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode == 0:
                for item in json.loads(res.stdout):
                    ifname = item.get("ifname", "")
                    for addr in item.get("addr_info", []):
                        if addr.get("family") == "inet":
                            ip_map[ifname] = f"{addr.get('local')}/{addr.get('prefixlen')}"
                            break
        except Exception:
            pass

    try:
        entries = os.listdir(net_dir)
    except Exception:
        return stats

    # Skip loopback and internal hypervisor tap/veth interfaces
    ignored_prefixes = ("lo", "veth", "virbr", "tap")
    for name in entries:
        if name == "lo" or name.startswith(ignored_prefixes):
            continue

        dev_path = os.path.join(net_dir, name)
        mac: Optional[str] = None
        addr_file = os.path.join(dev_path, "address")
        if os.path.exists(addr_file):
            try:
                with open(addr_file, "r") as f:
                    val = f.read().strip().lower()
                    if val and val != "00:00:00:00:00:00":
                        mac = val
            except Exception:
                pass

        status = "unknown"
        oper_file = os.path.join(dev_path, "operstate")
        if os.path.exists(oper_file):
            try:
                with open(oper_file, "r") as f:
                    status = f.read().strip()
            except Exception:
                pass

        mtu = 1500
        mtu_file = os.path.join(dev_path, "mtu")
        if os.path.exists(mtu_file):
            try:
                with open(mtu_file, "r") as f:
                    mtu = int(f.read().strip())
            except Exception:
                pass

        speed = "Unknown"
        iface_type = get_interface_type(name)
        if iface_type == "wireguard":
            speed = "Virtual / Tunnel"
        else:
            speed_file = os.path.join(dev_path, "speed")
            if os.path.exists(speed_file):
                try:
                    with open(speed_file, "r") as f:
                        sp = f.read().strip()
                        if sp.isdigit() and int(sp) > 0:
                            speed = f"{sp} Mbps"
                except Exception:
                    pass

        duplex = "N/A" if iface_type == "wireguard" else "Unknown"
        duplex_file = os.path.join(dev_path, "duplex")
        if os.path.exists(duplex_file):
            try:
                with open(duplex_file, "r") as f:
                    dp = f.read().strip()
                    if dp:
                        duplex = dp.capitalize()
            except Exception:
                pass

        stats[name] = {
            "mac": mac,
            "status": status,
            "mtu": mtu,
            "speed": speed,
            "duplex": duplex,
            "ip": ip_map.get(name, ""),
            "iface_type": iface_type,
        }
    return stats


def discover_live_system_subnets() -> List[Network]:
    """Inspects kernel interfaces and routes to detect real local subnets and overlays."""
    networks: List[Network] = []
    if not shutil.which("ip"):
        return networks

    wan_iface, wan_gw = get_default_wan_route()

    try:
        res = subprocess.run(
            ["ip", "-j", "addr", "show"],
            capture_output=True, text=True, timeout=1
        )
        if res.returncode != 0:
            return networks
        items = json.loads(res.stdout)
    except Exception:
        return networks

    ignored_prefixes = ("lo", "veth", "virbr", "tap")
    for item in items:
        ifname = item.get("ifname", "")
        if ifname == "lo" or ifname.startswith(ignored_prefixes):
            continue

        for addr in item.get("addr_info", []):
            if addr.get("family") != "inet":
                continue
            ip_str = addr.get("local")
            prefix = addr.get("prefixlen")
            if not ip_str or prefix is None:
                continue

            try:
                iface_obj = ipaddress.IPv4Interface(f"{ip_str}/{prefix}")
                sub_str = str(iface_obj.network)
                iface_type = get_interface_type(ifname)

                if iface_type == "wireguard":
                    net_type = "vpn_overlay"
                    name = f"WireGuard Hub ({ifname})"
                    zone = "vpn"
                    gw = ip_str
                elif iface_type == "bridge":
                    net_type = "lan"
                    name = f"Local LAN ({ifname})"
                    zone = "lan"
                    gw = ip_str
                elif ifname == wan_iface:
                    net_type = "wan_upstream"
                    name = f"WAN Uplink ({ifname})"
                    zone = "wan"
                    gw = wan_gw or ip_str
                elif iface_type == "container":
                    net_type = "dmz"
                    name = f"Container Bridge ({ifname})"
                    zone = "lan"
                    gw = ip_str
                else:
                    net_type = "lan"
                    name = f"Local Interface ({ifname})"
                    zone = "lan"
                    gw = ip_str

                networks.append(Network(
                    id=f"net-{ifname}",
                    name=name,
                    subnet=sub_str,
                    gateway_ip=gw,
                    network_type=net_type,
                    interface=ifname,
                    zone_id=zone,
                ))
            except Exception:
                continue

    return networks
