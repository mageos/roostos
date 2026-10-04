# RoostOS Debian Package Architecture & Specification

RoostOS is packaged into modular, role-oriented Debian (`.deb`) packages for Debian/Ubuntu systems. To ensure that installed systems run the exact, tested Python library versions without relying on fragmented or outdated system distribution packages, RoostOS bundles a self-contained Python 3.13 runtime and locked virtual environment in `roostos-runtime`.

---

## 1. Package Dependency Graph

```
                               ┌────────────────────────────────────────────────────────┐
                               │             roostos-runtime (Base Runtime)             │
                               │  • Bundled Python 3.13 standalone runtime               │
                               │  • Pinned & locked dependencies from uv.lock           │
                               │  • Installed at /usr/lib/roostos/runtime               │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                               ┌───────────────────────────┴────────────────────────────┐
                               │                 roostos (Root Package)                 │
                               │  • Unified CLI (/usr/bin/roostos)                      │
                               │  • Generic hardware inspector & mDNS discovery         │
                               │  • Guided Setup Wizard (roostos setup)                 │
                               │  • Depends: roostos-runtime                            │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
        ┌──────────────────────────────────────────────────┼──────────────────────────────────────────────────┐
        │ Local Infrastructure                             │ Remote Cloud / VPS                               │ Client Endpoints
        ▼                                                  ▼                                                  ▼
 ┌─────────────┐                                    ┌─────────────────────┐                            ┌─────────────────────┐
 │roostos-node │                                    │  roostos-edge-node  │                            │ roostos-workstation │
 │ (Base Node) │                                    │ (VPS Edge Gateway)  │                            │  (Client Endpoint)  │
 └──────┬──────┘                                    ├─────────────────────┤                            ├─────────────────────┤
        │                                           │ • WireGuard tunnel  │                            │ • TimeGuard limits  │
   ┌────┴────────────────┐                          │ • Nginx ingress     │                            │ • Session hooks     │
   ▼                     ▼                          │ • Bootstrap API     │                            │ • SSSD / AD join    │
┌──────────────────┐  ┌──────────────────┐          │ • nftables lockdown │                            │ • Auto-inventory    │
│ roostos-gateway  │  │  roostos-engine  │          │ • CGNAT bypass      │                            └─────────────────────┘
│ (Home Gateway)   │  │   (Controller)   │          └─────────────────────┘
├──────────────────┤  ├──────────────────┤
│ • nftables rules │  │ • Single source  │
│ • Kea DHCP server│  │ • Cluster sync   │
│ • networkd gen   │  │ • MQTT broker    │
└──────────────────┘  └──────────────────┘
```

---

## 2. Package Specifications

### A. `roostos-runtime` (Standalone Python Runtime & Locked Venv)
Contains the self-contained Python 3.13 runtime and all project dependencies locked to `uv.lock`.
- **Binary Package Name**: `roostos-runtime`
- **Architecture**: `amd64`, `arm64`
- **Installed Files**:
  - `/usr/lib/roostos/runtime/` (Python 3.13 interpreter, stdlib, site-packages, and CLI entrypoint binaries)
- **Dependencies (`Depends`)**: `libc6 (>= 2.31)`
- **Description**: Self-contained runtime ensuring exact version parity across all Debian and Ubuntu releases.

---

### B. `roostos-cli` (Root Base Package)
The universal entry-point package for any machine running or interacting with RoostOS.
- **Binary Package Name**: `roostos-cli` (Provides/Replaces: `roostos`)
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/bin/roostos`
- **Dependencies (`Depends`)**: `roostos-runtime`
- **Description**: Universal command-line interface, hardware inspector, and guided setup wizard for RoostOS.

---

### C. `roostos-node` (Node Agent & Local REST API)
Base infrastructure agent running on all server, gateway, and compute nodes.
- **Binary Package Name**: `roostos-node` (Provides/Replaces: `roostos-web`)
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/bin/roostos-node`
  - `/usr/share/roostos/web/` (Web Console SPA assets)
  - `/etc/systemd/system/roostos-node.service`
