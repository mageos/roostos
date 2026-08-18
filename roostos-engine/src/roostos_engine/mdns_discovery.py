import socket
import json
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DiscoveredController(BaseModel):
    hostname: str
    ip: str
    port: int = 8000
    version: str = "0.1.0"
    node_id: str = "node-01"
    name: str = "RoostOS Master"
    controller_url: str = ""
    discovered_via: str = "mdns"


class MDNSDiscoveryService:
    """Manages mDNS advertisement and discovery of RoostOS controllers across the LAN."""

    SERVICE_TYPE = "_roostos._tcp.local."

    def __init__(self, mock: bool = False):
        self.mock = mock
        self._advertised_info: Optional[Dict[str, Any]] = None

    def advertise_controller(
        self,
        hostname: str,
        port: int = 8000,
        node_id: str = "node-01",
        version: str = "0.1.0",
        name: str = "RoostOS Controller"
    ) -> None:
        """Advertises the local RoostOS controller on the LAN."""
        self._advertised_info = {
            "hostname": hostname,
            "port": port,
            "node_id": node_id,
            "version": version,
            "name": name,
            "controller_url": f"http://{hostname}.local:{port}"
        }

    def stop_advertising(self) -> None:
        self._advertised_info = None

    async def discover_controllers(self, timeout_seconds: float = 2.0) -> List[DiscoveredController]:
        """Discovers existing RoostOS controllers on the local network."""
        if self.mock or self._advertised_info:
            if self._advertised_info:
                info = self._advertised_info
                return [
                    DiscoveredController(
                        hostname=info["hostname"],
                        ip="127.0.0.1",
                        port=info["port"],
                        version=info["version"],
                        node_id=info["node_id"],
                        name=info["name"],
                        controller_url=info["controller_url"],
                        discovered_via="local_advertisement",
                    )
                ]
            return [
                DiscoveredController(
                    hostname="roost-gateway",
                    ip="192.168.1.1",
                    port=8000,
                    version="0.1.0",
                    node_id="node-gw-01",
                    name="Basement Gateway Router",
                    controller_url="http://192.168.1.1:8000",
                    discovered_via="mock",
                )
            ]

        controllers = []
        try:
            # Fallback probe via avahi-browse if available
            import subprocess
            proc = subprocess.run(
                ["avahi-browse", "-t", "-r", "-p", "_roostos._tcp"],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            for line in proc.stdout.splitlines():
                parts = line.split(";")
                if len(parts) >= 8 and parts[0] == "=":
                    hostname = parts[6]
                    ip = parts[7]
                    port = int(parts[8]) if len(parts) > 8 and parts[8].isdigit() else 8000
                    controllers.append(
                        DiscoveredController(
                            hostname=hostname,
                            ip=ip,
                            port=port,
                            controller_url=f"http://{ip}:{port}",
                            discovered_via="avahi",
                        )
                    )
        except Exception:
            pass

        return controllers
