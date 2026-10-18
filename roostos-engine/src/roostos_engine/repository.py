from abc import ABC, abstractmethod
import os
from typing import Union, Any, List, Optional
import yaml
from roostos_engine.config import (
    RoostConfig, SystemConfig, NodesConfigFile, DevicesConfig, NetworkSettings,
    NetworkConfig, SchedulesConfig, FirewallConfig, PluginsConfig,
    load_config_directory, save_config_file,
)


class ConfigRepository(ABC):
    def __init__(self) -> None:
        self._listeners: list = []

    def add_listener(self, listener: Any) -> None:
        if not hasattr(self, "_listeners"):
            self._listeners = []
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Any) -> None:
        if hasattr(self, "_listeners") and listener in self._listeners:
            self._listeners.remove(listener)

    def notify_change(self, section: str, action: str = "save", data: Any = None) -> None:
        from roostos_engine.events import ConfigChangeEvent
        event = ConfigChangeEvent(section=section, action=action, data=data)
        for listener in list(getattr(self, "_listeners", [])):
            try:
                listener(event)
            except Exception:
                pass

    @abstractmethod
    def get_config(self) -> RoostConfig:
        pass

    @abstractmethod
    def save_system_config(self, data: SystemConfig) -> None: pass
    @abstractmethod
    def save_nodes_config(self, data: NodesConfigFile) -> None: pass
    @abstractmethod
    def save_devices_config(self, data: DevicesConfig) -> None: pass
    @abstractmethod
    def save_network_config(self, data: Union[NetworkConfig, NetworkSettings]) -> None: pass
    @abstractmethod
    def save_schedules_config(self, data: SchedulesConfig) -> None: pass
    @abstractmethod
    def save_firewall_config(self, data: FirewallConfig) -> None: pass
    @abstractmethod
    def save_plugins_config(self, data: PluginsConfig) -> None: pass


