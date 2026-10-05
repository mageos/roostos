"""Unit tests for the RoostOS Setup Wizard."""

import os
import yaml
import tempfile
from roostos_cli.models import (
    NodeRole,
    SystemEnvironment,
    GatewayConfigParams,
    ControllerConfigParams,
    WorkstationConfigParams,
)
from roostos_cli.wizard import SetupWizard


def test_wizard_setup_gateway():
    with tempfile.TemporaryDirectory() as tmpdir:
        wizard = SetupWizard(config_dir=tmpdir, mock_install=True)
        params = GatewayConfigParams(
            wan_interface="eth0",
            lan_interfaces=["eth1", "eth2"],
            lan_network="10.10.0.0/24",
            lan_ip="10.10.0.1",
            dhcp_enabled=True,
            dhcp_start="10.10.0.100",
            dhcp_end="10.10.0.200",
        )
        res = wizard.run_setup(role=NodeRole.GATEWAY, gateway_params=params)

        assert res.success is True
        assert res.role == NodeRole.GATEWAY
        assert "kea-dhcp4-server" in res.installed_packages
        assert "nftables" in res.installed_packages

        # Verify network.yaml written
        net_path = os.path.join(tmpdir, "network.yaml")
        assert os.path.exists(net_path)
        with open(net_path, "r") as f:
            data = yaml.safe_load(f)
        assert data["network"]["bridges"][0]["ip"] == "10.10.0.1/24"
        assert len(data["network"]["interfaces"]) == 3


def test_wizard_setup_controller():
    with tempfile.TemporaryDirectory() as tmpdir:
        wizard = SetupWizard(config_dir=tmpdir, mock_install=True)
        params = ControllerConfigParams(
            cluster_name="Lab Cluster",
            domain="lab.local",
            adopted_gateway_ip="192.168.1.1",
        )
        res = wizard.run_setup(role=NodeRole.CONTROLLER, controller_params=params)

        assert res.success is True
        assert res.role == NodeRole.CONTROLLER
        assert "mosquitto" in res.installed_packages

        # Verify nodes.yaml written
        nodes_path = os.path.join(tmpdir, "nodes.yaml")
        assert os.path.exists(nodes_path)
        with open(nodes_path, "r") as f:
            data = yaml.safe_load(f)
        assert len(data["nodes"]) == 2
        assert data["nodes"][1]["management_ip"] == "192.168.1.1"


def test_wizard_setup_workstation():
    with tempfile.TemporaryDirectory() as tmpdir:
        wizard = SetupWizard(config_dir=tmpdir, mock_install=True)
        params = WorkstationConfigParams(
            controller_host="192.168.1.50",
            controller_port=1883,
            family_user_mapping={"alice": "Alice Smith"},
            enable_domain_login=True,
        )
        res = wizard.run_setup(role=NodeRole.WORKSTATION, workstation_params=params)

        assert res.success is True
        assert res.role == NodeRole.WORKSTATION
        assert "sssd" in res.installed_packages


def test_wizard_setup_standalone():
    with tempfile.TemporaryDirectory() as tmpdir:
        wizard = SetupWizard(config_dir=tmpdir, mock_install=True)
        gw_params = GatewayConfigParams(
            wan_interface="eth0",
            lan_interfaces=["eth1"],
            lan_network="192.168.1.0/24",
            lan_ip="192.168.1.1",
            dns_servers=["1.1.1.1"],
        )
        ctrl_params = ControllerConfigParams(
            cluster_name="Home",
            domain="home.local",
        )
        res = wizard.run_setup(
            role=NodeRole.STANDALONE,
            gateway_params=gw_params,
            controller_params=ctrl_params,
        )

        assert res.success is True
        assert res.role == NodeRole.STANDALONE

        # Verify network.yaml and system.yaml
        sys_path = os.path.join(tmpdir, "system.yaml")
        assert os.path.exists(sys_path)
        with open(sys_path, "r") as f:
            sys_data = yaml.safe_load(f)

        cluster_cfg = sys_data["system"]["cluster"]
        assert cluster_cfg["is_controller"] is True
        assert "gateway_router" in cluster_cfg["roles"]
        assert "controller" in cluster_cfg["roles"]
        assert sys_data["system"]["dns"]["forwarders"] == ["1.1.1.1"]
        assert sys_data["system"]["domain"] == "home.local"
        assert os.path.exists(os.path.join(tmpdir, "network.yaml"))
