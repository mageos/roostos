from abc import ABC, abstractmethod
import os
from roostos_engine.config import (
    RoostConfig,
    SystemConfig,
    NodesConfigFile,
    DevicesConfig,
    NetworkConfig,
    SchedulesConfig,
    FirewallConfig,
    PluginsConfig,
    load_config_directory,
    save_config_file,
)

class ConfigRepository(ABC):
    @abstractmethod
    def get_config(self) -> RoostConfig:
        pass

    @abstractmethod
    def save_system_config(self, data: SystemConfig) -> None:
        pass

    @abstractmethod
    def save_nodes_config(self, data: NodesConfigFile) -> None:
        pass

    @abstractmethod
    def save_devices_config(self, data: DevicesConfig) -> None:
        pass

    @abstractmethod
    def save_network_config(self, data: NetworkConfig) -> None:
        pass

    @abstractmethod
    def save_schedules_config(self, data: SchedulesConfig) -> None:
        pass

    @abstractmethod
    def save_firewall_config(self, data: FirewallConfig) -> None:
        pass

    @abstractmethod
    def save_plugins_config(self, data: PluginsConfig) -> None:
        pass


class YAMLConfigRepository(ConfigRepository):
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        try:
            os.makedirs(self.config_dir, exist_ok=True)
        except PermissionError:
            pass

    def get_config(self) -> RoostConfig:
        return load_config_directory(self.config_dir)

    def save_system_config(self, data: SystemConfig) -> None:
        save_config_file(self.config_dir, "system.yaml", data)

    def save_nodes_config(self, data: NodesConfigFile) -> None:
        save_config_file(self.config_dir, "nodes.yaml", data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        save_config_file(self.config_dir, "devices.yaml", data)

    def save_network_config(self, data: NetworkConfig) -> None:
        save_config_file(self.config_dir, "network.yaml", data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        save_config_file(self.config_dir, "schedules.yaml", data)

    def save_firewall_config(self, data: FirewallConfig) -> None:
        save_config_file(self.config_dir, "firewall.yaml", data)

    def save_plugins_config(self, data: PluginsConfig) -> None:
        save_config_file(self.config_dir, "plugins.yaml", data)


class StagingConfigRepository(ConfigRepository):
    def __init__(self, active_dir: str, staged_dir: str):
        self.active_repo = YAMLConfigRepository(active_dir)
        self.staged_dir = staged_dir
        try:
            os.makedirs(self.staged_dir, exist_ok=True)
        except PermissionError:
            pass

    def get_config(self) -> RoostConfig:
        config = self.active_repo.get_config()
        
        if not os.path.exists(self.staged_dir):
            return config

        staged_files = [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]
        if staged_files:
            import yaml
            if "system.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "system.yaml"), "r") as f:
                    parsed = SystemConfig.model_validate(yaml.safe_load(f) or {})
                    config.system = parsed.system
                    config.users = parsed.users
            if "nodes.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "nodes.yaml"), "r") as f:
                    parsed_nodes = NodesConfigFile.model_validate(yaml.safe_load(f) or {})
                    config.nodes = parsed_nodes.nodes
            if "network.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "network.yaml"), "r") as f:
                    parsed_net = NetworkConfig.model_validate(yaml.safe_load(f) or {})
                    config.network = parsed_net.network
                    config.wifi = parsed_net.wifi
                    config.vpns = parsed_net.vpns
            if "devices.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "devices.yaml"), "r") as f:
                    parsed_dev = DevicesConfig.model_validate(yaml.safe_load(f) or {})
                    config.people = parsed_dev.people
                    config.buildings = parsed_dev.buildings
                    config.rooms = parsed_dev.rooms
                    config.devices = parsed_dev.devices
            if "schedules.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "schedules.yaml"), "r") as f:
                    parsed_sch = SchedulesConfig.model_validate(yaml.safe_load(f) or {})
                    config.schedules = parsed_sch.firewall.schedules if parsed_sch.firewall else []
            if "firewall.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "firewall.yaml"), "r") as f:
                    parsed_fw = FirewallConfig.model_validate(yaml.safe_load(f) or {})
                    if parsed_fw.firewall:
                        config.firewall.port_forwards = parsed_fw.firewall.port_forwards
                        config.firewall.rules = parsed_fw.firewall.rules
            if "plugins.yaml" in staged_files:
                with open(os.path.join(self.staged_dir, "plugins.yaml"), "r") as f:
                    parsed_plg = PluginsConfig.model_validate(yaml.safe_load(f) or {})
                    config.plugins = parsed_plg.plugins
                
        return config

    def save_system_config(self, data: SystemConfig) -> None:
        save_config_file(self.staged_dir, "system.yaml", data)

    def save_nodes_config(self, data: NodesConfigFile) -> None:
        save_config_file(self.staged_dir, "nodes.yaml", data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        save_config_file(self.staged_dir, "devices.yaml", data)

    def save_network_config(self, data: NetworkConfig) -> None:
        save_config_file(self.staged_dir, "network.yaml", data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        save_config_file(self.staged_dir, "schedules.yaml", data)

    def save_firewall_config(self, data: FirewallConfig) -> None:
        save_config_file(self.staged_dir, "firewall.yaml", data)

    def save_plugins_config(self, data: PluginsConfig) -> None:
        save_config_file(self.staged_dir, "plugins.yaml", data)

    def commit_staged_changes(self) -> None:
        """Copies all staged configurations to active directory and deletes them from stage."""
        if not os.path.exists(self.staged_dir):
            return
        staged_files = [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]
        for filename in staged_files:
            src = os.path.join(self.staged_dir, filename)
            dst = os.path.join(self.active_repo.config_dir, filename)
            import shutil
            shutil.copy2(src, dst)
            os.remove(src)

    def discard_staged_changes(self) -> None:
        """Deletes all staged files."""
        if not os.path.exists(self.staged_dir):
            return
        staged_files = [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]
        for filename in staged_files:
            os.remove(os.path.join(self.staged_dir, filename))

    def has_staged_changes(self) -> bool:
        if not os.path.exists(self.staged_dir):
            return False
        return len([f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]) > 0


class InMemoryConfigRepository(ConfigRepository):
    """In-memory implementation of ConfigRepository for isolated unit tests."""

    def __init__(self, initial_config: RoostConfig = None):
        if initial_config is not None:
            self._config = initial_config
        else:
            from roostos_engine.models import (
                SystemSettings, NetworkSettings, FirewallSettings
            )
            self._config = RoostConfig(
                system=SystemSettings(hostname="roost-router", domain="lan"),
                users=[],
                nodes=[],
                network=NetworkSettings(interfaces=[], bridges=[], vlans=[], gateways=[], zones=[]),
                vpns=[],
                people=[],
                buildings=[],
                rooms=[],
                devices=[],
                firewall=FirewallSettings(schedules=[], port_forwards=[], rules=[]),
                schedules=[],
                plugins=[],
            )

    def get_config(self) -> RoostConfig:
        return self._config.model_copy(deep=True)

    def save_system_config(self, data: SystemConfig) -> None:
        self._config.system = data.system
        self._config.users = data.users

    def save_nodes_config(self, data: NodesConfigFile) -> None:
        self._config.nodes = data.nodes

    def save_devices_config(self, data: DevicesConfig) -> None:
        self._config.people = data.people
        self._config.buildings = data.buildings
        self._config.rooms = data.rooms
        self._config.devices = data.devices

    def save_network_config(self, data: NetworkConfig) -> None:
        self._config.network = data.network
        self._config.wifi = data.wifi
        self._config.vpns = data.vpns

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        self._config.firewall.schedules = data.schedules

    def save_firewall_config(self, data: FirewallConfig) -> None:
        self._config.firewall.port_forwards = data.port_forwards
        self._config.firewall.rules = data.rules

    def save_plugins_config(self, data: PluginsConfig) -> None:
        self._config.plugins = data.plugins


