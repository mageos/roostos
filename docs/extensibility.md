# RoostOS Extensibility & Plugin Architecture

To prevent system bloat and foster community-driven additions, RoostOS supports a clean, secure, and containerized extension system. This architecture ensures third-party plugins (e.g. ad blockers, dynamic network visualizers, parental portals) run in isolation while retaining real-time communication capabilities with the host OS via D-Bus.

---

## 1. Containerized Plugin & Sidecar Model

Plugins are hosted as **Docker containers** managed by the host's RoostOS Engine. 

### A. Sidecar (Multi-Container) Pattern
Many standard tools (like Technitium DNS or AdGuard Home) run their own web interfaces and databases. To avoid modifying these official containers, RoostOS plugins support a **sidecar architecture**:

```
                               ┌─── Docker Network Namespace ──────────┐
                               │                                       │
  ┌────────────────┐           │   ┌───────────────┐                   │
  │  Roost Daemon  │◄──D-Bus──►│   │ D-Bus Bridge  │                   │
  │    (roostd)    │           │   │   (Sidecar)   │                   │
  └────────────────┘           │   └───────┬───────┘                   │
                               │           │ Localhost REST API        │
                               │           ▼                           │
                               │   ┌───────────────┐                   │
                               │   │  DNS Engine   │                   │
                               │   │ (Technitium)  │                   │
                               │   └───────────────┘                   │
                               │                                       │
                               └───────────────────────────────────────┘
```

1.  **Main Service Container**: Runs the official off-the-shelf software (e.g. `technitium/dns-server:latest`).
2.  **Sidecar D-Bus Bridge Container**: Runs a custom helper script/daemon that implements the standard RoostOS D-Bus interfaces. It mounts the D-Bus socket from the host and shares the **network namespace** of the Main Service container (`network_mode: "service:dns-server"`).
3.  **Local Isolation**: This namespace sharing enables the sidecar to securely query the main service via `localhost` (e.g. `http://127.0.0.1:5380/api`) without exposing APIs to the LAN.

### B. Mounting and IPC Setup
Every plugin container designated to communicate with D-Bus is run with:
*   **Socket Mount**: `-v /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket`
*   **Environment Variable**: `DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket`

---

## 2. Plugin Manifest Specification

To facilitate installation and upgrades, plugins are packaged as tarball/ZIP archives containing a central **`manifest.json`** file. The manifest declares metadata, update configurations, Web UI assets, and container service profiles.

### Manifest Schema Example (`manifest.json`):
```json
{
  "id": "local-dns-resolver",
  "name": "Technitium DNS Resolver",
  "version": "1.0.2",
  "description": "Standard DNS resolution and blocklists powered by Technitium.",
  "author": "RoostOS Core Team",
  "update_url": "https://plugins.roostos.org/api/v1/plugins/local-dns-resolver",
  
  "cockpit_ui": {
    "container": "dbus-bridge",
    "src_dir": "/var/www/cockpit",
    "dest_name": "local-dns-resolver"
  },
  
  "services": {
    "dns-server": {
      "image": "technitium/dns-server:latest",
      "ports": [
        "${dns_port:-53}:53/udp",
        "${dns_port:-53}:53/tcp",
        "${web_console_port:-5380}:5380/tcp"
      ],
      "volumes": [
        "/var/lib/roostos/plugins/dns/config:/etc/dns"
      ]
    },
    "dbus-bridge": {
      "image": "roostos/technitium-dbus-bridge:latest",
      "network_mode": "service:dns-server",
      "volumes": [
        "/var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket"
      ],
      "environment": {
        "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=/var/run/dbus/system_bus_socket",
        "TECHNITIUM_API_URL": "http://127.0.0.1:5380/api"
      }
    }
  }
}
```

### Manifest Fields Description:
1.  **Metadata (`id`, `name`, `version`, `description`, `author`)**: Basic identifiers. `id` must be alphanumeric and unique on the host.
2.  **`update_url`**: An HTTP/HTTPS JSON endpoint queried by the Roost Daemon to check for updates. The endpoint should return a payload containing the latest version and the download link.
3.  **`cockpit_ui`**:
    *   `container`: The service container containing the Web UI assets.
    *   `src_dir`: Directory inside the container containing HTML/CSS/JS.
    *   `dest_name`: Target directory created on the host at `/usr/share/cockpit/roostos-plugins/<dest_name>/`.
