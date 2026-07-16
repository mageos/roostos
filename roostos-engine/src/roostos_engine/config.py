import os
import yaml
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator

# ==========================================
# 1. system.yaml Schemas
# ==========================================

class SystemHTTPSConfig(BaseModel):
    enabled: bool = False
    domain: Optional[str] = None
    email: Optional[str] = None
    acme_provider: Optional[str] = "letsencrypt"
    challenge_type: Optional[str] = "dns-01"
    dns_provider: Optional[str] = None
    dns_credentials_file: Optional[str] = None

class SystemUpdatesRebootWindow(BaseModel):
    days: List[str] = ["Sun"]
    time: str = "03:00"

class SystemUpdatesConfig(BaseModel):
    auto_install: bool = True
    auto_reboot: bool = True
    reboot_window: SystemUpdatesRebootWindow = Field(default_factory=SystemUpdatesRebootWindow)

class SystemDNSConfig(BaseModel):
    forwarders: List[str] = Field(default_factory=list)
    ad_blocking_enabled: bool = False

class SystemSettings(BaseModel):
    hostname: str = "roost-router"
    domain: str = "lan"
    timezone: str = "UTC"
    docker_registry: Optional[str] = None
    https: Optional[SystemHTTPSConfig] = Field(default_factory=SystemHTTPSConfig)
    updates: Optional[SystemUpdatesConfig] = Field(default_factory=SystemUpdatesConfig)
    dns: Optional[SystemDNSConfig] = Field(default_factory=SystemDNSConfig)

class UserConfig(BaseModel):
    username: str
    role: str
    person: Optional[str] = None
    ssh_keys: List[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "parent", "member"):
            raise ValueError("role must be 'admin', 'parent', or 'member'")
        return v

class SystemConfig(BaseModel):
    system: SystemSettings = Field(default_factory=SystemSettings)
    users: List[UserConfig] = Field(default_factory=list)

# ==========================================
# 2. network.yaml Schemas
# ==========================================

class PPPoEConfig(BaseModel):
    username: str
    password: str

class NetworkInterface(BaseModel):
    name: str
    network: str = Field(alias="role")  # maps role/network
    protocol: Optional[str] = None      # "dhcp", "static", "pppoe", "pptp", "l2tp"
    vlan_tag: Optional[int] = None
    pppoe: Optional[PPPoEConfig] = None
    dhcp: Optional[bool] = None
    bridge: Optional[str] = None
    ip: Optional[str] = None
    gateway: Optional[str] = None
    ipv6: Optional[bool] = None

    model_config = {
        "populate_by_name": True
    }

    @field_validator("network", mode="before")
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v not in ("wan", "lan"):
            raise ValueError("network must be 'wan' or 'lan'")
        return v

    @property
    def role(self) -> str:
        return self.network

    @role.setter
    def role(self, value: str) -> None:
        self.network = value

class NetworkBridge(BaseModel):
    name: str
    ip: str
    isolate: bool = False
    dhcp_enabled: bool = True
    dhcp_pool_start: Optional[str] = None
    dhcp_pool_end: Optional[str] = None

class NetworkVlan(BaseModel):
    name: str
    id: int
    interface: str
    ip: str
    isolate: bool = True
    dhcp_enabled: bool = True
    dhcp_pool_start: Optional[str] = None
    dhcp_pool_end: Optional[str] = None

class NetworkGateway(BaseModel):
    id: str
    name: str
    interface: str
    type: str = "dhcp"
    metric: int = 10

class QoSConfig(BaseModel):
    enabled: bool = False
    wan_upload_kbps: Optional[int] = None
    wan_download_kbps: Optional[int] = None
    prioritize_tags: List[str] = Field(default_factory=list)

class NetworkSettings(BaseModel):
    interfaces: List[NetworkInterface] = Field(default_factory=list)
    bridges: List[NetworkBridge] = Field(default_factory=list)
    vlans: List[NetworkVlan] = Field(default_factory=list)
    gateways: List[NetworkGateway] = Field(default_factory=list)
    qos: Optional[QoSConfig] = Field(default_factory=QoSConfig)

