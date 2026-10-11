import os
import json
import ipaddress
from typing import Dict, Any, List
from roostos_engine.config import RoostConfig

class DHCPManager:
    """Generates Kea DHCP4 server configurations from network and devices settings."""

    def __init__(self, config: RoostConfig, target_path: str = "/etc/kea/kea-dhcp4.conf"):
        self.config = config
        self.target_path = target_path

    def _ip_in_subnet(self, ip_str: str, subnet_str: str) -> bool:
        """Returns True if ip_str falls within subnet_str range."""
        try:
            ip = ipaddress.ip_address(ip_str)
            subnet = ipaddress.ip_network(subnet_str, strict=False)
            return ip in subnet
        except ValueError:
            return False

    def _is_local_dns_active(self) -> bool:
        """Determines if a local DNS resolver/plugin is active or filtering enabled."""
        if hasattr(self.config, "plugins") and any(
            getattr(p, "enabled", True) and "dnsServer" in getattr(p, "known_services", [])
            for p in self.config.plugins
        ):
            return True
        if getattr(getattr(self.config.system, "dns", None), "ad_blocking_enabled", False):
            return True
        if os.environ.get("ROOSTOS_MOCK", "0") != "1" and os.environ.get("ROOSTOS_ETC_DIR") is None:
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.05)
                res = s.connect_ex(("127.0.0.1", 53))
                s.close()
                if res == 0:
                    return True
            except Exception:
                pass
        return False

    def _resolve_dns_servers(self, local_ip: str) -> str:
        """Resolves DNS servers to advertise to DHCP clients."""
        if self._is_local_dns_active():
            return local_ip
        forwarders = getattr(getattr(self.config.system, "dns", None), "forwarders", [])
        if forwarders:
            return ", ".join(forwarders)
        return local_ip

    def compile_kea_config(self) -> Dict[str, Any]:
        """Compiles unified RoostConfig structures into Kea DHCP4 JSON structure."""
        
        interfaces: List[str] = []
        subnets_config: List[Dict[str, Any]] = []
        subnet_id = 1

        # 1. Gather Subnets from bridges (LAN networks)
        for bridge in self.config.network.bridges:
            if not getattr(bridge, "dhcp_enabled", True):
                continue

            interfaces.append(bridge.name)
            
            # Resolve subnet network from bridge IP definition (e.g. '192.168.1.1/24')
            try:
                network = ipaddress.ip_network(bridge.ip, strict=False)
                subnet_str = str(network)
                bridge_ip = bridge.ip.split("/")[0]
            except ValueError:
                print(f"Warning: Invalid bridge IP configuration '{bridge.ip}'")
                continue

            # Standard or custom pool allocation range
            custom_start = getattr(bridge, "dhcp_pool_start", None)
            custom_end = getattr(bridge, "dhcp_pool_end", None)
            if custom_start and custom_end:
                pool_start = custom_start
                pool_end = custom_end
            else:
                network_hosts = list(network.hosts())
                if len(network_hosts) > 200:
                    base_ip = str(network.network_address).rsplit(".", 1)[0]
                    pool_start = f"{base_ip}.100"
                    pool_end = f"{base_ip}.250"
                else:
                    pool_start = str(network_hosts[min(5, len(network_hosts)-1)])
                    pool_end = str(network_hosts[-1])

            # Gather static IP allocations falling inside this subnet
            reservations: List[Dict[str, Any]] = []
            for device in self.config.devices:
                if device.static_ip and self._ip_in_subnet(device.static_ip, subnet_str):
                    reservations.append({
                        "hw-address": device.mac,
                        "ip-address": device.static_ip
                    })

            subnets_config.append({
                "id": subnet_id,
                "subnet": subnet_str,
                "pools": [{"pool": f"{pool_start} - {pool_end}"}],
                "interface": bridge.name,
                "option-data": [
                    {
                        "name": "routers",
                        "data": bridge_ip
                    },
                    {
                        "name": "domain-name-servers",
                        "data": self._resolve_dns_servers(bridge_ip)
                    }
                ],
                "reservations": reservations
            })
            subnet_id += 1

        # 2. Gather Subnets from isolated VLAN interfaces
        for vlan in self.config.network.vlans:
            if not getattr(vlan, "dhcp_enabled", True):
                continue

            interfaces.append(vlan.name)
            try:
                network = ipaddress.ip_network(vlan.ip, strict=False)
                subnet_str = str(network)
                vlan_ip = vlan.ip.split("/")[0]
            except ValueError:
                print(f"Warning: Invalid VLAN IP configuration '{vlan.ip}'")
                continue

            # Standard or custom pool allocation range
            custom_start = getattr(vlan, "dhcp_pool_start", None)
            custom_end = getattr(vlan, "dhcp_pool_end", None)
            if custom_start and custom_end:
                pool_start = custom_start
                pool_end = custom_end
            else:
                base_ip = str(network.network_address).rsplit(".", 1)[0]
                pool_start = f"{base_ip}.100"
                pool_end = f"{base_ip}.250"

            reservations = []
            for device in self.config.devices:
                if device.static_ip and self._ip_in_subnet(device.static_ip, subnet_str):
                    reservations.append({
                        "hw-address": device.mac,
                        "ip-address": device.static_ip
                    })

            subnets_config.append({
                "id": subnet_id,
                "subnet": subnet_str,
                "pools": [{"pool": f"{pool_start} - {pool_end}"}],
                "interface": vlan.name,
                "option-data": [
                    {
                        "name": "routers",
                        "data": vlan_ip
                    },
                    {
                        "name": "domain-name-servers",
                        "data": self._resolve_dns_servers(vlan_ip)
                    }
                ],
                "reservations": reservations
            })
            subnet_id += 1

        # Dynamically locate installed run-script hook library across architectures
        candidate_hook_paths = [
            "/usr/lib/aarch64-linux-gnu/kea/hooks/libdhcp_run_script.so",
            "/usr/lib/x86_64-linux-gnu/kea/hooks/libdhcp_run_script.so",
            "/usr/lib/arm-linux-gnueabihf/kea/hooks/libdhcp_run_script.so",
            "/usr/lib/kea/hooks/libdhcp_run_script.so",
            "/usr/local/lib/kea/hooks/libdhcp_run_script.so",
        ]
        hook_path = next((p for p in candidate_hook_paths if os.path.exists(p)), None)
        hooks_libraries: List[Dict[str, Any]] = []
        if hook_path and os.path.exists("/usr/local/bin/roost-dhcp-hook"):
            hooks_libraries.append({
                "library": hook_path,
                "parameters": {
                    "name": "/usr/local/bin/roost-dhcp-hook",
                    "sync": False
                }
            })

        # Standard Kea run parameters
        dhcp4_dict: Dict[str, Any] = {
            "interfaces-config": {
                "interfaces": interfaces if interfaces else ["*"]
            },
            "control-socket": {
                "socket-type": "unix",
                "socket-name": "/run/kea/kea-dhcp4-ctrl.sock"
            },
            "lease-database": {
                "type": "memfile",
                "persist": True,
                "name": "/var/lib/kea/kea-leases4.csv"
            },
            "subnet4": subnets_config
        }
        if hooks_libraries:
            dhcp4_dict["hooks-libraries"] = hooks_libraries

        return {"Dhcp4": dhcp4_dict}

    def write_config(self) -> None:
        """Writes the compiled JSON Kea configuration cleanly to disk target path."""
        target_dir = os.path.dirname(self.target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
            
        compiled = self.compile_kea_config()
        with open(self.target_path, "w") as f:
            json.dump(compiled, f, indent=4)
        print(f"Kea DHCP4 configuration written successfully to {self.target_path}")