4.  **`services`**: Standard Docker Compose service specifications. Supports environment variable templating (e.g. `${dns_port:-53}`), allowing users to override port mappings or volume directories via their custom `settings` overrides inside `/etc/roostos/plugins.yaml`.

---

## 3. Plugin Installation & Update Lifecycle

```
[ Upload ZIP / Tarball ] 
          │
          ▼
[ Unpack to /var/lib/roostos/plugins/<id>/ ]
          │
          ▼
[ Register entry in /etc/roostos/plugins.yaml ]
          │
          ▼
[ Extract Cockpit UI assets from container to host ]
          │
          ▼
[ Run Docker Containers based on manifest.json ]
```

### A. The Installation Process
1.  **Upload**: The administrator uploads a plugin bundle (ZIP or tarball) via the Cockpit Web interface or drops it on the filesystem.
2.  **Extraction**: The daemon unpacks the archive into `/var/lib/roostos/plugins/<id>/`.
3.  **Registration**: The daemon appends the plugin registration record to `/etc/roostos/plugins.yaml`.
4.  **UI Asset Extraction**: Before starting the containers, `roostd` spins up the specified `cockpit_ui.container` temporarily and copies files from `cockpit_ui.src_dir` into the host's `/usr/share/cockpit/roostos-plugins/<dest_name>/` using docker copy extraction.
5.  **Execution**: The daemon launches the container services mapped in `services`, passing any custom overrides from `/etc/roostos/plugins.yaml`.

### B. The Update Check Process
*   **Daily Check**: A systemd-timer or internal thread in `roostd` runs daily to check for updates.
*   **API Query**: It makes an HTTP request to the `update_url` declared in the local manifest.
*   **Alerting**: If the returned `version` is greater than the current local version, the daemon triggers a D-Bus signal notifying Cockpit, which flags the plugin dashboard with an "Update Available" notification.
*   **Execution**: Clicking "Upgrade" causes the daemon to stop active containers, download the new tarball, unpack it over the old directory, re-extract the UI assets, and restart the containers.

---

## 4. Security & D-Bus Access Restrictions

Because plugin containers mount the host's `/var/run/dbus/system_bus_socket`, they can theoretically send messages to any host service registered on D-Bus. To restrict this and prevent container escape, RoostOS installs a strict **D-Bus System Policy file** (`/etc/dbus-1/system.d/org.roostos.conf`) on the host.

### `/etc/dbus-1/system.d/org.roostos.conf` Configuration:
```xml
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <!-- 1. Allow the core Roost Daemon running as root to own the D-Bus name -->
  <policy user="root">
    <allow own="org.roostos.Daemon"/>
    <allow send_destination="org.roostos.Daemon"/>
  </policy>

  <!-- 2. Allow third-party plugin containers to send messages ONLY to RoostOS interfaces -->
  <policy context="default">
    <deny send_destination="*"/> <!-- Deny all other host destinations (systemd, login1, networkd) -->
    
    <allow send_destination="org.roostos.Daemon"/>
    <allow send_destination="org.roostos.DNSResolver"/>
    <allow send_interface="org.roostos.Daemon"/>
    <allow send_interface="org.roostos.DNSResolver"/>
  </policy>
</busconfig>
```

### Multi-Architecture Support
To ensure portability between `x86_64` and `arm64` routers, all plugin container images must be built as multi-arch manifests (e.g. using `docker buildx`). The host engine daemon executes standard Docker CLI pulls, which automatically fetch the architecture matching the host's kernel.

---

## 5. Core D-Bus API Specifications

### Interface: `org.roostos.Daemon`
Registered on the System Bus at name `org.roostos.Daemon` and path `/org/roostos/Daemon`. It supports full CRUD (Create, Read, Update, Delete) and reactive signals for all core domain objects.

#### A. Methods

