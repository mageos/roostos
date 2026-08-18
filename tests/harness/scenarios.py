import os
import shutil
from typing import Dict, List, Optional
from tests.harness.models import ScenarioConfig


AVAILABLE_SCENARIOS: Dict[str, ScenarioConfig] = {
    "default": ScenarioConfig(
        name="default",
        description="Standard single-router deployment with WAN (eth0), LAN (eth1), and Guest network (eth2)",
        config_dir="test-harness/scenarios/default",
        expected_interfaces=["eth0", "eth1", "eth2"],
        gateway_id="default",
    ),
    "multi-wan": ScenarioConfig(
        name="multi-wan",
        description="Dual-WAN setup with primary WAN (eth0), backup WAN (eth1), and LAN bridge (eth2)",
        config_dir="test-harness/scenarios/multi-wan",
        expected_interfaces=["eth0", "eth1", "eth2"],
        gateway_id="default",
    ),
    "mesh-satellite": ScenarioConfig(
        name="mesh-satellite",
        description="Satellite mesh node operating in 802.11s bridged backhaul mode",
        config_dir="test-harness/scenarios/mesh-satellite",
        expected_interfaces=["eth0", "wlan1"],
        gateway_id="default",
    ),
    "vpn-gateway": ScenarioConfig(
        name="vpn-gateway",
        description="Policy-routed Wireguard VPN gateway routing tagged clients through encrypted tunnel",
        config_dir="test-harness/scenarios/vpn-gateway",
        expected_interfaces=["eth0", "eth1", "wg-vpn-eu"],
        gateway_id="vpn_eu",
    ),
}


class ScenarioManager:
    """Manages loading and staging scenario configurations for the test harness."""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

    def get_scenario(self, name: str) -> ScenarioConfig:
        """Retrieves scenario metadata by name. Defaults to 'default'."""
        if name not in AVAILABLE_SCENARIOS:
            raise ValueError(f"Unknown scenario '{name}'. Available: {list(AVAILABLE_SCENARIOS.keys())}")
        return AVAILABLE_SCENARIOS[name]

    def list_scenarios(self) -> List[ScenarioConfig]:
        """Lists all registered deployment scenarios."""
        return list(AVAILABLE_SCENARIOS.values())

    def stage_scenario_config(self, scenario_name: str, target_dir: str) -> str:
        """Copies scenario YAML configs to target directory for container mounting."""
        scenario = self.get_scenario(scenario_name)
        source_dir = os.path.join(self.base_dir, scenario.config_dir)
        os.makedirs(target_dir, exist_ok=True)
        
        if os.path.isdir(source_dir):
            for item in os.listdir(source_dir):
                s = os.path.join(source_dir, item)
                d = os.path.join(target_dir, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
                elif os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
        return target_dir
