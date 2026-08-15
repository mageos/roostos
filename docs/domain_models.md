# RoostOS Domain Models Specification

This document provides a comprehensive technical reference for all RoostOS domain objects and Data Transfer Objects (DTOs). These Pydantic models define the structure, validation constraints, and cross-reference relationships across the 6 configuration domains, transient runtime states, Family Controls (`roostos-timeguardd`), and cluster compute nodes.

---

## 1. System & Security Domain (`system.yaml`)

### `SystemSettings`
Host identity, DNS settings, Active Directory realm equivalent, global unregistered device policy, and default OCI registry.
- `hostname` (str, default `"roost-router"`): Machine hostname.
- `domain` (str, default `"lan"`): Local network domain name.
- `realm` (str, default `"ROOSTOS.LOCAL"`): Directory Services / Kerberos / Active Directory domain realm equivalent.
- `timezone` (str, default `"UTC"`): System timezone string (e.g. `"America/Chicago"`).
- `unregistered_device_policy` (str, default `"deny"`): Default security policy for unknown MAC addresses (`"allow"` or `"deny"`).
- `docker_registry` (Optional[str], default `None`): Default OCI container registry URL (e.g. `"ghcr.io"`).
- `https` (`SystemHTTPSConfig`): SSL certificate and ACME settings.
- `updates` (`SystemUpdatesConfig`): Maintenance window and unattended updates.
- `dns` (`SystemDNSConfig`): Global forwarders and ad-blocking toggle.

### `UserConfig`
Web management login account definition.
- `username` (str): Unique login username.
- `role` (str): Authorization role (`"admin"`, `"parent"`, or `"member"`).
- `person` (Optional[str], default `None`): Foreign key referencing a `PersonConfig.id` in `devices.yaml`.
- `ssh_keys` (List[str], default `[]`): Public SSH keys authorized for terminal login (admin role only).

---

## 2. Network & Connectivity Domain (`network.yaml`)

### `NetworkInterface`
Physical interface binding definition.
- `name` (str): Hardware interface name (e.g. `"eth0"`).
- `network` (str): Network role (`"wan"` or `"lan"`).
- `protocol` (Optional[str], default `None`): IP assignment protocol (`"dhcp"`, `"static"`, `"pppoe"`).
- `vlan_tag` (Optional[int], default `None`): 802.1Q VLAN tag ID.
- `bridge` (Optional[str], default `None`): Parent bridge interface name (e.g. `"br0"`).
- `ip` (Optional[str], default `None`): Static CIDR address (e.g. `"192.168.1.1/24"`).
- `gateway` (Optional[str], default `None`): Upstream default gateway IP.

### `NetworkBridge`
Layer 2 network bridge (LAN subnet controller).
- `name` (str): Bridge interface name (e.g. `"br0"`).
- `ip` (str): Router interface CIDR address (e.g. `"192.168.1.1/24"`).
- `isolate` (bool, default `False`): If true, isolates traffic from other subnets.
- `dhcp_enabled` (bool, default `True`): Toggles Kea DHCP address distribution.
- `dhcp_pool_start` (Optional[str]): Start IP of DHCP dynamic allocation range.
- `dhcp_pool_end` (Optional[str]): End IP of DHCP dynamic allocation range.

### `NetworkVlan`
Isolated VLAN subinterface definition.
- `name` (str): Subinterface name (e.g. `"vlan-iot"`).
- `id` (int): 802.1Q VLAN Tag ID (1-4094).
- `interface` (str): Parent bridge or physical interface.
- `ip` (str): Router interface CIDR address.
- `isolate` (bool, default `True`): Forces WAN-only forwarding.
- `dhcp_enabled` (bool, default `True`): Toggles DHCP server on VLAN.