- **Dependencies (`Depends`)**: `roostos-runtime`, `roostos-cli`
- **Description**: Local node agent and REST API service ensuring independent survivability and management.

---

### D. `roostos-gateway` (Home Router & LAN Gateway Stack)
Local routing, packet filtering, and DHCP address allocation module for physical on-premises routers.
- **Binary Package Name**: `roostos-gateway` (Provides/Replaces: `roostos-core`)
- **Architecture**: `amd64`, `arm64`
- **Installed Files**:
  - `/usr/local/bin/roost-dhcp-hook`
  - `/etc/dbus-1/system.d/org.roostos.conf`
- **Dependencies (`Depends`)**: `roostos-node`, `nftables`, `kea-dhcp4-server`, `wireguard`, `systemd`
- **Description**: Home router stack configuring nftables firewall sets, Kea DHCP leases, WireGuard tunnels, and systemd-networkd for local physical networks.

---

### E. `roostos-engine` (Central Controller & Cluster Coordinator)
Central domain object registry, cluster coordinator, and application plugin host.
- **Binary Package Name**: `roostos-engine`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/bin/roostos-engine`
  - `/usr/bin/roostd`
  - `/etc/systemd/system/roostos-engine.service`
- **Dependencies (`Depends`)**: `roostos-runtime`, `mosquitto`
- **Description**: Central configuration storage service, cluster sync coordinator, and domain object REST API.

---

### F. `roostos-workstation` (Unified Client Endpoint)
Screen time, family schedule limits, and workstation domain enrollment client.
- **Binary Package Name**: `roostos-workstation` (Provides/Replaces: `roostos-timeguardd`)
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/local/bin/roostos-timeguardd`
  - `/usr/local/bin/roostos-workstation-join`
  - `/usr/local/bin/roostos-workstation-enroll`
  - `/etc/systemd/system/roostos-timeguardd.service`
- **Dependencies (`Depends`)**: `roostos-runtime`, `systemd`, `dbus`
- **Description**: Screen time monitoring, session locking, and domain enrollment client for managed workstations.

---

### G. `roostos-edge-node` (Cloud VPS Edge Gateway & Ingress Proxy)
Dedicated package for a public Debian/Ubuntu VPS to bypass Carrier-Grade NAT (CGNAT) and reverse proxy external traffic into the home network.
- **Binary Package Name**: `roostos-edge-node`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/local/bin/roostos-edge-setup`
- **Dependencies (`Depends`)**: `roostos-cli`, `roostos-node`, `wireguard`, `nftables`
- **Description**: Provisions a lightweight VPS edge ingress node with WireGuard tunnel termination, bootstrap enrollment API, automatic WAN firewall lockdown, and containerized Nginx reverse proxy.

---

### H. Meta-Packages & Compatibility Packages

* **`roostos-gateway-node`**: Installs a complete dedicated Home Gateway Router (`roostos-cli` + `roostos-gateway`).
* **`roostos-controller-node`**: Installs a complete dedicated Central Controller Server (`roostos-cli` + `roostos-engine`).
* **`roostos-router`**: Installs an all-in-one standalone router combining Gateway and Controller (`roostos-gateway` + `roostos-engine`).
* **`roostos-edge-node`**: Installs a dedicated VPS Edge Gateway & Ingress proxy (`roostos-cli` + `roostos-node` + `wireguard` + `nftables`).
* **`roostos`**: Compatibility metapackage depending on `roostos-cli`.
* **`roostos-core`**: Compatibility transitional package depending on `roostos-gateway`.
* **`roostos-web`**: Compatibility transitional package depending on `roostos-node`.
* **`roostos-timeguardd`**: Compatibility transitional package depending on `roostos-workstation`.

---

## 3. Package Build Automation

The packages are compiled using standard `dpkg-deb` automation via `scripts/`:

```bash
# Builds all architecture-independent (.deb all) and multi-arch (.deb amd64) packages
bash scripts/build-all-debs.sh

# Or specifying architecture:
ARCH=amd64 bash scripts/build-all-debs.sh
```
