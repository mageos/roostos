"""Network discovery service for locating RoostOS gateways and controllers on the LAN."""

import socket
import subprocess
from typing import List, Optional

from roostos_cli.models import DiscoveredService


class NetworkDiscoverer:
    """Discovers RoostOS nodes using mDNS, standard hostname resolution, and routing probes."""

    @classmethod
    def discover_services(
        cls,
        timeout_seconds: float = 1.0,
        mock_services: Optional[List[DiscoveredService]] = None,
    ) -> List[DiscoveredService]:
        """Discovers active RoostOS nodes on the local subnet."""
        if mock_services is not None:
            return mock_services

        discovered: List[DiscoveredService] = []

        # 1. Check default gateway for Gateway Router presence
        gw_ip = cls._get_default_gateway()
        if gw_ip:
            if cls._probe_port(gw_ip, 8000, timeout=timeout_seconds):
                discovered.append(DiscoveredService(
                    name=f"RoostOS Gateway ({gw_ip})",
                    ip=gw_ip,
                    port=8000,
                    service_type="gateway",
                    properties={"source": "default_gateway"}
                ))

        # 2. Check standard domain name roostos.local
        try:
            ctrl_ip = socket.gethostbyname("roostos.local")
            if ctrl_ip and ctrl_ip != gw_ip:
                discovered.append(DiscoveredService(
                    name=f"RoostOS Controller ({ctrl_ip})",
                    ip=ctrl_ip,
                    port=8000,
                    service_type="controller",
                    properties={"source": "dns_roostos_local"}
                ))
        except Exception:
            pass

        # 3. Check WireGuard tunnel peers (10.42.0.2 is default gateway/controller)
        for wg_peer in ("10.42.0.2", "10.42.0.1"):
            if wg_peer != gw_ip and cls._probe_port(wg_peer, 8000, timeout=timeout_seconds):
                discovered.append(DiscoveredService(
                    name=f"RoostOS Controller via WireGuard ({wg_peer})",
                    ip=wg_peer,
                    port=8000,
                    service_type="controller",
                    properties={"source": "wireguard_tunnel"}
                ))
                break

        return discovered

    @classmethod
    def discover_gateways(cls, mock: Optional[List[DiscoveredService]] = None) -> List[DiscoveredService]:
        """Returns discovered gateway routers."""
        services = cls.discover_services(mock_services=mock)
        return [s for s in services if s.service_type == "gateway"]

    @classmethod
    def discover_controllers(cls, mock: Optional[List[DiscoveredService]] = None) -> List[DiscoveredService]:
        """Returns discovered cluster controllers."""
        services = cls.discover_services(mock_services=mock)
        return [s for s in services if s.service_type == "controller"]

    @staticmethod
    def _get_default_gateway() -> Optional[str]:
        """Extracts default gateway IP via ip route."""
        try:
            out = subprocess.check_output(
                ["ip", "route", "show", "default"],
                stderr=subprocess.DEVNULL,
                text=True
            )
            parts = out.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
        except Exception:
            pass
        return None

    @staticmethod
    def _probe_port(ip: str, port: int, timeout: float = 0.5) -> bool:
        """Attempts a quick TCP handshake to check if port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False