### `ZoneConfig`
Logical network zone grouping multiple physical interfaces, bridges, or VLANs together.
- `id` (str): Unique zone identifier (e.g. `"lan"`, `"wan"`, `"iot"`, `"guest"`, `"dmz"`).
- `name` (str): Display name (e.g. `"Smart Home IoT Zone"`).
- `interfaces` (List[str], default `[]`): List of constituent interface names, bridge names, or VLAN subinterface names (e.g. `["br0", "vlan-iot"]`).
- `isolate` (bool, default `False`): If true, blocks inter-zone forwarding by default.
- `allow_zones` (List[str], default `[]`): Destination zone IDs where devices in this zone are permitted to **initiate NEW connections** (`ct state new`). Netfilter stateful connection tracking (`ct state established,related accept`) automatically permits return traffic for LAN-initiated connections (e.g., a LAN device accessing an IoT bulb allows return packets, but the IoT bulb cannot initiate new connections to the LAN).
- `masquerade` (bool, default `False`): Toggles SNAT/masquerade for egressing traffic.

### `QoSConfig`
Linux Traffic Control (`tc`) bandwidth shaping configuration.
- `enabled` (bool, default `False`): Enables HTB / fq_codel queue shaping.
- `wan_upload_kbps` (Optional[int]): Egress WAN upload speed limit in Kilobits/sec.
- `wan_download_kbps` (Optional[int]): Ingress WAN download speed limit in Kilobits/sec.
- `prioritize_tags` (List[str], default `[]`): Devices carrying these tags get priority queueing (`Class 1:10`).

---

## 3. Family & Device Domain (`devices.yaml`)

### `PersonConfig`
Household family member profile.
- `id` (str): Unique person identifier (e.g. `"alice_profile"`).
- `name` (str): Display name (e.g. `"Alice"`).
- `dns_profile` (Optional[str]): Default DNS filtering profile binding (e.g. `"Kids-Safe"`).

### `BuildingConfig` & `RoomConfig`
Physical location spatial hierarchy.
- `BuildingConfig`: `id` (str), `name` (str).
- `RoomConfig`: `id` (str), `name` (str), `building` (str - foreign key to `BuildingConfig.id`).

### `DeviceConfig`
Registered client network device profile.
- `mac` (str): Hardware MAC address (normalized to lowercase `aa:bb:cc:dd:ee:ff`).
- `name` (str): Friendly device name (e.g. `"Alice's iPad"`).
- `owner` (Optional[str]): Foreign key referencing `PersonConfig.id`.
- `location` (Optional[str]): Foreign key referencing `RoomConfig.id` or `BuildingConfig.id`.
- `tags` (List[str], default `[]`): Custom organizational tags (e.g. `["kids", "gaming"]`).
- `static_ip` (Optional[str]): Static DHCP reservation IP address.
- `upnp_trusted` (bool, default `False`): If true, auto-approves all UPnP port requests.
- `upnp_allowed_ports` (List[`UPnPAllowedPort`], default `[]`): Pre-approved static UPnP rules.
- `gateway` (Optional[str]): Policy-based routing gateway override.
- `max_download_kbps` (Optional[int]): Per-device download speed cap.
- `max_upload_kbps` (Optional[int]): Per-device upload speed cap.

---

## 4. Firewall & Scheduling Domain (`schedules.yaml` & `firewall.yaml`)

### `ScheduleTarget`
Selector targeting devices for firewall actions.
- `tag` (Optional[str]): Target devices carrying a specific tag.
- `person` (Optional[str]): Target all devices owned by a specific `Person`.
- `location` (Optional[str]): Target all devices located in a `Room` or `Building`.
- `mac` (Optional[str]): Target a specific hardware MAC address.

