from abc import ABC, abstractmethod
import os
from roostos_engine.config import (
    RoostConfig,
    SystemConfig,
    DevicesConfig,
    NetworkConfig,
    SchedulesConfig,
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
    def save_devices_config(self, data: DevicesConfig) -> None:
        pass

    @abstractmethod
    def save_network_config(self, data: NetworkConfig) -> None:
        pass

    @abstractmethod
    def save_schedules_config(self, data: SchedulesConfig) -> None:
        pass

    @abstractmethod
    def save_plugins_config(self, data: PluginsConfig) -> None:
        pass


class YAMLConfigRepository(ConfigRepository):
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)

    def get_config(self) -> RoostConfig:
        return load_config_directory(self.config_dir)

    def save_system_config(self, data: SystemConfig) -> None:
        save_config_file(self.config_dir, "system.yaml", data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        save_config_file(self.config_dir, "devices.yaml", data)

    def save_network_config(self, data: NetworkConfig) -> None:
        save_config_file(self.config_dir, "network.yaml", data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        save_config_file(self.config_dir, "schedules.yaml", data)

    def save_plugins_config(self, data: PluginsConfig) -> None:
        save_config_file(self.config_dir, "plugins.yaml", data)


class StagingConfigRepository(ConfigRepository):
    def __init__(self, active_dir: str, staged_dir: str):
        self.active_repo = YAMLConfigRepository(active_dir)
        self.staged_dir = staged_dir
        os.makedirs(self.staged_dir, exist_ok=True)

    def get_config(self) -> RoostConfig:
        config = self.active_repo.get_config()
        
        if not os.path.exists(self.staged_dir):
            return config

        staged_files = [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]
        if staged_files:
            staged_repo = YAMLConfigRepository(self.staged_dir)
            staged_config = staged_repo.get_config()
            
            if "system.yaml" in staged_files:
                config.system = staged_config.system
            if "network.yaml" in staged_files:
                config.network = staged_config.network
            if "devices.yaml" in staged_files:
                config.devices = staged_config.devices
            if "schedules.yaml" in staged_files:
                config.schedules = staged_config.schedules
            if "plugins.yaml" in staged_files:
                config.plugins = staged_config.plugins
                
        return config

    def save_system_config(self, data: SystemConfig) -> None:
        save_config_file(self.staged_dir, "system.yaml", data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        save_config_file(self.staged_dir, "devices.yaml", data)

    def save_network_config(self, data: NetworkConfig) -> None:
        save_config_file(self.staged_dir, "network.yaml", data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        save_config_file(self.staged_dir, "schedules.yaml", data)

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

