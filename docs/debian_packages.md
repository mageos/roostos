# RoostOS Debian Package Architecture & Specification

RoostOS is packaged into modular, role-oriented Debian (`.deb`) packages for Debian/Ubuntu systems. This enables users to deploy an all-in-one router, separate management controllers from edge routing gateways, or install lightweight client daemons on workstations without unnecessary overhead.

---

## 1. Package Dependency Graph

```
                               ┌────────────────────────────────────────────────────────┐
                               │                 roostos (Root Package)                 │
                               │  • Unified CLI (/usr/bin/roostos)                      │
                               │  • Generic hardware inspector & mDNS discovery         │
                               │  • Guided Setup Wizard (roostos setup)                 │
                               │  • Minimal base deps: python3, iproute2, curl          │
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

### A. `roostos-cli` (Root Base Package)
The universal entry-point package for any machine running or interacting with RoostOS.
- **Binary Package Name**: `roostos-cli` (Provides/Replaces: `roostos`)
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/bin/roostos`
  - `/usr/lib/python3/dist-packages/roostos_cli/`
- **Dependencies (`Depends`)**: `python3`, `python3-click`, `python3-pydantic`, `python3-yaml`
- **Description**: Universal command-line interface, hardware inspector, and guided setup wizard for RoostOS.

---

### B. `roostos-node` (Node Agent & Local REST API)
Base infrastructure agent running on all server, gateway, and compute nodes.
- **Binary Package Name**: `roostos-node` (Provides/Replaces: `roostos-web`)
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/bin/roostos-node`
  - `/usr/lib/python3/dist-packages/roostos_web/`
  - `/usr/share/roostos/web/` (Web Console SPA assets)
  - `/etc/systemd/system/roostos-node.service`
- **Dependencies (`Depends`)**: `roostos-cli`, `roostos-sdk`, `roostos-engine`, `python3`, `python3-fastapi`, `python3-uvicorn`, `python3-pam`, `python3-jwt`
- **Description**: Local node agent and REST API service ensuring independent survivability and management.

---

### C. `roostos-gateway` (Home Router & LAN Gateway Stack)
Local routing, packet filtering, and DHCP address allocation module for physical on-premises routers.
- **Binary Package Name**: `roostos-gateway` (Provides/Replaces: `roostos-core`)
- **Architecture**: `amd64`, `arm64`
- **Installed Files**:
  - `/usr/local/bin/roost-dhcp-hook`
  - `/etc/dbus-1/system.d/org.roostos.conf`
- **Dependencies (`Depends`)**: `roostos-node`, `nftables`, `kea-dhcp4-server`, `wireguard`, `systemd`, `python3-paho-mqtt`
- **Description**: Home router stack configuring nftables firewall sets, Kea DHCP leases, WireGuard tunnels, and systemd-networkd for local physical networks.

---

### D. `roostos-engine` (Central Controller & Cluster Coordinator)
Central domain object registry, cluster coordinator, and application plugin host.
- **Binary Package Name**: `roostos-engine`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/lib/python3/dist-packages/roostos_engine/`
  - `/usr/bin/roostos-engine`
  - `/etc/systemd/system/roostos-engine.service`
- **Dependencies (`Depends`)**: `roostos-sdk`, `mosquitto`, `python3-paho-mqtt`, `python3-pydantic`, `python3-yaml`
- **Description**: Central configuration storage service, cluster sync coordinator, and domain object REST API.

---

### E. `roostos-workstation` (Unified Client Endpoint)
Screen time, family schedule limits, and workstation domain enrollment client.
- **Binary Package Name**: `roostos-workstation` (Provides/Replaces: `roostos-timeguardd`)
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/local/bin/roostos-timeguardd`
  - `/usr/local/bin/roostos-workstation-join`
  - `/usr/local/bin/roostos-workstation-enroll`
  - `/etc/systemd/system/roostos-timeguardd.service`
- **Dependencies (`Depends`)**: `roostos-cli`, `python3`, `python3-paho-mqtt`, `systemd`, `dbus`
- **Description**: Screen time monitoring, session locking, and domain enrollment client for managed workstations.

---

### F. `roostos-edge-node` (Cloud VPS Edge Gateway & Ingress Proxy)
Dedicated package for a public Debian/Ubuntu VPS to bypass Carrier-Grade NAT (CGNAT) and reverse proxy external traffic into the home network.
- **Binary Package Name**: `roostos-edge-node`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/local/bin/roostos-edge-setup`
- **Dependencies (`Depends`)**: `roostos-cli`, `roostos-node`, `wireguard`, `nftables`
- **Description**: Provisions a lightweight VPS edge ingress node with WireGuard tunnel termination, bootstrap enrollment API (`/api/edge/enroll`), automatic WAN firewall lockdown, and containerized Nginx reverse proxy.

---

### G. Meta-Packages & Compatibility Packages

* **`roostos-gateway-node`**: Installs a complete dedicated Home Gateway Router (`roostos-cli` + `roostos-gateway`).
* **`roostos-controller-node`**: Installs a complete dedicated Central Controller Server (`roostos-cli` + `roostos-engine`).
* **`roostos-router`**: Installs an all-in-one standalone router combining Gateway and Controller (`roostos-gateway` + `roostos-engine`).
* **`roostos-edge-node`**: Installs a dedicated VPS Edge Gateway & Ingress proxy (`roostos-cli` + `roostos-node` + `wireguard` + `nftables` + `/usr/local/bin/roostos-edge-setup`).
* **`roostos`**: Compatibility metapackage depending on `roostos-cli`.
* **`roostos-core`**: Compatibility transitional package depending on `roostos-gateway`.
* **`roostos-web`**: Compatibility transitional package depending on `roostos-node`.
* **`roostos-timeguardd`**: Compatibility transitional package depending on `roostos-workstation`.

---

## 3. Package Build Automation

The packages are compiled using standard `dpkg-deb` automation via `scripts/`:

```bash
# Builds all architecture-independent (.deb all) and multi-arch (.deb amd64 and arm64) packages
bash scripts/build-all-debs.sh

# Or via Makefile (defaults to ARCHITECTURES="amd64 arm64"):
make deb

# To compile for a specific architecture only:
ARCHITECTURES="arm64" make deb
# or
ARCH=arm64 bash scripts/build-all-debs.sh
```

Architecture-specific packages (such as `roostos-gateway` and transitional `roostos-core`) automatically generate artifacts for both `amd64` and `arm64` targets into `dist/debs/`. Uploading these deb packages to the APT repository inbound queue publishes both `binary-amd64` and `binary-arm64` distribution indices.
