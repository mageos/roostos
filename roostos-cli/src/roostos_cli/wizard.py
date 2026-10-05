"""Universal guided setup wizard for RoostOS."""

import os
import sys
import json
import yaml
from typing import List, Optional, Dict, Any

from roostos_cli.models import (
    NodeRole,
    SystemEnvironment,
    GatewayConfigParams,
    ControllerConfigParams,
    WorkstationConfigParams,
    EdgeGatewayConfigParams,
    SetupResult,
)
from roostos_cli.inspector import EnvironmentInspector
from roostos_cli.discovery import NetworkDiscoverer


class SetupWizard:
    """Coordinates hardware introspection, role selection, package installation, and config provisioning."""

    def __init__(self, config_dir: str = "/etc/roostos", mock_install: bool = False):
        self.config_dir = config_dir
        self.mock_install = mock_install

    def run_setup(
        self,
        role: Optional[NodeRole] = None,
        gateway_params: Optional[GatewayConfigParams] = None,
        controller_params: Optional[ControllerConfigParams] = None,
        workstation_params: Optional[WorkstationConfigParams] = None,
        edge_params: Optional[EdgeGatewayConfigParams] = None,
        env: Optional[SystemEnvironment] = None,
    ) -> SetupResult:
        """Executes setup workflow for the chosen or detected role."""
        if env is None:
            env = EnvironmentInspector.inspect()
            env.discovered_gateways = NetworkDiscoverer.discover_gateways()
            env.discovered_controllers = NetworkDiscoverer.discover_controllers()

        target_role = role or env.recommended_role

        if target_role == NodeRole.GATEWAY:
            return self._setup_gateway(gateway_params, env)
        elif target_role == NodeRole.CONTROLLER:
            return self._setup_controller(controller_params, env)
        elif target_role == NodeRole.WORKSTATION:
            return self._setup_workstation(workstation_params, env)
        elif target_role == NodeRole.STANDALONE:
            return self._setup_standalone(gateway_params, controller_params, env)
        elif target_role == NodeRole.EDGE_GATEWAY:
            return self._setup_edge_gateway(edge_params, env)
        return SetupResult(success=True, role=target_role, message=f"Configured node with role: {target_role.value}")

    def _setup_gateway(
        self,
        params: Optional[GatewayConfigParams],
        env: SystemEnvironment
    ) -> SetupResult:
        """Configures system as an Edge Gateway Router."""
        if params is None:
            eth_ifaces = [i.name for i in env.interfaces if not i.is_wireless and i.name != "lo"]
            wan = eth_ifaces[0] if eth_ifaces else "eth0"
            lan = eth_ifaces[1:] if len(eth_ifaces) > 1 else ["eth1"]
            params = GatewayConfigParams(
                wan_interface=wan,
                lan_interfaces=lan,
            )

        packages = ["nftables", "kea-dhcp4-server", "wireguard"]
        self._install_packages(packages)

        net_cfg = {
            "network": {
                "interfaces": [{"name": params.wan_interface, "role": "wan", "dhcp": params.wan_proto == "dhcp"}]
                + [{"name": iface, "role": "lan", "bridge": "br0"} for iface in params.lan_interfaces],
                "bridges": [{
                    "name": "br0", "ip": f"{params.lan_ip}/24", "dhcp_enabled": params.dhcp_enabled,
                    "dhcp_pool_start": params.dhcp_start, "dhcp_pool_end": params.dhcp_end,
                }]
            }
        }
        sys_cfg = {
            "system": {
                "hostname": "roost-gateway",
                "dns": {"forwarders": params.dns_servers},
                "cluster": {"roles": ["gateway_router"]}
            }
        }
        created_files = [
            self._save_yaml("network.yaml", net_cfg),
            self._save_yaml("system.yaml", sys_cfg),
        ]

        self._enable_service("roostos-node.service")
        self._enable_service("kea-dhcp4-server.service")
        self._enable_service("nftables.service")

        return SetupResult(
            success=True,
            role=NodeRole.GATEWAY,
            installed_packages=packages,
            created_configs=created_files,
            dashboard_url=f"http://{params.lan_ip}:8000",
            message=f"Gateway Router successfully configured. Web Console at http://{params.lan_ip}:8000"
        )

    def _setup_controller(
        self,
        params: Optional[ControllerConfigParams],
        env: SystemEnvironment
    ) -> SetupResult:
        """Configures system as the Central Controller and Application Server."""
        if params is None:
            gw_ip = env.discovered_gateways[0].ip if env.discovered_gateways else None
            params = ControllerConfigParams(adopted_gateway_ip=gw_ip)

        packages = ["mosquitto"]
        self._install_packages(packages)

        sys_cfg = {
            "system": {
                "hostname": "roost-controller", "domain": params.domain,
                "cluster": {"is_controller": True, "roles": ["controller", "compute_node"]}
            }
        }
        nodes = [{
            "id": "controller-01", "name": "RoostOS Central Controller",
            "roles": ["controller", "compute_node"], "management_ip": "127.0.0.1"
        }]
        if params.adopted_gateway_ip:
            nodes.append({
                "id": "gateway-01", "name": "Adopted Edge Gateway",
                "roles": ["gateway_router"], "management_ip": params.adopted_gateway_ip
            })

        created_files = [
            self._save_yaml("system.yaml", sys_cfg),
            self._save_yaml("nodes.yaml", {"nodes": nodes}),
        ]

        self._enable_service("mosquitto.service")
        self._enable_service("roostos-engine.service")
        self._enable_service("roostos-node.service")

        return SetupResult(
            success=True,
            role=NodeRole.CONTROLLER,
            installed_packages=packages,
            created_configs=created_files,
            dashboard_url="http://localhost:8000",
            message="Central Controller successfully configured. Web Console at http://localhost:8000"
        )

    def _setup_workstation(
        self,
        params: Optional[WorkstationConfigParams],
        env: SystemEnvironment
    ) -> SetupResult:
        """Configures system as a Managed Client Workstation with TimeGuard screen time."""
        if params is None:
            ctrl_ip = env.discovered_controllers[0].ip if env.discovered_controllers else "roostos.local"
            params = WorkstationConfigParams(controller_host=ctrl_ip)

        packages: List[str] = []
        if params.enable_domain_login:
            packages.extend(["sssd", "realmd", "adcli", "oddjob-mkhomedir"])
        self._install_packages(packages)

        tg_dir = os.path.join(self.config_dir, "timeguardd") if self.config_dir != "/etc/roostos" else "/etc/roostos-timeguardd"
        os.makedirs(tg_dir, exist_ok=True)
        tg_config = {
            "mqtt_host": params.controller_host,
            "mqtt_port": params.controller_port,
            "join_token": params.join_token or "",
            "users": {u: {"daily_limit_seconds": 7200} for u in params.family_user_mapping} or {"default": {"daily_limit_seconds": 7200}}
        }
        tg_path = os.path.join(tg_dir, "config.json")
        with open(tg_path, "w") as f:
            json.dump(tg_config, f, indent=2)

        self._enable_service("roostos-timeguardd.service")

        return SetupResult(
            success=True,
            role=NodeRole.WORKSTATION,
            installed_packages=packages,
            created_configs=[tg_path],
            message=f"Workstation enrolled with RoostOS TimeGuard. Connected to {params.controller_host}"
        )

    def _setup_standalone(
        self,
        gw_params: Optional[GatewayConfigParams],
        ctrl_params: Optional[ControllerConfigParams],
        env: SystemEnvironment
    ) -> SetupResult:
        """Configures All-in-One Standalone system combining Gateway and Controller."""
        gw_res = self._setup_gateway(gw_params, env)
        ctrl_res = self._setup_controller(ctrl_params, env)

        dns_servers = gw_params.dns_servers if gw_params else ["1.1.1.1", "8.8.8.8"]
        domain = ctrl_params.domain if ctrl_params else "roostos.local"
        standalone_sys_cfg = {
            "system": {
                "hostname": "roost-router", "domain": domain, "dns": {"forwarders": dns_servers},
                "cluster": {"is_controller": True, "roles": ["gateway_router", "controller", "compute_node"]}
            }
        }
        self._save_yaml("system.yaml", standalone_sys_cfg)

        self._enable_service("mosquitto.service")
        self._enable_service("roostos-engine.service")

        combined_packages = list(dict.fromkeys(gw_res.installed_packages + ctrl_res.installed_packages))
        combined_configs = list(dict.fromkeys(gw_res.created_configs + ctrl_res.created_configs))

        return SetupResult(
            success=True,
            role=NodeRole.STANDALONE,
            installed_packages=combined_packages,
            created_configs=combined_configs,
            dashboard_url=gw_res.dashboard_url,
            message="Standalone All-in-One Router & Controller successfully configured."
        )

    def _setup_edge_gateway(
        self,
        params: Optional[EdgeGatewayConfigParams],
        env: SystemEnvironment,
    ) -> SetupResult:
        """Configures system as an Ingress Edge Gateway on a cloud VPS."""
        wan = params.wan_interface if params else "eth0"
        packages = ["wireguard", "nftables"]
        self._install_packages(packages)

        sys_cfg = {"system": {"hostname": "roost-edge", "cluster": {"roles": ["edge_gateway"]}}}
        net_cfg = {
            "network": {
                "interfaces": [{"name": wan, "role": "wan", "dhcp": True}],
                "gateways": [{"id": "default", "name": "VPS Gateway", "interface": wan}],
            }
        }
        created_files = [
            self._save_yaml("system.yaml", sys_cfg),
            self._save_yaml("network.yaml", net_cfg),
        ]

        self._enable_service("roostos-node.service")

        return SetupResult(
            success=True,
            role=NodeRole.EDGE_GATEWAY,
            installed_packages=packages,
            created_configs=created_files,
            dashboard_url="http://localhost:8000",
            message="Edge Gateway configured. Generate bootstrap token with: roostos edge token",
        )

    def _install_packages(self, packages: List[str]) -> None:
        """Installs packages via apt-get unless mock_install is True."""
        if not packages or self.mock_install or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1" or os.getuid() != 0:
            return
        import subprocess
        try:
            needed: List[str] = []
            for pkg in packages:
                res = subprocess.run(["dpkg", "-s", pkg], capture_output=True, text=True)
                if res.returncode != 0:
                    needed.append(pkg)
            if not needed:
                return
            print(f"Installing required system packages: {', '.join(needed)}...")
            subprocess.run(["apt-get", "update", "-qq"], check=False)
            subprocess.run(["apt-get", "install", "-y", "--no-install-recommends"] + needed, check=True)
        except Exception as e:
            print(f"Warning: Package installation via apt failed: {e}", file=sys.stderr)

    def _enable_service(self, service_name: str) -> None:
        """Enables and starts a systemd service."""
        if self.mock_install or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1" or os.getuid() != 0:
            return
        import subprocess
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)
            subprocess.run(["systemctl", "enable", service_name], check=False, capture_output=True)
            if os.path.isdir("/run/systemd/system"):
                subprocess.run(["systemctl", "restart", service_name], check=False, capture_output=True)
        except Exception as e:
            print(f"Warning: Failed to enable {service_name}: {e}", file=sys.stderr)

    def _save_yaml(self, filename: str, data: Dict[str, Any]) -> str:
        os.makedirs(self.config_dir, exist_ok=True)
        path = os.path.join(self.config_dir, filename)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        return path