class WifiRadio(BaseModel):
    interface: str
    band: str # "2.4ghz", "5ghz", "both"
    channel: Union[str, int] = "auto"
    width: int = 20 # 20, 40, 80, 160
    tx_power: str = "high" # "low", "medium", "high"

class WifiAccessPoint(BaseModel):
    name: Optional[str] = None # Friendly name
    ssid: str
    interface: Optional[str] = None # Deprecated/Optional
    passphrase: str
    security: str = "wpa3-sae" # "wpa2-psk", "wpa3-sae", "mixed"
    radio: Optional[str] = None # The physical radio interface it binds to (e.g. wlan0)
    bridge: Optional[str] = None
    vlan: Optional[int] = None

class WifiMesh(BaseModel):
    enabled: bool = False
    interface: str
    ssid: str
    passphrase: str
    frequency: int = 5180

class WifiSettings(BaseModel):
    radios: List[WifiRadio] = Field(default_factory=list)
    access_points: List[WifiAccessPoint] = Field(default_factory=list)
    mesh: Optional[WifiMesh] = None

class VPNConfig(BaseModel):
    id: str
    name: str
    type: str = "wireguard"  # "wireguard" or "openvpn"
    role: str = "client"  # "client" or "server"
    enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)

class NetworkConfig(BaseModel):
    network: Optional[NetworkSettings] = Field(default_factory=NetworkSettings)
    wifi: Optional[WifiSettings] = Field(default_factory=WifiSettings)
    vpns: List[VPNConfig] = Field(default_factory=list)

# ==========================================
# 3. devices.yaml Schemas
# ==========================================

class PersonConfig(BaseModel):
    id: str
    name: str
    dns_profile: Optional[str] = None

class BuildingConfig(BaseModel):
    id: str
    name: str

class RoomConfig(BaseModel):
    id: str
    name: str
    building: str

class UPnPAllowedPort(BaseModel):
    port: int
    protocol: str

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if v.lower() not in ("tcp", "udp"):
            raise ValueError("protocol must be 'tcp' or 'udp'")
        return v.lower()

class DeviceConfig(BaseModel):
    mac: str
    name: str
    owner: Optional[str] = None
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    static_ip: Optional[str] = None
    upnp_trusted: bool = False
    upnp_allowed_ports: List[UPnPAllowedPort] = Field(default_factory=list)
    gateway: Optional[str] = None
    max_download_kbps: Optional[int] = None
    max_upload_kbps: Optional[int] = None

    @field_validator("mac")
    @classmethod
    def normalize_mac(cls, v: str) -> str:
        mac = v.replace("-", ":").replace(".", ":").lower()
        parts = mac.split(":")
        if len(parts) != 6 or not all(len(p) <= 2 for p in parts):
            raise ValueError("invalid MAC address format")
        return ":".join(p.zfill(2) for p in parts)

class DevicesConfig(BaseModel):
    people: List[PersonConfig] = Field(default_factory=list)
    buildings: List[BuildingConfig] = Field(default_factory=list)
    rooms: List[RoomConfig] = Field(default_factory=list)
    devices: List[DeviceConfig] = Field(default_factory=list)

# ==========================================
# 4. schedules.yaml Schemas
# ==========================================

class PortForwardConfig(BaseModel):
    name: str
    protocol: str
    external_port: int
    internal_ip: str
    internal_port: int

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if v.lower() not in ("tcp", "udp"):
            raise ValueError("protocol must be 'tcp' or 'udp'")
        return v.lower()

class ScheduleTarget(BaseModel):
    tag: Optional[str] = None
    person: Optional[str] = None
    location: Optional[str] = None
    mac: Optional[str] = None

class ScheduleConfig(BaseModel):
    name: str
    targets: List[ScheduleTarget]
    days: List[str] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    daily_limit: Optional[int] = None
    action: str = "block_internet"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("block_internet", "block_all"):
            raise ValueError("action must be 'block_internet' or 'block_all'")
        return v

