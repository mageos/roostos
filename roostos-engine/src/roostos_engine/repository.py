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
