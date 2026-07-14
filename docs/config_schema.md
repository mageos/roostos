# RoostOS Configuration Schema

To ensure safe terminal-based editing and robust write-backs from the Web UI, RoostOS divides its declarative configuration into five strict YAML files located under `/etc/roostos/`. 

The Roost Engine daemon (`roostd`) parses these files, validates their schema collectively, and applies them to the system.

---

## 1. Split File Structure

```
/etc/roostos/
├── system.yaml        # System identity, timezones, HTTPS certs, updates, and logins
├── network.yaml       # Interfaces, bridges, VLAN subnets, and mesh SSIDs
├── devices.yaml       # User roles, people, buildings, rooms, and registered devices
├── schedules.yaml     # Time-based firewall policies and daily allowances
└── plugins.yaml       # Installed plugins registration and user-defined settings overrides
```

---

## 2. File Specifications & Schemas

### A. `/etc/roostos/system.yaml`
Declares host credentials, administrative settings, Let's Encrypt HTTPS config, and unattended update window settings.

```yaml
# system.yaml
system:
  hostname: roost-router
  timezone: America/Chicago
  
  https:
    enabled: true
    domain: router.myhome.com
    email: admin@myhome.com
    acme_provider: letsencrypt
    challenge_type: dns-01
    dns_provider: cloudflare
    dns_credentials_file: /etc/roostos/cloudflare.ini

  updates:
    auto_install: true
    auto_reboot: true
    reboot_window:
      days: ["Sun"]
      time: "03:00"
```

---

### B. `/etc/roostos/network.yaml`
Configures bridges, VLAN subnets, physical interfaces, and Wi-Fi networks (SSIDs / Mesh).

```yaml
# network.yaml
network:
  interfaces:
    - name: eth0
      role: wan
      dhcp: true
    - name: eth1
      role: lan
      bridge: br0
  
  bridges:
    - name: br0
      ip: 192.168.1.1/24

  vlans:
    - name: vlan-iot
      id: 10
      interface: br0
      ip: 10.0.10.1/24
      isolate: true
    - name: vlan-guest
      id: 20
      interface: br0
      ip: 10.0.20.1/24
      isolate: true

wifi:
  access_points:
    - ssid: "Roost Home"
      interface: wlan0
      passphrase: "SuperSecurePassword123"
      security: wpa3
      bridge: br0
```

---

### C. `/etc/roostos/devices.yaml`
Contains the shared family registry. The Cockpit Web UI exclusively edits and writes back to this file when registering new MAC addresses, static IPs, and UPnP trust permissions.

```yaml
# devices.yaml
people:
  - id: mom_profile
    name: "Mom"
  - id: alice_profile
    name: "Alice (Kid)"
    dns_profile: "Kids-Filtering"

buildings:
  - id: main_house
    name: "Main House"

rooms:
  - id: living_room
    name: "Living Room"
    building: main_house

devices:
  - mac: "a4:83:e7:12:34:56"
    name: "Mom's Laptop"
    owner: mom_profile
    location: living_room
    tags: ["personal"]
    static_ip: 192.168.1.10
  
  - mac: "4c:32:75:98:76:54"
    name: "Alice's iPad"
    owner: alice_profile
    tags: ["kids"]
    static_ip: 192.168.1.50
    upnp_trusted: false           # Must request approval for any UPnP port forwards
    upnp_allowed_ports:           # Pre-approved static UPnP rules
      - port: 3074
        protocol: udp

  - mac: "00:09:b0:12:34:56"
    name: "Xbox Series X"
    owner: alice_profile
    tags: ["gaming"]
    upnp_trusted: true            # Automatically approves all UPnP requests from this MAC
```
*   **`upnp_trusted`**: Toggles whether the device can open ports automatically.
*   **`upnp_allowed_ports`**: Stores specific port-protocol rules approved by the parent.

---

### D. `/etc/roostos/schedules.yaml`
Declares firewall schedules, bedtime blocks, daily accumulated limits, and static port forwards.

```yaml
# schedules.yaml
firewall:
  port_forwards:
    - name: "Plex Server"
      protocol: tcp
      external_port: 32400
      internal_ip: 192.168.1.10
      internal_port: 32400

  schedules:
    # 1. Fixed Time-Window Block
    - name: "Kids Bedtime Block"
      targets:
        - tag: kids
      days: ["Mon", "Tue", "Wed", "Thu", "Fri"]
      start_time: "21:00"
      end_time: "06:00"
      action: block_internet

    # 2. Daily Accumulated Usage Limit
    - name: "Alice Daily Screen Time Limit"
      targets:
        - person: alice_profile
      daily_limit: 120
      action: block_internet
```

---

### E. `/etc/roostos/plugins.yaml`
Registers active plugins and maps them to their local manifest configuration profiles.

```yaml
# plugins.yaml
plugins:
  - id: local-dns-resolver
    enabled: true
    manifest_path: "/var/lib/roostos/plugins/local-dns-resolver/manifest.json"
    settings:
      dns_port: 53
      web_console_port: 5380
```
