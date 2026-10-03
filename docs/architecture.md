# RoostOS Architecture

RoostOS is structured around a decoupled, secure, distributed, and declarative design. The system runs on Debian-based Linux distributions, using standard Linux system services (`systemd-networkd`, `IWD`, `nftables`, `Kea DHCP`) coordinated by a decoupled management engine and client daemons communicating over MQTT and D-Bus. It is packaged as installable `.deb` packages, allowing users to install only the components required for their specific deployment.

DNS resolution is handled as a standard containerized plugin, decoupled from the core OS.

This document outlines the three-service architecture, system layers, communication pipelines, and component lifecycles across both local and distributed nodes.

---

## 1. Core Components

RoostOS separates concerns into distinct, modular services that can run on a single standalone router or be distributed across multiple systems in a home network.

* **`roostos` (Root Base Package & Universal Setup Wizard)**: Provides the `/usr/bin/roostos` CLI, hardware introspection, and a hardware-aware guided setup wizard (`roostos setup`) that detects system capabilities and installs/configures the appropriate roles.
* **`roostos-node` (Base Infrastructure Agent & Local REST API)**: The base management daemon running on every infrastructure node (port 8000). Provides host telemetry, physical interface controls, system diagnostics, and serves the local Web Console SPA, ensuring independent local survivability and management during network or central server outages.
* **`roostos-gateway` (Edge Gateway Router Stack)**: The routing and firewall stack installed on gateway hardware. It manages physical system states (`systemd-networkd`, `Kea DHCP` leases/subnets, `nftables` rulesets/sets, and `IWD` mesh), maintaining an autonomous local SQLite state cache.
* **`roostos-engine` (Central Domain Controller & Cluster Service)**: The central source of truth for all domain objects across nodes (devices, people, buildings, rooms, schedules, firewall policies, plugins). It manages persistent multi-node configuration storage (`/etc/roostos/`), coordinates cluster sync, runs the central MQTT broker (`mosquitto`), and orchestrates container workloads.
* **`roostos-workstation` (Unified Client Endpoint Stack)**: Screen time, parental controls, and domain enrollment client installed on client workstations (laptops/desktops). Runs the lightweight `roostos-timeguardd` daemon (monitoring `systemd-logind` sessions), enforces daily screen time and bedtime curfews via PAM hooks, and connects to RoostOS domain controllers without opening any inbound listening ports.

---

## 2. System Layers (The Layer Cake)

RoostOS separates concerns clearly into distinct operational layers:

```mermaid
graph TD
    UI[Web UI: roostos-web / roostos-node SPA] -->|FastAPI REST API: port 8000| NodeAgent[roostos-node: Local REST Daemon]
    CLI[Terminal: roostos CLI] -->|Local REST API / Setup| NodeAgent
    
    Engine[roostos-engine: Central Controller] <-->|mTLS / REST & MQTT Sync| NodeAgent
    NodeAgent --> Gateway[roostos-gateway: Routing Stack]
    Engine <-->|MQTT Broker: roostos/timeguard/*| Workstation[roostos-workstation: Client Daemon]
    
    subgraph Configuration Layer (Split YAML Files)
        Engine -->|Read/Write| ConfigSys[system.yaml]
        Engine -->|Read/Write| ConfigNet[network.yaml]
        Engine -->|Read/Write| ConfigDev[devices.yaml]
        Engine -->|Read/Write| ConfigSch[schedules.yaml]
        Engine -->|Read/Write| ConfigFw[firewall.yaml]
        Engine -->|Read/Write| ConfigPlg[plugins.yaml]
    end
    
    Gateway -->|Read/Write| Cache[(Transient Cache: SQLite)]
    
    subgraph System Services Layer (Managed by roostos-gateway)
        Gateway -->|Write Config & Reload| Networkd[systemd-networkd]
        Gateway -->|Write Config & Restart| IWD[IWD Wireless Daemon]
        Gateway -->|Write Config & Reload| Kea[Kea DHCP Server]
        Gateway -->|nft CLI Commands| Nftables[nftables Firewall]
    end
```

### A. The UI & CLI Layer
* **Web Management Console (`roostos-web` / `roostos-node`)**: Built using HTML, CSS, and Vanilla JS / Web Components, served by FastAPI on port 8000 on each node for independent local survivability and single-pane-of-glass cluster management.
* **Command Line Interface (`roostos`)**: Universal root CLI utility providing hardware inspection, environment discovery, and the setup wizard (`roostos setup`).

### B. The Management Layer
* **`roostos-engine`**: Python-based central coordinator daemon. Maintains the single source of truth for domain objects across all nodes, validates 6-file split YAML configurations, issues mTLS certificates, and broadcasts change notifications over MQTT.
* **`roostos-gateway`**: Host-level edge routing daemon. Applies firewall rules via `nftables`, manages physical interface configs with `systemd-networkd`, runs `Kea DHCP`, and maintains the local SQLite lease cache.

