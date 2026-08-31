import os
import yaml
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator

from roostos_engine.models.system import (
    SystemHTTPSConfig,
    SystemUpdatesRebootWindow,
    SystemUpdatesConfig,
    SystemDNSConfig,
    ClusterSettingsConfig,
    SystemIdentityServerConfig,
    SystemSettings,
    UserConfig,
    SystemConfig,
)
from roostos_engine.models.identity import (
    DomainUser,
    DomainUserCreate,
    DomainUserUpdate,
    DomainPasswordReset,
    DomainGroup,
    DomainStatus,
    WorkstationEnrollmentInfo,
)
from roostos_engine.models.network import (
    PPPoEConfig,
    NetworkInterface,
    NetworkBridge,
    NetworkVlan,
    NetworkGateway,
    QoSConfig,
    ZoneConfig,
    NetworkSettings,
    WifiRadio,
    WifiAccessPoint,
    WifiMesh,
    WifiSettings,
    VPNConfig,
    NetworkConfig,
)
from roostos_engine.models.node import (
    NodeRole,
    InterfaceType,
    InterfaceMode,
    NodeInterface,
    DetectedHardwareInterface,
    NodeCapabilities,
    NodeConfig,
    NodesConfigFile,
)
from roostos_engine.models.networks import (
    Network,
    NetworksConfigFile,
    WifiSSIDConfig,
    DHCPSettings,
)
from roostos_engine.models.devices import (
    PersonConfig,
    BuildingConfig,
    RoomConfig,
    UPnPAllowedPort,
    DeviceConfig,
    DevicesConfig,
)
from roostos_engine.models.schedules import (
    ScheduleTarget,
    ScheduleConfig,
    ScheduleSettings,
    SchedulesConfig,
)
from roostos_engine.models.firewall import (
    PortForwardConfig,
    InputRuleConfig,
    FirewallSettings,
    FirewallConfig,
)
from roostos_engine.models.plugins import (
    PortMapping,
    VolumeMount,
    ContainerConfig,
    PluginConfig,
    PluginsConfig,
)
from roostos_engine.models.providers import (
    ProvidersSettings,
    ProvidersConfigFile,
)
from roostos_engine.models.state import (
    ActiveLease,
    PendingUPnPRequest,
    BypassGrant,
    TimeGuardHeartbeat,
    TimeGuardUserLimits,
    ClusterNode,
)


class RoostConfig(BaseModel):
    system: SystemSettings
    users: List[UserConfig]
    network: NetworkSettings
    nodes: List[NodeConfig] = Field(default_factory=list)
    wifi: Optional[WifiSettings] = None
    vpns: List[VPNConfig]
    people: List[PersonConfig]
    buildings: List[BuildingConfig]
    rooms: List[RoomConfig]
    devices: List[DeviceConfig]
    firewall: FirewallSettings
    schedules: List[ScheduleConfig]
    plugins: List[PluginConfig]
    providers: Optional[ProvidersSettings] = Field(default_factory=ProvidersSettings)

    @model_validator(mode="after")
    def validate_cross_references(self) -> "RoostConfig":
        people_ids = {p.id for p in self.people}
        building_ids = {b.id for b in self.buildings}
        room_ids = {r.id for r in self.rooms}
        location_ids = building_ids.union(room_ids)

        for u in self.users:
            if u.person and u.person not in people_ids:
                raise ValueError(f"User '{u.username}' references non-existent person ID '{u.person}'")

        for r in self.rooms:
            if r.building not in building_ids:
                raise ValueError(f"Room '{r.id}' references non-existent building ID '{r.building}'")

        gateway_ids = {g.id for g in self.network.gateways}
        for d in self.devices:
            if d.owner and d.owner not in people_ids:
                raise ValueError(f"Device '{d.mac}' references non-existent owner ID '{d.owner}'")
            if d.location and d.location not in location_ids:
                raise ValueError(f"Device '{d.mac}' references non-existent location ID '{d.location}'")
            if d.gateway and d.gateway not in gateway_ids:
                raise ValueError(f"Device '{d.mac}' references non-existent gateway ID '{d.gateway}'")

        for s in self.schedules:
            for target in s.targets:
                if target.person and target.person not in people_ids:
                    raise ValueError(f"Schedule '{s.name}' target references non-existent person ID '{target.person}'")
                if target.location and target.location not in location_ids:
                    raise ValueError(f"Schedule '{s.name}' target references non-existent location ID '{target.location}'")
                if target.mac:
                    try:
                        norm_mac = DeviceConfig.normalize_mac(target.mac)
                        if not any(d.mac == norm_mac for d in self.devices):
                            raise ValueError()
                    except Exception:
                        raise ValueError(f"Schedule '{s.name}' target MAC '{target.mac}' is not registered under devices.")

        return self

    def get_building_rooms(self, building_id: str) -> List[str]:
        return [r.id for r in self.rooms if r.building == building_id]

    def resolve_location_macs(self, location_id: str) -> List[str]:
        building_ids = {b.id for b in self.buildings}
        room_ids = {r.id for r in self.rooms}

        target_locations = {location_id}
        if location_id in building_ids:
            target_locations.update(self.get_building_rooms(location_id))

        return [d.mac for d in self.devices if d.location in target_locations]

    def resolve_person_macs(self, person_id: str) -> List[str]:
        return [d.mac for d in self.devices if d.owner == person_id]

    def resolve_tag_macs(self, tag: str) -> List[str]:
        return [d.mac for d in self.devices if tag in d.tags]

    def resolve_selector_macs(self, selector: ScheduleTarget) -> List[str]:
        if selector.mac:
            return [DeviceConfig.normalize_mac(selector.mac)]
        if selector.person:
            return self.resolve_person_macs(selector.person)
        if selector.location:
            return self.resolve_location_macs(selector.location)
        if selector.tag:
            return self.resolve_tag_macs(selector.tag)
        if selector.zone:
            # Resolve devices connected via interfaces belonging to the target zone
            zone_obj = next((z for z in self.network.zones if z.id == selector.zone), None)
            if zone_obj and zone_obj.interfaces:
                zone_ifaces = set(zone_obj.interfaces)
                return [d.mac for d in self.devices if d.location in zone_ifaces]
        return []


