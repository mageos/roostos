import os
from pathlib import Path
import pytest
from tests.harness.scenarios import ScenarioManager, AVAILABLE_SCENARIOS


def test_scenario_manager_lists_scenarios() -> None:
    """Verifies that all standard deployment scenarios are registered and loadable."""
    manager = ScenarioManager()
    scenarios = manager.list_scenarios()
    
    names = [s.name for s in scenarios]
    assert "default" in names
    assert "multi-wan" in names
    assert "mesh-satellite" in names
    assert "vpn-gateway" in names


def test_scenario_manager_stage_configs(tmp_path: Path) -> None:
    """Verifies staging scenario configuration files to a target directory."""
    manager = ScenarioManager()
    staged = manager.stage_scenario_config("default", str(tmp_path))
    
    assert os.path.isfile(os.path.join(staged, "system.yaml"))
    assert os.path.isfile(os.path.join(staged, "network.yaml"))
    assert os.path.isfile(os.path.join(staged, "devices.yaml"))
    assert os.path.isfile(os.path.join(staged, "firewall.yaml"))
    assert os.path.isfile(os.path.join(staged, "schedules.yaml"))


def test_scenario_manager_unknown_scenario_raises() -> None:
    """Verifies that querying a non-existent scenario raises ValueError."""
    manager = ScenarioManager()
    with pytest.raises(ValueError, match="Unknown scenario"):
        manager.get_scenario("non-existent-scenario")
