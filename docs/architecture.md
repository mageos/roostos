# RoostOS Architecture

RoostOS is structured around a decoupled, secure, and declarative design. The system runs on Ubuntu Server, using standard Linux system services (systemd-networkd, IWD, nftables, Kea DHCP) coordinated by a central custom management daemon. 

DNS resolution is handled as a standard containerized plugin, decoupled from the core OS.

This document outlines the system layers, the communication pipeline, and the lifecycles of both persistent configurations and transient network states.

---

## 1. System Layers (The Layer Cake)

RoostOS separates concerns clearly into distinct layers:

```mermaid
graph TD
    UI[Web UI: Cockpit Custom Plugin] -->|D-Bus API| Engine[Roost Engine: Python Daemon]
    CLI[Terminal: CLI & YAML Editors] -->|File Write & D-Bus trigger| Engine
    
    subgraph Configuration Layer (Split YAML Files)
        Engine -->|Read/Write| ConfigSys[system.yaml]
        Engine -->|Read/Write| ConfigNet[network.yaml]
        Engine -->|Read/Write| ConfigDev[devices.yaml]
        Engine -->|Read/Write| ConfigSch[schedules.yaml]
        Engine -->|Read/Write| ConfigPlg[plugins.yaml]
    end
    
    Engine -->|Read/Write| Cache[(Transient Cache: SQLite)]
    
    subgraph System Services Layer
        Engine -->|Write Config & Reload| Networkd[systemd-networkd]
        Engine -->|Write Config & Restart| IWD[IWD Wireless Daemon]
        Engine -->|Write Config & Reload| Kea[Kea DHCP Server]
        Engine -->|nft CLI Commands| Nftables[nftables Firewall]
        Engine -->|Docker Compose API| Docker[Docker Engine]
    end
    
    subgraph DNS Plugin Container (Decoupled)
        Docker -.->|Runs| DNS[DNS Server e.g., Technitium]
        Docker -.->|Runs| Sidecar[RoostOS D-Bus Bridge Sidecar]
        DNS <-->|Localhost HTTP API| Sidecar
    end

    Kea -->|Event Hook| Hook[Kea Lease Hook]
    Hook -->|D-Bus Signal| Engine
    Sidecar <-->|D-Bus API: org.roostos.DNSResolver| Engine
```

### A. The UI & CLI Layer
*   **Cockpit Web UI**: Built as a custom Cockpit package using HTML, CSS, and vanilla JS. It runs client-side in the user's browser, communicating with the host OS strictly via D-Bus (`cockpit.dbus`). It has no direct root shell access, preventing command-injection vulnerabilities.
*   **Command Line Interface (CLI)**: A terminal-based utility allowing administrators to view, edit, and apply configurations. Developers and users can edit `/etc/roostos/*.yaml` files manually and then trigger a reload via a CLI command.

### B. The Management Layer (Roost Engine)
*   **Roost Engine (`roostd`)**: A Python-based system service managed by `systemd`. It serves as the coordinator of the OS. It:
    *   Exposes a D-Bus API for Cockpit and plugin integration.
    *   Validates and parses the split configuration YAML files.
    *   Generates configuration files for underlying system services.
    *   Maintains the transient runtime state in a local SQLite cache.
    *   Executes localized, safe helper functions (e.g., calling `nft` to add temporary MAC overrides, checking system status).
*   **`roostos-sdk`**: A Python helper library that third-party plugin developers use to communicate with `roostd` over D-Bus without writing raw D-Bus socket code.

### C. Configuration & State Layer
To enable safe terminal-based editing alongside reliable web-based updates, configuration is divided into five **strict YAML files** under `/etc/roostos/`:
*   `system.yaml`: Host credentials, timezone, HTTPS SSL, and update schedules.
*   `network.yaml`: Network interfaces, IP allocations, VLANs, Wi-Fi SSIDs, and mesh settings.
*   `devices.yaml`: Shared domain registry mapping devices, persons, rooms, and static reservations. The Web UI writes back to this file exclusively when registering new MAC addresses.
*   `schedules.yaml`: Time-based schedules, bedtime blocks, and daily usage limits.
*   `plugins.yaml`: Installed plugin container definitions and volume setups.

All dynamic runtime values (like active DHCP leases, temporary bypass timers, and daily screen time accumulation metrics) are separated from the config files and cached in `/var/lib/roostos/state.db`.

### D. System Services Layer
*   **systemd-networkd**: Manages physical network interfaces, bridge interfaces, static IPs, and VLAN configurations. We bypass Netplan to prevent configuration conflicts when dealing with Mesh Wi-Fi and IWD.
*   **IWD (iNet Wireless Daemon)**: Handles Wi-Fi client connection and Access Point (AP) mesh capabilities.
*   **Kea DHCP**: Distributes IPv4/IPv6 addresses. Runs a lease hook library to push lease events to D-Bus in real time.
*   **nftables**: The Linux firewall framework. Used to configure routing, NAT, static port forwards, and tag-based network isolation.
*   **Docker & Docker Compose**: The container runtime hosting third-party plugins.

---

## 2. Decoupled DNS Architecture