class YAMLConfigRepository(ConfigRepository):
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        try:
            os.makedirs(self.config_dir, exist_ok=True)
        except (PermissionError, OSError):
            pass

    def get_config(self) -> RoostConfig:
        return load_config_directory(self.config_dir)

    def save_system_config(self, data: SystemConfig) -> None:
        save_config_file(self.config_dir, "system.yaml", data)
        self.notify_change("system", data=data)

    def save_nodes_config(self, data: NodesConfigFile) -> None:
        save_config_file(self.config_dir, "nodes.yaml", data)
        self.notify_change("nodes", data=data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        save_config_file(self.config_dir, "devices.yaml", data)
        self.notify_change("devices", data=data)

    def save_network_config(self, data: Union[NetworkConfig, NetworkSettings]) -> None:
        if isinstance(data, NetworkSettings):
            existing = None
            filepath = os.path.join(self.config_dir, "network.yaml")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        raw = yaml.safe_load(f) or {}
                    existing = NetworkConfig.model_validate(raw)
                except Exception:
                    pass
            net_cfg = existing if existing else NetworkConfig(network=data, edge_gateways=data.edge_gateways)
            if existing:
                existing.network = data
                existing.edge_gateways = data.edge_gateways
            save_config_file(self.config_dir, "network.yaml", net_cfg)
        else:
            save_config_file(self.config_dir, "network.yaml", data)
        self.notify_change("network", data=data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        save_config_file(self.config_dir, "schedules.yaml", data)
        self.notify_change("schedules", data=data)

    def save_firewall_config(self, data: FirewallConfig) -> None:
        save_config_file(self.config_dir, "firewall.yaml", data)
        self.notify_change("firewall", data=data)

    def save_plugins_config(self, data: PluginsConfig) -> None:
        save_config_file(self.config_dir, "plugins.yaml", data)
        self.notify_change("plugins", data=data)


class StagingConfigRepository(ConfigRepository):
    def __init__(self, active_dir: str, staged_dir: str):
        self.active_repo = YAMLConfigRepository(active_dir)
        self.staged_dir = staged_dir
        try:
            os.makedirs(self.staged_dir, exist_ok=True)
        except (PermissionError, OSError):
            pass

    @property
    def config_dir(self) -> str:
        return self.active_repo.config_dir

    def get_config(self) -> RoostConfig:
        config = self.active_repo.get_config()
        if not os.path.exists(self.staged_dir):
            return config
        staged_files = [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]
        if "system.yaml" in staged_files:
            parsed = SystemConfig.model_validate(self._load_staged_yaml("system.yaml"))
            config.system, config.users = parsed.system, parsed.users
        if "nodes.yaml" in staged_files:
            config.nodes = NodesConfigFile.model_validate(self._load_staged_yaml("nodes.yaml")).nodes
        if "network.yaml" in staged_files:
            active_edge_gws = list(config.edge_gateways or getattr(config.network, "edge_gateways", []) or [])
            p_net = NetworkConfig.model_validate(self._load_staged_yaml("network.yaml"))
            merged_edge_gws = p_net.edge_gateways if p_net.edge_gateways else active_edge_gws
            p_net.network.edge_gateways = merged_edge_gws
            config.network, config.wifi, config.vpns, config.edge_gateways = p_net.network, p_net.wifi, p_net.vpns, merged_edge_gws
        if "devices.yaml" in staged_files:
            p_dev = DevicesConfig.model_validate(self._load_staged_yaml("devices.yaml"))
            config.people, config.buildings, config.rooms, config.devices = p_dev.people, p_dev.buildings, p_dev.rooms, p_dev.devices
        if "schedules.yaml" in staged_files:
            config.schedules = SchedulesConfig.model_validate(self._load_staged_yaml("schedules.yaml")).schedules
        if "firewall.yaml" in staged_files:
            p_fw = FirewallConfig.model_validate(self._load_staged_yaml("firewall.yaml"))
            if p_fw.firewall:
                config.firewall.port_forwards = p_fw.firewall.port_forwards
                config.firewall.rules = p_fw.firewall.rules
                config.firewall.block_doh = p_fw.firewall.block_doh
                config.firewall.block_vpns = p_fw.firewall.block_vpns
                config.firewall.block_quic = p_fw.firewall.block_quic
                config.firewall.custom_doh_ips = p_fw.firewall.custom_doh_ips
                config.firewall.custom_vpn_ips = p_fw.firewall.custom_vpn_ips
        if "plugins.yaml" in staged_files:
            config.plugins = PluginsConfig.model_validate(self._load_staged_yaml("plugins.yaml")).plugins
        return config

    def _load_staged_yaml(self, filename: str) -> dict:
        try:
            with open(os.path.join(self.staged_dir, filename), "r") as f:
                raw_text = f.read().replace("\t", "  ")
            return yaml.safe_load(raw_text) or {}
        except Exception:
            return {}

    def save_system_config(self, data: SystemConfig) -> None:
        save_config_file(self.staged_dir, "system.yaml", data)
        self.notify_change("system", data=data)

    def save_nodes_config(self, data: NodesConfigFile) -> None:
        save_config_file(self.staged_dir, "nodes.yaml", data)
        self.notify_change("nodes", data=data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        save_config_file(self.staged_dir, "devices.yaml", data)
        self.notify_change("devices", data=data)

    def save_network_config(self, data: Union[NetworkConfig, NetworkSettings]) -> None:
        if isinstance(data, NetworkSettings):
            existing = None
            filepath = os.path.join(self.staged_dir, "network.yaml")
            if not os.path.exists(filepath):
                filepath = os.path.join(self.active_repo.config_dir, "network.yaml")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        existing = NetworkConfig.model_validate(yaml.safe_load(f) or {})
                except Exception:
                    pass
            net_cfg = existing if existing else NetworkConfig(network=data, edge_gateways=data.edge_gateways)
            if existing:
                existing.network, existing.edge_gateways = data, data.edge_gateways
            save_config_file(self.staged_dir, "network.yaml", net_cfg)
        else:
            save_config_file(self.staged_dir, "network.yaml", data)
        self.notify_change("network", data=data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        save_config_file(self.staged_dir, "schedules.yaml", data)
        self.notify_change("schedules", data=data)

    def save_firewall_config(self, data: FirewallConfig) -> None:
        save_config_file(self.staged_dir, "firewall.yaml", data)
        self.notify_change("firewall", data=data)

    def save_plugins_config(self, data: PluginsConfig) -> None:
        save_config_file(self.staged_dir, "plugins.yaml", data)
        self.notify_change("plugins", data=data)

    def commit_staged_changes(self) -> None:
        """Copies all staged configurations to active directory and deletes them from stage."""
        if not os.path.exists(self.staged_dir):
            return
        import shutil
        for filename in [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]:
            src = os.path.join(self.staged_dir, filename)
            dst = os.path.join(self.active_repo.config_dir, filename)
            shutil.copy2(src, dst)
            os.remove(src)
        self.notify_change("commit", action="commit")
        self.active_repo.notify_change("commit", action="commit")

    def discard_staged_changes(self) -> None:
        """Deletes all staged files."""
        if not os.path.exists(self.staged_dir):
            return
        for filename in [f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]:
            os.remove(os.path.join(self.staged_dir, filename))

    def has_staged_changes(self) -> bool:
        if not os.path.exists(self.staged_dir):
            return False
        return len([f for f in os.listdir(self.staged_dir) if f.endswith(".yaml")]) > 0

    def add_listener(self, listener: Any) -> None:
        super().add_listener(listener)
        self.active_repo.add_listener(listener)


class InMemoryConfigRepository(ConfigRepository):
    """In-memory implementation of ConfigRepository for isolated unit tests."""

    def __init__(self, initial_config: Optional[RoostConfig] = None):
        super().__init__()
        if initial_config is not None:
            self._config = initial_config
        else:
            from roostos_engine.models import SystemSettings, NetworkSettings, FirewallSettings
            self._config = RoostConfig(
                system=SystemSettings(hostname="roost-router", domain="lan"),
                users=[], nodes=[],
                network=NetworkSettings(interfaces=[], bridges=[], vlans=[], gateways=[], zones=[]),
                vpns=[], people=[], buildings=[], rooms=[], devices=[],
                firewall=FirewallSettings(port_forwards=[], rules=[]),
                schedules=[], plugins=[],
            )

    def get_config(self) -> RoostConfig:
        return self._config.model_copy(deep=True)

    def save_system_config(self, data: SystemConfig) -> None:
        self._config.system = data.system
        self._config.users = data.users
        self.notify_change("system", data=data)

    def save_nodes_config(self, data: NodesConfigFile) -> None:
        self._config.nodes = data.nodes
        self.notify_change("nodes", data=data)

    def save_devices_config(self, data: DevicesConfig) -> None:
        self._config.people = data.people
        self._config.buildings = data.buildings
        self._config.rooms = data.rooms
        self._config.devices = data.devices
        self.notify_change("devices", data=data)

    def save_network_config(self, data: NetworkConfig) -> None:
        self._config.network = data.network
        self._config.wifi = data.wifi
        self._config.vpns = data.vpns
        self.notify_change("network", data=data)

    def save_schedules_config(self, data: SchedulesConfig) -> None:
        self._config.schedules = data.schedules
        self.notify_change("schedules", data=data)

    def save_firewall_config(self, data: FirewallConfig) -> None:
        fw = data.firewall if hasattr(data, "firewall") and data.firewall else data
        for k in ("port_forwards", "rules", "custom_doh_ips", "custom_vpn_ips"):
            setattr(self._config.firewall, k, getattr(fw, k, []))
        for k in ("block_doh", "block_vpns", "block_quic"):
            setattr(self._config.firewall, k, getattr(fw, k, False))
        self.notify_change("firewall", data=data)

    def save_plugins_config(self, data: PluginsConfig) -> None:
        self._config.plugins = data.plugins
        self.notify_change("plugins", data=data)