### C. Configuration & State Layer
Configuration is divided into **six strict YAML files** under `/etc/roostos/`:
* `system.yaml`: Host credentials, timezone, HTTPS SSL settings, unattended updates, and global unregistered device policy (`allow` | `deny`).
* `network.yaml`: Network interfaces, bridges, IP allocations, VLAN subnets, Wi-Fi SSIDs, and mesh settings.
* `devices.yaml`: Shared family registry mapping devices, persons, buildings, rooms, static IP allocations, and UPnP trust settings.
* `schedules.yaml`: Time-based access windows and daily accumulated screen time allowance limits.
* `firewall.yaml`: Permanent input rules, port forwards, and custom firewall chain definitions.
* `plugins.yaml`: Installed plugin metadata, enabled flags, container definitions, requested scopes, and settings overrides.

Dynamic runtime values (active DHCP leases, pending UPnP staging requests) are cached locally on node daemons in `/var/lib/roostos/state.db` and synchronized with `roostos-engine` via MQTT events.

### D. System Services Layer
* **systemd-networkd**: Controls physical interface bindings, bridges, static IPs, and VLAN subinterfaces directly.
* **IWD (iNet Wireless Daemon)**: Manages Wi-Fi access points and 802.11s mesh networking.
* **Kea DHCP**: Distributes IPv4/IPv6 address leases. Executes `roost-dhcp-hook` to emit lease commit signals over local D-Bus to `roostos-core`.
* **nftables**: Manages packet filtering, NAT masquerading, DNS hijacking, and tag-based network isolation via three dynamic sets (`quarantined`, `schedule_blocked`, `admin_blocked`).
* **Docker / Podman**: Container runtime hosting core service plugins and application workloads.

---

## 3. Decoupled DNS Architecture

RoostOS exposes a standard local **D-Bus Interface (`org.roostos.DNSResolver`)** for DNS containers on the local router host.
* **The DNS Container**: Runs the chosen DNS engine (Technitium DNS by default).
* **The Sidecar Bridge**: A lightweight container sharing the DNS container's network namespace (`network_mode: "service:dns-server"`). It mounts the local host D-Bus system bus socket, exposes `org.roostos.DNSResolver`, and translates D-Bus calls into Technitium local HTTP API calls.
* **MQTT Bridge**: `roostos-core` listens to `org.roostos.DNSResolver` D-Bus events locally and bridges them to MQTT topics (`roostos/dns/#`), enabling remote nodes and `roostos-engine` to manage DNS profiles network-wide.

---

## 4. Bootstrapping & Security

### A. First-Boot Bootstrap DNS
1. **Bootstrap Resolution**: During installation, the system uses `systemd-resolved` configured with temporary upstream DNS resolvers (e.g., `1.1.1.1`).
2. **Plugin Pull**: `roostos-core` uses bootstrap resolution to authenticate, pull, and launch the containerized DNS resolver plugin.
3. **Active Switch**: Once the DNS container passes health checks, the daemon switches host `/etc/resolv.conf` to `127.0.0.1`.

### B. Console Authentication & Security
* **PAM Integration**: `roostos-web` validates user credentials against Linux PAM (or custom OAuth2 authentication providers), issuing signed JWT access tokens upon login.
* **Restricted Shells & SSH Lockout**: Standard family user accounts created for dashboard access have default shell set to `/usr/sbin/nologin`. `/etc/ssh/sshd_config` enforces `AllowGroups admin` to prevent non-admin terminal access.

### C. Automatic HTTPS (Let's Encrypt Integration)
`roostos-web` serves traffic securely over HTTPS:
1. **ACME Client**: Coordinated by `roostos-engine` using DNS-01 challenge APIs (Cloudflare, Namecheap, etc.) or standalone `http-01` challenge fallback on port 80.
2. **Cert Reload**: SSL certificates are stored in `/etc/roostos/certs/` and auto-reloaded by `roostos-web`.

---

## 5. Updates & Maintenance Windows

* **Non-Disruptive Updates**: Ubuntu `unattended-upgrades` installs security patches daily in the background.
* **Reboot-Required Detection**: When updates write to `/var/run/reboot-required`, `roostos-engine` detects the flag and exposes `reboot_required` via REST API and MQTT, displaying a banner in `roostos-web` and scheduling reboots during the configured maintenance window (`system.yaml`).

---

## 6. Built-in Backup & Restore

* **Backup Contents**: Packages `/etc/roostos/` (all 6 YAML files) and `state.db` cache histories into a compressed archive.
* **Encryption**: Encrypted with AES-256 via GnuPG (`gpg`) using user-supplied passphrases.
* **REST API**: Exposes `POST /api/v1/system/backup` and `POST /api/v1/system/restore` endpoints.
