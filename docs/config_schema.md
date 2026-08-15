# RoostOS Configuration Schema

To ensure safe terminal-based editing and robust write-backs from the Web UI / REST API, RoostOS divides its declarative configuration into six strict YAML files located under `/etc/roostos/`. 

The Roost Engine daemon (`roostos-engine`) parses these files, validates their schema collectively using Pydantic DTO models, and publishes configuration updates across the cluster via MQTT.

---

## 1. Split File Structure

```
/etc/roostos/
├── system.yaml        # System identity, timezones, HTTPS certs, updates, global policies, and logins
├── network.yaml       # Interfaces, bridges, VLAN subnets, gateways, QoS, and mesh SSIDs
├── devices.yaml       # User accounts, family profiles (people), buildings, rooms, and registered devices
├── schedules.yaml     # Time-window access rules and daily screen time allowance limits
├── firewall.yaml      # Static input rules, port forwards, and custom nftables policies
└── plugins.yaml       # Installed plugin definitions, requested scopes, containers, and settings overrides
```

---

## 2. File Specifications & Schemas

### A. `/etc/roostos/system.yaml`
Declares host credentials, administrative settings, Let's Encrypt HTTPS config, unattended update window settings, and global unregistered device security policy.

```yaml
# system.yaml
system:
  hostname: roost-router
  domain: lan
  realm: ROOSTOS.LOCAL                # Directory Services / Active Directory realm equivalent
  timezone: America/Chicago
  unregistered_device_policy: deny   # "allow" (open network) or "deny" (quarantine unknown MACs)
  docker_registry: ghcr.io
  
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

users:
  - username: admin
    role: admin
    ssh_keys:
      - "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..."
  - username: parent
    role: parent
    person: mom_profile
```

---

### B. `/etc/roostos/network.yaml`
Configures bridges, VLAN subnets, physical interfaces, gateways, traffic shaping (QoS), and Wi-Fi networks (SSIDs / Mesh).

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
      dhcp_enabled: true

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

  zones:
    - id: lan
      name: "Household LAN"
      interfaces: ["br0"]
      isolate: false
    - id: iot
      name: "Smart Home IoT Zone"
      interfaces: ["vlan-iot"]
      isolate: true
      allow_zones: ["wan"]
    - id: guest
      name: "Guest Wi-Fi Zone"
      interfaces: ["vlan-guest"]
      isolate: true
      allow_zones: ["wan"]

  qos:
    enabled: true
    wan_upload_kbps: 50000
    wan_download_kbps: 300000
    prioritize_tags: ["work", "voip"]

wifi:
  access_points:
    - ssid: "Roost Home"
      interface: wlan0
      passphrase: "SuperSecurePassword123"
      security: wpa3-sae
      bridge: br0
```

---

### C. `/etc/roostos/devices.yaml`
Contains the shared family registry. The Web UI exclusively edits and writes back to this file when registering new MAC addresses, static IPs, and UPnP trust permissions.

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
    tags: ["personal", "work"]
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

---

### D. `/etc/roostos/schedules.yaml`
Declares time-window access rules and daily accumulated usage allowance limits.

```yaml
# schedules.yaml
firewall:
  schedules:
    # 1. Fixed Time-Window Block
    - name: "Kids Bedtime Block"
      targets:
        - tag: kids
      days: ["Mon", "Tue", "Wed", "Thu", "Fri"]
      start_time: "21:00"
      end_time: "06:00"
      action: block_internet

    # 2. Daily Accumulated Usage Limit (Minutes)
    - name: "Alice Daily Screen Time Limit"
      targets:
        - person: alice_profile
      daily_limit: 120            # 2 hours per day
      action: block_internet
```

---

### E. `/etc/roostos/firewall.yaml`
Declares permanent firewall input rules, port forwards, and routing rules.

```yaml
# firewall.yaml
firewall:
  port_forwards:
    - name: "Plex Server"
      protocol: tcp
      external_port: 32400
      internal_ip: 192.168.1.10
      internal_port: 32400

  rules:
    - name: "Allow SSH from Management LAN"
      interface: br0
      protocol: tcp
      port: 22
      source: "192.168.1.0/24"
      action: accept
      enabled: true

    - name: "Drop Inbound Telnet"
      interface: "*"
      protocol: tcp
      port: 23
      action: drop
      enabled: true
```

---

### F. `/etc/roostos/plugins.yaml`
Registers active plugins, requested permission scopes, container definitions, and user settings overrides.

```yaml
# plugins.yaml
plugins:
  - id: local-dns-resolver
    name: "Technitium DNS Resolver"
    type: core_service             # "core_service" or "application"
    enabled: true
    network_mode: bridge
    requested_scopes:
      - "dns:manage"
      - "network:read"
    containers:
      - name: dns-server
        image: technitium/dns-server:latest
        ports:
          - host_port: 53
            container_port: 53
            protocol: udp
          - host_port: 53
            container_port: 53
            protocol: tcp
          - host_port: 5380
            container_port: 5380
            protocol: tcp
        volumes:
          - host_path: /var/lib/roostos/plugins/dns/config
            container_path: /etc/dns
      - name: dbus-bridge
        image: roostos/technitium-dbus-bridge:latest
        environment:
          TECHNITIUM_API_URL: "http://127.0.0.1:5380/api"
    ui_entrypoint: "/var/www/cockpit/ui.js"
    known_services:
      - "dns"
    settings:
      dns_port: 53
      web_console_port: 5380
```