##### User Management
*   `GetUsers() -> (string JSON)`: Returns a JSON list of login users and their roles from `system.yaml`.
*   `UpdateUser(string username, string role, string person_id, array[string] ssh_keys) -> (bool success)`: Updates or inserts a Web UI user in `system.yaml`.
*   `DeleteUser(string username) -> (bool success)`: Deletes a user.

##### Person Management
*   `GetPeople() -> (string JSON)`: Returns a JSON list of family profiles from `devices.yaml`.
*   `UpdatePerson(string id, string name, string dns_profile) -> (bool success)`: Creates or updates a person profile.
*   `DeletePerson(string id) -> (bool success)`: Deletes a person profile.

##### Location Management
*   `GetBuildings() -> (string JSON)`: Returns a JSON list of physical building profiles.
*   `UpdateBuilding(string id, string name) -> (bool success)`: Creates or updates a building.
*   `DeleteBuilding(string id) -> (bool success)`: Deletes a building and unlinks rooms.
*   `GetRooms() -> (string JSON)`: Returns a JSON list of rooms.
*   `UpdateRoom(string id, string name, string building_id) -> (bool success)`: Creates/updates a room bound to a building.
*   `DeleteRoom(string id) -> (bool success)`: Deletes a room.

##### Device Management
*   `GetDevices() -> (string JSON)`: Returns a JSON list of registered client devices.
*   `UpdateDevice(string mac, string name, string owner_id, string location_id, array[string] tags, string static_ip, bool upnp_trusted, string upnp_allowed_ports_json) -> (bool success)`: Updates or registers a device, setting static DHCP reservations and UPnP trust and un-quarantining it if needed.
*   `DeleteDevice(string mac) -> (bool success)`: Removes a device, returning it to unregistered status.
*   `GetActiveLeases() -> (string JSON)`: Returns currently leased DHCP clients from cache.
*   `GrantTimeExtension(string mac, int duration_seconds) -> (bool success)`: Grants temporary firewall bypass.
*   `RemoveTimeExtension(string mac) -> (bool success)`: Revokes active time extension bypass.

##### Schedule Management
*   `GetSchedules() -> (string JSON)`: Returns active firewall schedules and limits.
*   `UpdateSchedule(string json_schedule) -> (bool success)`: Creates or updates a schedule block in `schedules.yaml`.
*   `DeleteSchedule(string name) -> (bool success)`: Removes a schedule block.

##### System Operations
*   `CreateBackup(string passphrase) -> (string backup_path)`: Bundles configuration files and caches into a compressed, passphrase-encrypted archive file on the host.
*   `RestoreBackup(string backup_path, string passphrase) -> (bool success)`: Decrypts, verifies, extracts, and reloads system configuration files from a backup archive.
*   `RebootHost() -> (bool success)`: Triggers a clean system reboot command.

##### UPnP Staging Gateway Control
*   `GetPendingUPnPRequests() -> (string JSON)`: Returns currently queued UPnP requests waiting for review.
*   `ApproveUPnPRequest(string mac, int port, string protocol, bool remember, bool trust_device) -> (bool success)`: Approves the pending port forward. If `remember` is true, registers it in `devices.yaml`. If `trust_device` is true, trusts all future UPnP mappings for the MAC.
*   `RejectUPnPRequest(string mac, int port, string protocol) -> (bool success)`: Rejects and cancels the pending port forward.

#### B. Properties
*   `RebootRequired` (bool, read-only): Exposes whether a system update has written to `/var/run/reboot-required`, signaling the UI to display a reboot prompt.

#### C. Signals
Emitted instantly when domains are modified, allowing the Cockpit UI and background plugins to update immediately without polling.
*   `UsersUpdated()`: Emitted when users are modified.
*   `PeopleUpdated()`: Emitted when family members are modified.
*   `LocationsUpdated()`: Emitted when buildings or rooms are modified.
*   `DevicesUpdated()`: Emitted when registered devices change.
*   `SchedulesUpdated()`: Emitted when schedules/limits change.
*   `DeviceConnected(string mac, string ip, string hostname)`: DHCP lease committed.
*   `UnknownDeviceDiscovered(string mac, string ip, string hostname)`: Unregistered device connected.
*   `BypassExpired(string mac)`: Dynamic time extension expired.
*   `UPnPRequestReceived(string mac, int port, string protocol, string description)`: Emitted when a new UPnP mapping requires staging review.
*   `UPnPQueueCleared()`: Emitted when the staging queue changes.

