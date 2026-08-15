# RoostOS Features & Tools Mapping

RoostOS avoids "reinventing the wheel." Instead of writing a routing stack, a DNS server, or a firewall engine from scratch, it leverages mature, standard Linux open-source tools. The role of RoostOS is to act as the orchestrator—providing a unified configuration engine (`roostos-engine`), node management daemons (`roostos-core`), an MQTT messaging backbone, and an intuitive Web UI (`roostos-web`).

This document outlines the mapping between RoostOS features, their underlying backend tools, and the custom glue code built into RoostOS.

---

## Feature & Tool Matrix

| Feature | Backend Tool | Role of Backend Tool | What We Build (The Glue) |
| :--- | :--- | :--- | :--- |
| **Network Interfaces & VLANs** | `systemd-networkd` | Configures network interfaces, VLAN subinterfaces, bridges, and static routes. | YAML parser (`roostos-engine`) that compiles network definitions into `/etc/systemd/network/*.network` and `*.netdev` files via `roostos-core`. |
| **Wi-Fi Access Point & MESH** | `IWD` (iNet Wireless Daemon) | Manages Wi-Fi interfaces, connections, AP mode, and 802.11s Mesh networks. | Generator for `/etc/iwd/*.link` and main config files. D-Bus/MQTT queries to monitor signal strength and Wi-Fi networks. |
| **DNS Resolution & Filtering** | **DNS Container Plugin** (Technitium by default) | Resolves DNS names, blocks ads, and runs DNS-level client-filtering profiles. | A sidecar D-Bus bridge container (`org.roostos.DNSResolver`) bridged to MQTT (`roostos/dns/#`) by `roostos-core`. |
| **DHCP Address Allocation** | `Kea DHCP Server` | Handles IPv4/IPv6 leases, subnet pools, and static IP reservations. | Configuration generator for Kea (`/etc/kea/kea-dhcp4.conf`). `roost-dhcp-hook` emitting lease events over D-Bus and MQTT. |
| **Firewall & NAT** | `nftables` | Packet filtering, NAT masquerading, port forwarding, DNS hijacking, DoT/DoH blocking. | `nftables` ruleset generator using `firewall.yaml` and three dynamic sets (`quarantined`, `schedule_blocked`, `admin_blocked`). |
| **VPN Client & Server** | `Wireguard` | Kernel-level high-performance VPN tunnels. | Generator for Wireguard Netdev configurations in `systemd-networkd`, enabling policy routing for target devices. |
| **Containerized Plugins** | `Docker` / `Podman` | Running core service plugins and application container workloads. | Container orchestration in `roostos-engine`. Multi-arch OCI registry pulling, mTLS certificate provisioning, and scope enforcement. |
| **Family Controls & Screen Time** | `systemd-logind` & `roostos-timeguardd` | Session tracking and locking on client systems. | `roostos-timeguardd` client daemon tracking local logind sessions, caching limits offline, and syncing via MQTT with `roostos-engine`. |
| **Administration Web UI** | `FastAPI` & Vanilla JS / Web Components | Web server, API routing, and user interface. | Modern single-page console UI (`roostos-web`) providing dashboard, device management, schedules, and dynamic plugin UI extensions. |
| **Backup & Restore** | Standard Linux tools (`tar`, `gzip`, `gpg`) | File compression and AES-256 encryption. | Python backup utilities in `roostos-engine` bundling 6 YAML files and state databases, exposed via REST API. |

---

## Detailed Tool Implementations

### 1. Network Layer (`systemd-networkd` & `IWD`)
RoostOS uses **`systemd-networkd`** for low-overhead, deterministic network management.
* **VLAN Subnets**: For guest networks and IoT isolation, `systemd-networkd` creates VLANs using `.netdev` (defining VLAN IDs) and `.network` (assigning to bridges).
* **MESH Wi-Fi**: **`IWD`** replaces older wireless daemons, offering native support for WPA3, fast roaming, and 802.11s mesh networking.
* *Custom code*: `roostos-core` reads `network.yaml` configuration payloads from `roostos-engine` via MQTT, generates networkd/IWD config files, and executes `networkctl reload` and `systemctl restart iwd`.