def load_config_directory(config_dir: str) -> RoostConfig:
    files = {
        "system.yaml": (SystemConfig, "system"),
        "network.yaml": (NetworkConfig, "network"),
        "nodes.yaml": (NodesConfigFile, "nodes"),
        "devices.yaml": (DevicesConfig, "devices"),
        "schedules.yaml": (SchedulesConfig, "schedules"),
        "firewall.yaml": (FirewallConfig, "firewall"),
        "plugins.yaml": (PluginsConfig, "plugins"),
        "providers.yaml": (ProvidersConfigFile, "providers"),
    }

    raw_data: Dict[str, Any] = {}
    firewall_settings = FirewallSettings()
    schedules_list: List[ScheduleConfig] = []

    for filename, (schema_cls, namespace) in files.items():
        filepath = os.path.join(config_dir, filename)
        if not os.path.exists(filepath):
            yaml_content = {}
        else:
            with open(filepath, "r") as f:
                yaml_content = yaml.safe_load(f) or {}

        parsed = schema_cls.model_validate(yaml_content)

        if namespace == "system":
            raw_data["system"] = parsed.system
            raw_data["users"] = parsed.users
        elif namespace == "nodes":
            raw_data["nodes"] = parsed.nodes
        elif namespace == "network":
            if parsed.network:
                has_migration = False
                for bridge in parsed.network.bridges:
                    if bridge.name == "br-lan":
                        bridge.name = "br0"
                        has_migration = True
                for interface in parsed.network.interfaces:
                    if interface.bridge == "br-lan":
                        interface.bridge = "br0"
                        has_migration = True
                if has_migration:
                    try:
                        save_config_file(config_dir, "network.yaml", parsed)
                    except Exception as e:
                        print(f"Warning: Failed to write migrated network config: {e}")
            raw_data["network"] = parsed.network
            raw_data["wifi"] = parsed.wifi
            raw_data["vpns"] = parsed.vpns
        elif namespace == "devices":
            raw_data["people"] = parsed.people
            raw_data["buildings"] = parsed.buildings
            raw_data["rooms"] = parsed.rooms
            raw_data["devices"] = parsed.devices
        elif namespace == "schedules":
            if parsed.firewall:
                schedules_list = parsed.firewall.schedules
                # Migration fallback if port_forwards or rules were in schedules.yaml
                if hasattr(parsed.firewall, "port_forwards") and getattr(parsed.firewall, "port_forwards"):
                    firewall_settings.port_forwards = getattr(parsed.firewall, "port_forwards")
                if hasattr(parsed.firewall, "rules") and getattr(parsed.firewall, "rules"):
                    firewall_settings.rules = getattr(parsed.firewall, "rules")
        elif namespace == "firewall":
            if parsed.firewall:
                if parsed.firewall.port_forwards:
                    firewall_settings.port_forwards = parsed.firewall.port_forwards
                if parsed.firewall.rules:
                    firewall_settings.rules = parsed.firewall.rules
                firewall_settings.block_doh = parsed.firewall.block_doh
                firewall_settings.block_vpns = parsed.firewall.block_vpns
                firewall_settings.block_quic = parsed.firewall.block_quic
                firewall_settings.custom_doh_ips = parsed.firewall.custom_doh_ips
                firewall_settings.custom_vpn_ips = parsed.firewall.custom_vpn_ips

        elif namespace == "plugins":
            raw_data["plugins"] = parsed.plugins
        elif namespace == "providers":
            raw_data["providers"] = parsed.providers

    raw_data["firewall"] = firewall_settings
    raw_data["schedules"] = schedules_list

    return RoostConfig.model_validate(raw_data)


def save_config_file(config_dir: str, file_basename: str, model_data: BaseModel) -> None:
    filepath = os.path.join(config_dir, file_basename)
    dump_dict = model_data.model_dump(mode="json", exclude_none=True)
    with open(filepath, "w") as f:
        yaml.safe_dump(dump_dict, f, default_flow_style=False, sort_keys=False)