Rather than hardcoding a specific DNS server (like Technitium DNS) into the core `roostd` daemon, RoostOS exposes a standard **D-Bus Interface (`org.roostos.DNSResolver`)**. 
*   **The DNS Container**: Runs the chosen DNS software (Technitium by default).
*   **The Sidecar Bridge**: A lightweight container running in the same network namespace. It listens on D-Bus system bus, exposes the `org.roostos.DNSResolver` interface, and translates core command queries into DNS-specific API requests (e.g. Technitium HTTP requests).
*   **Decoupling Benefit**: Swapping Technitium for AdGuard Home or Pi-hole is as simple as launching a different DNS plugin that implements the same D-Bus interface. The host `roostd` engine remains unchanged.

---

## 3. Bootstrapping & Security

### A. First-Boot Bootstrap DNS
To resolve the circular dependency where a working DNS server is required to pull the container images (including the DNS plugin itself):
1.  **Bootstrap Resolution**: During system installation/first boot, the host OS utilizes standard **systemd-resolved** configured to query public upstream DNS resolvers (e.g., `1.1.1.1` or `8.8.8.8`).
2.  **Plugin Pull**: `roostd` uses this temporary resolution to authenticate, pull, and spin up the Docker DNS resolver container.
3.  **Active Switch**: Once the DNS container passes its health checks and exposes its local DNS port, the daemon switches the host's `/etc/resolv.conf` symlink to point to `127.0.0.1`.

### B. Cockpit User Account Security
Cockpit relies on standard Linux PAM authentication. To allow standard users (such as `parent` or `member` roles) to log into the Cockpit Web interface without granting SSH/terminal access:
1.  **Restricted Shell**: When `roostd` creates these users on the host OS, it sets their default shell to `/usr/sbin/nologin` or `/bin/false`.
2.  **SSH Lockout**: The system SSH daemon config (`/etc/ssh/sshd_config`) is automatically restricted:
    ```
    AllowGroups admin
    ```
    This allows non-admin family accounts to log into the web dashboard while strictly preventing them from opening terminal sessions.

### C. Automatic HTTPS (Let's Encrypt Integration)
Cockpit serves its Web interface over port 9090 using SSL certificates stored in `/etc/cockpit/ws-certs.d/`. 
To ensure secure HTTPS access:
1.  **ACME Client Integration**: RoostOS uses an integrated ACME client script (such as `acme.sh` or `certbot`) coordinated by `roostd`.
2.  **DNS-01 Challenge**: The default certification method utilizes the **DNS-01 challenge** (using API credentials for Cloudflare, Namecheap, etc., configured in `system.yaml`). This avoids opening port 80 to the WAN and works behind double-NAT or dynamic IPs.
3.  **http-01 Fallback**: If DNS-01 is not configured, the daemon can spin up a temporary standalone HTTP challenge server on port 80, requesting the cert from Let's Encrypt.
4.  **Auto-Load & Reload**: Once generated or renewed, the daemon compiles the private key and certificate into the expected `.cert` format inside `/etc/cockpit/ws-certs.d/` and runs `systemctl reload cockpit.socket`.

---

## 4. Updates & Maintenance Windows

Keeping a router updated is critical for security. RoostOS splits updates into two categories:

### A. Non-Disruptive Auto-Updates
*   **Automatic Installs**: RoostOS configures Ubuntu's **`unattended-upgrades`** to automatically download and install minor packages, libraries, and security patches daily.
*   **No Interruption**: These upgrades happen in the background without affecting routing, DHCP, or firewall operations.

### B. Reboot-Required Updates (Maintenance Windows)
*   **Pending Detection**: When a kernel update or a core libc patch is installed, Ubuntu writes to `/var/run/reboot-required`.
*   **D-Bus and UI Signals**: The daemon monitors this file. If it exists:
    *   Exposes `RebootRequired = true` over D-Bus.
    *   Displays an "Update Pending Reboot" banner in the Cockpit Web UI, allowing parents/admins to click "Reboot Now".
*   **Scheduled Reboots**: If not rebooted manually, the daemon checks the maintenance window defined in `system.yaml` (e.g. Sunday at 3:00 AM). When that time matches and `/var/run/reboot-required` exists, the daemon issues a system reboot command.

---

## 5. Built-in Backup & Restore

To ensure simple recovery and system migration:
*   **Backup Contents**: The backup utility packages the entire persistent configuration directory `/etc/roostos/` (all five YAML files) and the transient cache `/var/lib/roostos/state.db` (for DHCP lease and device histories) into a single tarball.
*   **Cryptography (Security)**: The tarball is optionally encrypted with a user-supplied password using GnuPG (`gpg`) before being made available for download.
*   **API Methods**:
    *   `CreateBackup(string passphrase) -> (string backup_path)`: Compresses, encrypts, and returns the path to the backup file.
    *   `RestoreBackup(string backup_path, string passphrase) -> (bool success)`: Unpacks and decrypts the backup, validates the YAML configurations, and triggers a full system configuration reload.
*   **UI Integration**: The Cockpit UI features a dedicated **Backups** tab allowing admins to trigger backups, download files locally, or upload an existing backup archive to restore the router's state.