### 2. DHCP (`Kea DHCP`)
* **D-Bus & MQTT Hook**: Kea executes `libdhcp_run_script.so` (`roost-dhcp-hook`) on lease commits.
* *Custom code*: `roostos-core` catches local lease commit signals, updates local SQLite `/var/lib/roostos/state.db`, and broadcasts MQTT events (`roostos/dhcp/lease/commit`) to `roostos-engine`.

### 3. DNS (Decoupled Sidecar Plugin)
* **Standard Interface**: `roostos-core` exposes `org.roostos.DNSResolver` over local D-Bus.
* **Technitium sidecar**: The default DNS plugin runs Technitium alongside a custom **RoostOS D-Bus Bridge** sidecar in the same network namespace.
* **MQTT Bridge**: `roostos-core` bridges local DNS D-Bus events to MQTT topics (`roostos/dns/#`) for cluster-wide management.

### 4. Firewall (`nftables` Security Rules)

#### A. Three Dynamic Sets Strategy
Instead of reloading the full firewall on every schedule tick, `roostos-core` dynamically adds/removes client MAC addresses across three `nftables` sets:
1. `quarantined`: Unregistered MAC addresses when `unregistered_device_policy: deny` is set. Dropped completely at input and forward chains.
2. `schedule_blocked`: MAC addresses with active schedule blocks or exhausted daily screen time limits. Dropped **only on WAN-bound forwarding** (LAN access retained).
3. `admin_blocked`: MAC addresses permanently blocked from internet access by administrator policy. Dropped on WAN-bound forwarding.

#### B. Stateful Inter-Zone Connection Tracking
Inter-zone routing defined by `allow_zones` in `network.yaml` enforces stateful connection tracking:
1. **Connection Initiation**: `allow_zones` specifies destination zones where devices in the source zone can **initiate NEW connections** (`ct state new`).
2. **Stateful Return Traffic**: `ct state established,related accept` is placed at the top of the forward chain. When a device on `lan` initiates a connection to an `iot` bulb, return packets are automatically allowed back to `lan`. Unsolicited new connection attempts from `iot` to `lan` are blocked.

```nftables
table inet filter {
    chain forward {
        type filter hook forward priority filter; policy drop;

        # 1. Allow return packets for existing established connections
        ct state established,related accept

        # 2. Allow NEW connections based on allow_zones
        iifname @zone_lan oifname @zone_wan ct state new accept
        iifname @zone_lan oifname @zone_iot ct state new accept
        iifname @zone_iot oifname @zone_wan ct state new accept

        # 3. Drop unauthorized new connections
        log prefix "FIREWALL:BLOCKED:Unauthorized_Zone_Forward " drop
    }
}
```

#### C. DNS Hijacking (Force Local DNS)
To prevent clients from bypassing parental blocklists by manually setting DNS to `8.8.8.8`, `roostos-core` generates DNAT rules:
```nftables
table ip nat {
    chain prerouting {
        type filter hook prerouting priority dstnat; policy accept;
        iifname "br0" tcp dport 53 redirect to :53
        iifname "br0" udp dport 53 redirect to :53
    }
}
```

#### C. Encrypted DNS Blocking (DoH / DoT)
- **DoT Blocking**: Drop outbound traffic to port `853` (TCP/UDP) at the forward chain.
- **DoH Blocking**: Technitium DNS includes blocklists for known public DoH providers (e.g. `cloudflare-dns.com`). `roostos-core` populates an `nftables` set `doh_server_ips` with known public DoH resolver IPs and drops outbound port 443 traffic to them.

### 5. Web UI (`roostos-web`)
FastAPI serves the Web Console SPA, managing OAuth2 JWT tokens, PAM user authentication, HTTPS Let's Encrypt certificates, and dynamic plugin ES Module UI tab loading.
