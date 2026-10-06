"""Universal guided setup wizard for RoostOS."""

import os
import sys
import json
import yaml
import shutil
import subprocess
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
        handlers = {
            NodeRole.GATEWAY: lambda: self._setup_gateway(gateway_params, env),
            NodeRole.CONTROLLER: lambda: self._setup_controller(controller_params, env),
            NodeRole.WORKSTATION: lambda: self._setup_workstation(workstation_params, env),
            NodeRole.STANDALONE: lambda: self._setup_standalone(gateway_params, controller_params, env),
            NodeRole.EDGE_GATEWAY: lambda: self._setup_edge_gateway(edge_params, env),
        }
        if target_role in handlers:
            return handlers[target_role]()
        return SetupResult(success=True, role=target_role, message=f"Configured node with role: {target_role.value}")

    def _setup_gateway(self, params: Optional[GatewayConfigParams], env: SystemEnvironment) -> SetupResult:
        """Configures system as an Edge Gateway Router."""
        if params is None:
            eth_ifaces = [i.name for i in env.interfaces if not i.is_wireless and i.name != "lo"]
            wan = eth_ifaces[0] if eth_ifaces else "eth0"
            lan = eth_ifaces[1:] if len(eth_ifaces) > 1 else ["eth1"]
            params = GatewayConfigParams(wan_interface=wan, lan_interfaces=lan)

        packages = ["nftables", "kea-dhcp4-server", "wireguard"]
        self._install_packages(packages)
        if not self._is_package_installed("kea-dhcp4-server"):
            return SetupResult(success=False, role=NodeRole.GATEWAY, message="Kea DHCP server (kea-dhcp4-server) is required for router mode but is not installed.")

        net_cfg = {
            "network": {
                "interfaces": [{"name": params.wan_interface, "role": "wan", "dhcp": params.wan_proto == "dhcp"}]
                + [{"name": iface, "role": "lan", "bridge": "br0"} for iface in params.lan_interfaces],
                "bridges": [{"name": "br0", "ip": f"{params.lan_ip}/24", "dhcp_enabled": params.dhcp_enabled, "dhcp_pool_start": params.dhcp_start, "dhcp_pool_end": params.dhcp_end}],
            }
        }
        is_tech = getattr(params, "dns_subsystem", "local") == "technitium"
        sys_cfg = {"system": {"hostname": "roost-gateway", "dns": {"forwarders": params.dns_servers, "ad_blocking_enabled": is_tech}, "cluster": {"roles": ["gateway_router"]}}}
        fw_rules = []
        if getattr(params, "allow_wan_ssh", False):
            fw_rules.append({"name": "Allow SSH (WAN)", "interface": params.wan_interface, "protocol": "tcp", "port": 22, "action": "accept", "enabled": True})
        if getattr(params, "allow_wan_web", False):
            fw_rules.append({"name": "Allow RoostOS Web (WAN)", "interface": params.wan_interface, "protocol": "tcp", "port": 8000, "action": "accept", "enabled": True})
        fw_cfg = {"firewall": {"rules": fw_rules, "port_forwards": []}}
        plg_cfg = {"plugins": [{"id": "technitium-dns", "name": "Technitium DNS Server", "enabled": True, "known_services": ["dnsServer", "dnsFilter"], "containers": [{"name": "dns-server", "image": "technitium/dns-server:latest"}]}]} if is_tech else {"plugins": []}

        created_files = [self._save_yaml(fn, dat) for fn, dat in [("network.yaml", net_cfg), ("system.yaml", sys_cfg), ("firewall.yaml", fw_cfg), ("plugins.yaml", plg_cfg)]]

        if not self.mock_install and os.environ.get("ROOSTOS_MOCK_INSTALL") != "1" and os.getuid() == 0:
            cmds = [["ip", "link", "add", "name", "br0", "type", "bridge"]]
            for iface in params.lan_interfaces:
                cmds.extend([["ip", "link", "set", iface, "master", "br0"], ["ip", "link", "set", iface, "up"]])
            cmds.extend([["ip", "addr", "add", f"{params.lan_ip}/24", "dev", "br0"], ["ip", "link", "set", "br0", "up"]])
            for c in cmds:
                subprocess.run(c, check=False, capture_output=True)
        self._apply_dns_resolv(params.dns_servers)

        for svc in ("systemd-networkd.service", "roostos-engine.service", "roostos-node.service", "kea-dhcp4-server.service", "nftables.service"):
            self._enable_service(svc)

        return SetupResult(
            success=True, role=NodeRole.GATEWAY, installed_packages=packages, created_configs=created_files,
            dashboard_url=f"http://{params.lan_ip}:8000", message=f"Gateway Router successfully configured. Web Console at http://{params.lan_ip}:8000"
        )

    def _setup_controller(self, params: Optional[ControllerConfigParams], env: SystemEnvironment) -> SetupResult:
        """Configures system as the Central Controller and Application Server."""
        if params is None:
            gw_ip = env.discovered_gateways[0].ip if env.discovered_gateways else None
            params = ControllerConfigParams(adopted_gateway_ip=gw_ip)

        packages = ["mosquitto"]
        self._install_packages(packages)

        sys_cfg = {"system": {"hostname": "roost-controller", "domain": params.domain, "cluster": {"is_controller": True, "roles": ["controller", "compute_node"]}}}
        nodes = [{"id": "controller-01", "name": "RoostOS Central Controller", "roles": ["controller", "compute_node"], "management_ip": "127.0.0.1"}]
        if params.adopted_gateway_ip:
            nodes.append({"id": "gateway-01", "name": "Adopted Edge Gateway", "roles": ["gateway_router"], "management_ip": params.adopted_gateway_ip})

        created_files = [self._save_yaml("system.yaml", sys_cfg), self._save_yaml("nodes.yaml", {"nodes": nodes})]
        for svc in ("mosquitto.service", "roostos-engine.service", "roostos-node.service"):
            self._enable_service(svc)

        return SetupResult(
            success=True, role=NodeRole.CONTROLLER, installed_packages=packages, created_configs=created_files,
            dashboard_url="http://localhost:8000", message="Central Controller successfully configured. Web Console at http://localhost:8000"
        )

    def _setup_workstation(self, params: Optional[WorkstationConfigParams], env: SystemEnvironment) -> SetupResult:
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
        tg_path = os.path.join(tg_dir, "config.json")
        tg_config = {
            "mqtt_host": params.controller_host, "mqtt_port": params.controller_port, "join_token": params.join_token or "",
            "users": {u: {"daily_limit_seconds": 7200} for u in params.family_user_mapping} or {"default": {"daily_limit_seconds": 7200}},
        }
        with open(tg_path, "w") as f:
            json.dump(tg_config, f, indent=2)

        self._enable_service("roostos-timeguardd.service")
        return SetupResult(
            success=True, role=NodeRole.WORKSTATION, installed_packages=packages, created_configs=[tg_path],
            message=f"Workstation enrolled with RoostOS TimeGuard. Connected to {params.controller_host}"
        )

    def _setup_standalone(
        self, gw_params: Optional[GatewayConfigParams], ctrl_params: Optional[ControllerConfigParams], env: SystemEnvironment
    ) -> SetupResult:
        """Configures All-in-One Standalone system combining Gateway and Controller."""
        gw_res = self._setup_gateway(gw_params, env)
        if not gw_res.success:
            return gw_res
        ctrl_res = self._setup_controller(ctrl_params, env)

        dns_servers = gw_params.dns_servers if gw_params else ["1.1.1.1", "8.8.8.8"]
        domain = ctrl_params.domain if ctrl_params else "roostos.local"
        is_tech = getattr(gw_params, "dns_subsystem", "local") == "technitium" if gw_params else False
        standalone_sys_cfg = {
            "system": {
                "hostname": "roost-router", "domain": domain, "dns": {"forwarders": dns_servers, "ad_blocking_enabled": is_tech},
                "cluster": {"is_controller": True, "roles": ["gateway_router", "controller", "compute_node"]},
            }
        }
        self._save_yaml("system.yaml", standalone_sys_cfg)
        self._apply_dns_resolv(dns_servers)

        for svc in ("mosquitto.service", "roostos-engine.service"):
            self._enable_service(svc)

        combined_packages = list(dict.fromkeys(gw_res.installed_packages + ctrl_res.installed_packages))
        combined_configs = list(dict.fromkeys(gw_res.created_configs + ctrl_res.created_configs))
        return SetupResult(
            success=True, role=NodeRole.STANDALONE, installed_packages=combined_packages, created_configs=combined_configs,
            dashboard_url=gw_res.dashboard_url, message="Standalone All-in-One Router & Controller successfully configured."
        )

    def _setup_edge_gateway(self, params: Optional[EdgeGatewayConfigParams], env: SystemEnvironment) -> SetupResult:
        """Configures system as an Ingress Edge Gateway on a cloud VPS."""
        wan = params.wan_interface if params else "eth0"
        packages = ["wireguard", "nftables"]
        self._install_packages(packages)

        sys_cfg = {"system": {"hostname": "roost-edge", "cluster": {"roles": ["edge_gateway"]}}}
        net_cfg = {"network": {"interfaces": [{"name": wan, "role": "wan", "dhcp": True}], "gateways": [{"id": "default", "name": "VPS Gateway", "interface": wan}]}}
        created_files = [self._save_yaml("system.yaml", sys_cfg), self._save_yaml("network.yaml", net_cfg)]
        self._enable_service("roostos-node.service")

        return SetupResult(
            success=True, role=NodeRole.EDGE_GATEWAY, installed_packages=packages, created_configs=created_files,
            dashboard_url="http://localhost:8000", message="Edge Gateway configured. Generate bootstrap token with: roostos edge token"
        )

    def _apply_dns_resolv(self, dns_servers: Optional[List[str]]) -> None:
        """Applies initial DNS forwarders to /etc/resolv.conf during bootstrap."""
        if not self.mock_install and os.environ.get("ROOSTOS_MOCK_INSTALL") != "1" and os.getuid() == 0:
            try:
                resolv = "/etc/resolv.conf"
                if os.path.islink(resolv) and not os.path.exists(resolv):
                    os.unlink(resolv)
                servers = dns_servers or ["1.1.1.1", "8.8.8.8"]
                with open(resolv, "w") as f:
                    f.write("# Generated by RoostOS\n" + "".join(f"nameserver {d}\n" for d in servers))
            except Exception:
                pass

    def _is_package_installed(self, pkg: str) -> bool:
        """Checks if a debian package or binary is installed on the system."""
        if self.mock_install or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1":
            return True
        if pkg == "kea-dhcp4-server" and (shutil.which("kea-dhcp4") or any(os.path.exists(f"/usr/{b}/kea-dhcp4") for b in ("sbin", "bin"))):
            return True
        try:
            return subprocess.run(["dpkg", "-s", pkg], capture_output=True).returncode == 0
        except Exception:
            return False

    def _install_packages(self, packages: List[str]) -> None:
        """Installs packages via apt-get unless mock_install is True."""
        if not packages or self.mock_install or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1" or os.getuid() != 0:
            return
        try:
            needed = [p for p in packages if not self._is_package_installed(p)]
            if needed:
                print(f"Installing required system packages: {', '.join(needed)}...")
                subprocess.run(["apt-get", "update", "-qq"], check=False)
                subprocess.run(["apt-get", "install", "-y", "--no-install-recommends"] + needed, check=True)
        except Exception as e:
            print(f"Warning: Package installation via apt failed: {e}", file=sys.stderr)

    def _enable_service(self, service_name: str) -> None:
        """Enables and starts a systemd service."""
        if self.mock_install or os.environ.get("ROOSTOS_MOCK_INSTALL") == "1" or os.getuid() != 0:
            return
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