### `ScheduleConfig` (`schedules.yaml`)
Time-window access rules and daily screen time limits.
- `name` (str): Rule description (e.g. `"Kids Bedtime"`).
- `targets` (List[`ScheduleTarget`]): Target selectors.
- `days` (List[str], default `[]`): Active days (e.g. `["Mon", "Tue"]`).
- `start_time` (Optional[str]): Start time `HH:MM` format.
- `end_time` (Optional[str]): End time `HH:MM` format.
- `daily_limit` (Optional[int]): Daily accumulated screen time allowance in minutes.
- `action` (str, default `"block_internet"`): Enforcement action (`"block_internet"` or `"block_all"`).

### `InputRuleConfig` (`firewall.yaml`)
Host firewall inbound access rules.
- `name` (str): Rule name.
- `interface` (str, default `"*"`): Target interface (`"*"` = all, `"br0"`, `"eth0"`).
- `protocol` (str, default `"tcp"`): IP protocol (`"tcp"`, `"udp"`, `"tcp/udp"`).
- `port` (int): Destination port number.
- `source` (Optional[str]): Source IP or CIDR subnet filter (e.g. `"192.168.1.0/24"`).
- `action` (str, default `"accept"`): Action (`"accept"` or `"drop"`).
- `enabled` (bool, default `True`): Toggles rule execution.

### `PortForwardConfig` (`firewall.yaml`)
Destination NAT WAN port forwarding.
- `name` (str): Forwarding description (e.g. `"Plex Server"`).
- `protocol` (str): Transport protocol (`"tcp"` or `"udp"`).
- `external_port` (int): Public WAN incoming port.
- `internal_ip` (str): Target LAN client IP address.
- `internal_port` (int): Target internal service port.

---

## 5. Extensibility & Cluster Domain (`plugins.yaml` & Cluster)

### `PluginConfig` (`plugins.yaml`)
Extension plugin registration profile.
- `id` (str): Unique plugin identifier.
- `name` (str): Display name.
- `type` (str, default `"application"`): Plugin category (`"core_service"` or `"application"`).
- `enabled` (bool, default `False`): Plugin execution toggle.
- `network_mode` (str, default `"bridge"`): Docker network mode (`"bridge"`, `"host"`, `"service:<name>"`).
- `requested_scopes` (List[str], default `[]`): Permission scopes requested by plugin.
- `containers` (List[`ContainerConfig`]): List of container service specs.
- `ui_entrypoint` (Optional[str]): Path to static UI ES Module inside container.
- `settings` (Dict[str, Any], default `{}`): User configuration overrides.
- `known_services` (List[str], default `[]`): Service capabilities provided (e.g. `["dns"]`).

### `ClusterNode`
Compute cluster node registry definition.
- `node_id` (str): Unique cluster node ID.
- `hostname` (str): Machine hostname.
- `role` (str): Node role (`"primary_router"`, `"secondary_router"`, or `"compute_worker"`).
- `ip_address` (str): Node management IP address.
- `status` (str): Operational status (`"online"`, `"offline"`, `"degraded"`).
- `last_seen` (str): UTC ISO timestamp of last heartbeat.

---

## 6. Transient State & Family Controls Domain (Runtime)

### `ActiveLease`
Cached DHCP address lease record in `state.db`.
- `mac` (str): Client MAC address.
- `ip` (str): Assigned IPv4 address.
- `hostname` (Optional[str]): Client hostname.
- `quarantined` (bool): True if device is unknown and policy is `deny`.
- `last_seen` (str): UTC ISO timestamp.

### `TimeGuardHeartbeat`
OS-level session heartbeat from client workstation (`roostos-timeguardd`).
- `username` (str): Logged-in human user account.
- `hostname` (str): Client machine hostname.
- `active_seconds` (int): Incremental session seconds since last tick.
- `remaining_seconds` (int): Remaining daily allowance seconds cached locally.

### `TimeGuardUserLimits`
Aggregated cross-device screen time state.
- `username` (str): Target user account.
- `remaining_seconds` (int): Net remaining screen time seconds across all devices.
- `daily_limit_seconds` (int): Total configured daily screen time allowance.
- `locked` (bool): True if time limit is exhausted and sessions are locked.
