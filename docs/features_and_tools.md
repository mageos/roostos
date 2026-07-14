# RoostOS Features & Tools Mapping

RoostOS avoids "reinventing the wheel." Instead of writing a routing stack, a DNS server, or a firewall engine from scratch, it leverages mature, standard Linux open-source tools. The role of RoostOS is to act as the "orchestrator"—providing a unified configuration, a unified D-Bus API, and an intuitive Web UI (Cockpit).

This document outlines the mapping between RoostOS features, their underlying backend tools, and the custom code we must build.

---

## Feature & Tool Matrix

| Feature | Backend Tool | Role of Backend Tool | What We Must Build (The Glue) |
| :--- | :--- | :--- | :--- |
| **Network Interfaces & VLANs** | `systemd-networkd` | Configures network interfaces, VLAN subinterfaces, bridges, and static routes. | YAML parser that writes `/etc/systemd/network/*.network` and `*.netdev` files. |
| **Wi-Fi Access Point & MESH** | `IWD` (iNet Wireless Daemon) | Manages Wi-Fi interfaces, connections, AP mode, and 802.11s Mesh networks. | Generator for `/etc/iwd/*.link` and main config files. D-Bus commands to query signal strength and Wi-Fi networks. |
| **DNS Resolution & Filtering** | **DNS Container Plugin** (Technitium by default) | Resolves DNS names, blocklists ads, and runs DNS-level client-filtering profiles. | A custom sidecar D-Bus bridge container that exposes the `org.roostos.DNSResolver` API and queries the local DNS server. |
| **DHCP Address Allocation** | `Kea DHCP Server` | Handles IPv4/IPv6 leases, subnet pools, and static IP reservations. | Configuration generator for Kea (`/etc/kea/kea-dhcp4.conf`). A D-Bus notification hook script triggered by Kea on lease commits. |
| **Firewall & NAT** | `nftables` | Packet filtering, NAT (masquerading), port forwarding, DNS hijacking, DoT/DoH blocking. | Core nftables ruleset template generator. Python integration utilizing `nft` commands to dynamically add/remove MACs from IP/MAC sets. |
| **VPN Client & Server** | `Wireguard` | Kernel-level high-performance VPN tunnels. | Generator for Wireguard Netdev configurations in systemd-networkd, allowing routing policy adjustments for specific devices. |
| **Containerized Plugins** | `Docker` & `Docker Compose` | Running third-party applications in isolated environments. | Docker compose orchestration. The config engine pulls, starts, and mounts D-Bus sockets for these containers. |
| **Administration Web UI** | `Cockpit` | Provides the underlying web server, user authentication, and system bridge. | Cockpit package (HTML, CSS, Javascript) presenting the dashboard, configuration forms, and family device views. |
| **Backup & Restore** | Standard Linux tools (`tar`, `gzip`) | File compression and archival. | Python utilities to bundle the split config files and the state cache, exposing backup/restore actions over the D-Bus interface. |

---

## Detailed Tool Implementations

### 1. Network Layer (systemd-networkd & IWD)
To ensure reliable operation without high-level desktop-centric overhead, RoostOS uses **systemd-networkd** as its network manager.
*   **VLAN Subnets**: For guest networks and IoT isolation, `systemd-networkd` natively creates VLANs using `.netdev` files (defining the VLAN ID) and `.network` files (assigning it to physical bridges).
*   **MESH Wi-Fi**: **IWD** is a lightweight, modern Wi-Fi daemon that replaces `wpa_supplicant`. It has built-in support for WPA3, fast roaming, and 802.11s mesh networking.
*   *Custom code*: RoostOS reads the split configurations, translates the VLAN and SSID setups into networkd/IWD config files, and executes `networkctl reload` and `systemctl restart iwd`.

#### Dynamic Interface Mapping (x86 & ARM Portability)
Standard network interface names are unpredictable and change across platforms.
To make RoostOS configurations completely portable, `roostd` dynamically discovers network interfaces using `udevadm` and `/sys/class/net/`:
*   **Logical Mapping**: In `network.yaml`, interfaces can be targeted logically rather than by hardcoded name. The daemon matches interfaces using attributes:
    *   `match: mac: "00:11:22:33:44:55"`
    *   `match: driver: "iwlwifi"`
    *   `match: path: "pci-0000:03:00.0"`
*   **Logical Names**: The daemon maps matched hardware interfaces to logical names like `wan` and `lan1` in `systemd-networkd` config generations.

### 2. DHCP (Kea DHCP)
RoostOS replaces older DHCP servers with **ISC Kea**.
*   **D-Bus Hook**: Kea includes a hook library framework. We configure `libdhcp_run_script.so` to run a lightweight script (`/usr/local/bin/roost-dhcp-hook`) whenever a lease is committed or released.
*   *Custom code*: The Python daemon writes Kea configuration files detailing subnet pools and static reservations, then reloads Kea.

### 3. DNS (Plugin Decoupled)
DNS is fully decoupled from the core OS:
*   **Standard Interface**: The Roost Daemon does not call Technitium API directly. Instead, it emits calls on the D-Bus system bus interface `org.roostos.DNSResolver`.
*   **Technitium sidecar**: The default DNS plugin runs the official Technitium Docker container. Alongside it, a custom **RoostOS D-Bus Bridge** sidecar container runs inside the same network namespace.

### 4. Firewall (nftables Security Rules)
**nftables** provides clean syntax and native dynamic "sets".

#### A. Dynamic Sets with Timeouts
Instead of reloading the firewall whenever a device's time limit expires, `roostd` creates a set named `blocked_macs` in nftables:
```
table inet filter {
    set blocked_macs {
        type ether_addr
    }
    chain forward {
        type filter hook forward priority filter; policy accept;
        ether saddr @blocked_macs reject
    }
}
```

#### B. DNS Hijacking (Force Local DNS)
To prevent users from changing their client device settings (e.g. setting DNS to `8.8.8.8`) to bypass parental blocklists, `roostd` compiles nftables destination NAT (DNAT) rules:
```
table ip nat {
    chain prerouting {
        type filter hook prerouting priority dstnat; policy accept;
        ip saddr 192.168.1.0/24 tcp dport 53 dnat to 192.168.1.1:53
        ip saddr 192.168.1.0/24 udp dport 53 dnat to 192.168.1.1:53
    }
}
```
*Exceptions are dynamically generated to allow the DNS resolver container/host to make outbound DNS queries.*

#### C. Encrypted DNS Blocking (DoH / DoT)
To prevent clients from using DNS-over-TLS (DoT) or DNS-over-HTTPS (DoH) to bypass filters:
1.  **DoT Blocking**: Drop all outbound traffic to port `853` (TCP/UDP) at the firewall forward chain:
    ```
    tcp dport 853 reject
    udp dport 853 reject
    ```
2.  **DoH Blocking**: Technitium DNS includes built-in blocklists containing domains of known public DoH providers (e.g. `cloudflare-dns.com`). Additionally, `roostd` populates an nftables set `doh_server_ips` with known public DoH resolver IP addresses and blocks outbound forwarding requests to them on port 443.

### 5. Web UI (Cockpit)
**Cockpit** is standard on Ubuntu Server, provides zero-overhead system administration, and authenticates using Linux system users (PAM).
*   **D-Bus Bridge**: Cockpit's javascript library has a native D-Bus client. We define a custom Cockpit module (`/usr/share/cockpit/roostos/`) containing React or Vanilla JS code.