class InputRuleConfig(BaseModel):
    name: str
    interface: str = "*"          # "*" = all interfaces, or "eth0", "br0", etc.
    protocol: str = "tcp"         # "tcp", "udp", "tcp/udp"
    port: int
    source: Optional[str] = None  # Optional source IP/CIDR filter, e.g. "10.0.0.0/8"
    action: str = "accept"        # "accept" or "drop"
    enabled: bool = True

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if v.lower() not in ("tcp", "udp", "tcp/udp"):
            raise ValueError("protocol must be 'tcp', 'udp', or 'tcp/udp'")
        return v.lower()

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v.lower() not in ("accept", "drop"):
            raise ValueError("action must be 'accept' or 'drop'")
        return v.lower()

class FirewallSettings(BaseModel):
    port_forwards: List[PortForwardConfig] = Field(default_factory=list)
    rules: List[InputRuleConfig] = Field(default_factory=list)
    schedules: List[ScheduleConfig] = Field(default_factory=list)

class SchedulesConfig(BaseModel):
    firewall: Optional[FirewallSettings] = Field(default_factory=FirewallSettings)

# ==========================================
# 5. plugins.yaml Schemas
# ==========================================

class PortMapping(BaseModel):
    host_port: int
    container_port: int
    protocol: str = "tcp"

class VolumeMount(BaseModel):
    host_path: str
    container_path: str
    mode: str = "rw"

class ContainerConfig(BaseModel):
    name: str
    image: str
    ports: List[PortMapping] = Field(default_factory=list)
    volumes: List[VolumeMount] = Field(default_factory=list)
    environment: Dict[str, str] = Field(default_factory=dict)

class PluginConfig(BaseModel):
    id: str
    name: str
    enabled: bool = False
    network_mode: str = "bridge"  # "bridge" or "host"
    containers: List[ContainerConfig] = Field(default_factory=list)
    ui_entrypoint: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    known_services: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def handle_known_service_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            services = []
            for key in ["known_services", "knownServices", "known_service", "knownService"]:
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        services.extend(val)
                    elif isinstance(val, str):
                        services.append(val)
            if services:
                data["known_services"] = list(dict.fromkeys(services))
        return data

class PluginsConfig(BaseModel):
    plugins: List[PluginConfig] = Field(default_factory=list)

# ==========================================
# Unified Router Configurations & Multi-File Loader
# ==========================================

class RoostConfig(BaseModel):
    system: SystemSettings
    users: List[UserConfig]
    network: NetworkSettings
    wifi: WifiSettings
    vpns: List[VPNConfig]
    people: List[PersonConfig]
    buildings: List[BuildingConfig]
    rooms: List[RoomConfig]
    devices: List[DeviceConfig]
    firewall: FirewallSettings
    plugins: List[PluginConfig]

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

        for s in self.firewall.schedules:
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
        return []


def load_config_directory(config_dir: str) -> RoostConfig:
    files = {
        "system.yaml": (SystemConfig, "system"),
        "network.yaml": (NetworkConfig, "network"),
        "devices.yaml": (DevicesConfig, "devices"),
        "schedules.yaml": (SchedulesConfig, "schedules"),
        "plugins.yaml": (PluginsConfig, "plugins")
    }

    raw_data: Dict[str, Any] = {}

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
                        print("Migrated legacy br-lan bridge configuration to br0 successfully.")
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
            raw_data["firewall"] = parsed.firewall
        elif namespace == "plugins":
            raw_data["plugins"] = parsed.plugins

    return RoostConfig.model_validate(raw_data)


def save_config_file(config_dir: str, file_basename: str, model_data: BaseModel) -> None:
    filepath = os.path.join(config_dir, file_basename)
    dump_dict = model_data.model_dump(exclude_none=True)
    with open(filepath, "w") as f:
        yaml.safe_dump(dump_dict, f, default_flow_style=False, sort_keys=False)