---

## 6. Interface: `org.roostos.DNSResolver`
Used to decouple local DNS engines. Any DNS plugin (such as the default Technitium plugin) must expose this interface on the D-Bus System Bus at path `/org/roostos/DNSResolver` so `roostd` can communicate with it generically.

#### Methods:
*   `SetClientDNSProfile(string mac, string profile_name) -> (bool success)`
    Maps a specific client MAC address to a DNS filtering profile (e.g. mapping Alice's MAC to the `Kids-Safe` profile to filter adult content).
*   `ClearClientDNSProfile(string mac) -> (bool success)`
    Removes any custom profile mapping for the MAC, returning them to the default global DNS profile.
*   `SetGlobalForwarders(array[string] forwarders) -> (bool success)`
    Configures upstream DNS forwarders (e.g. `["1.1.1.3", "8.8.8.8"]`).
*   `GetDNSProfiles() -> (string JSON)`
    Returns a list of available filtering profiles configured in the DNS engine.
*   `SetAdBlockingEnabled(bool enabled) -> (bool success)`
    Globally toggles ad-blocking on or off.

---

## 7. Remote Connectivity (Mobile App Integration Plugins)

To connect Android/iOS mobile applications to RoostOS, the system leverages the same plugin extension architecture instead of exposing a web server on the host OS. This guarantees that the core OS retains a minimal network footprint.

```
                  ┌─────────────── Host OS ───────────────┐
                  │                                       │
┌────────────┐    │  ┌─────────────────┐  ┌────────────┐  │
│ Mobile App ├─HTTPS►│  REST API Gateway  ├─►  System    │  │
└────────────┘    │  │ (Docker Plugin) │  │   D-Bus    │  │
                  │  └─────────────────┘  │            │  │
┌────────────┐    │  ┌─────────────────┐  │ (org.roostos.Daemon)
│ Mobile App ├─MQTT►│   MQTT Bridge   ├───┤            │  │
└────────────┘    │  │ (Docker Plugin) │  └────────────┘  │
                  │  └─────────────────┘                  │
                  └───────────────────────────────────────┘
```

---

## 8. The `roostos-sdk` Python Library

To abstract D-Bus IPC details, plugin developers can import `roostos-sdk`. The SDK supports both standard client requests and exposing custom D-Bus interfaces.

### Example: Implementing a DNS Resolver D-Bus Bridge (Inside a Sidecar)

```python
import requests
from roostos_sdk import DNSResolverServer

# Initialize the D-Bus provider
server = DNSResolverServer(dbus_name="org.roostos.DNSResolver")

# Implement the standard methods
@server.method()
def SetClientDNSProfile(mac: str, profile_name: str) -> bool:
    # 1. Translate the D-Bus call into Technitium REST API calls on localhost
    payload = {
        "token": "local-api-token",
        "ipOrMac": mac,
        "profile": profile_name
    }
    r = requests.post("http://127.0.0.1:5380/api/client/add", data=payload)
    return r.json().get("status") == "ok"

@server.method()
def SetAdBlockingEnabled(enabled: bool) -> bool:
    payload = {
        "token": "local-api-token",
        "block": "true" if enabled else "false"
    }
    r = requests.post("http://127.0.0.1:5380/api/blocklist/toggle", data=payload)
    return r.json().get("status") == "ok"

# Start listening on the D-Bus system bus
server.run()
```

---

## 9. Web UI Extensibility (Cockpit Plugins)

To support web UI plugins:
1.  **Asset Extraction**: A plugin's container image can package UI resources (HTML, CSS, JS) at `/var/www/cockpit/`.
2.  **Mounting/Copying**: Upon starting the container, `roostd` extracts this directory to `/usr/share/cockpit/roostos-plugins/<plugin-name>/`.
3.  **Rendering**: Cockpit reads this directory and dynamically adds tabs to the interface. The UI JavaScript in the plugin communicates directly with the plugin's own D-Bus service, keeping the interface responsive and isolated.
