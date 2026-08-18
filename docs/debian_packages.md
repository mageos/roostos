# RoostOS Debian Package Architecture & Specification

RoostOS is packaged into modular Debian (`.deb`) packages for Debian/Ubuntu systems. This enables users to deploy an all-in-one router, separate management services from execution daemons, or install lightweight client daemons on workstations without unnecessary overhead.

---

## 1. Package Dependency Graph

```
                               ┌────────────────────────────────┐
                               │   roostos-router (Meta-Pkg)    │
                               └───────────────┬────────────────┘
                                               │ (Depends)
            ┌──────────────────────────────────┼──────────────────────────────────┐
            ▼                                  ▼                                  ▼
┌───────────────────────┐          ┌───────────────────────┐          ┌───────────────────────┐
│    roostos-engine     │          │     roostos-core      │          │      roostos-web      │
│ (Config REST & MQTT)  │          │  (Local Node Daemon)  │          │    (Web Console SPA)  │
└───────────┬───────────┘          └───────────┬───────────┘          └───────────┬───────────┘
            │ (Depends)                        │ (Depends)                        │ (Depends)
            └──────────────────────────────────┼──────────────────────────────────┘
                                               ▼
                                   ┌───────────────────────┐
                                   │      roostos-sdk      │
                                   │     (Python SDK)      │
                                   └───────────────────────┘

                                   ┌───────────────────────┐
                                   │  roostos-timeguardd   │  (Standalone Client Pkg)
                                   └───────────────────────┘
```

---

## 2. Package Specifications

### A. `roostos-sdk`
Common Python library facilitating D-Bus and MQTT communication across services and sidecars.
- **Binary Package Name**: `roostos-sdk`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/lib/python3/dist-packages/roostos_sdk/`
- **Dependencies (`Depends`)**: `python3`, `python3-dbus-next`
- **Description**: Common Python SDK library for RoostOS services and plugin sidecars.

---

### B. `roostos-engine`
The central domain object, REST API, and configuration storage service (`/etc/roostos/`).
- **Binary Package Name**: `roostos-engine`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/lib/python3/dist-packages/roostos_engine/`
  - `/usr/bin/roostos-engine`
  - `/etc/systemd/system/roostos-engine.service`
  - `/etc/roostos/system.yaml` (default template)
  - `/etc/roostos/network.yaml` (default template)
  - `/etc/roostos/devices.yaml` (default template)
  - `/etc/roostos/schedules.yaml` (default template)
  - `/etc/roostos/firewall.yaml` (default template)
  - `/etc/roostos/plugins.yaml` (default template)
- **Dependencies (`Depends`)**: `python3`, `roostos-sdk`, `mosquitto` | `mqtt-broker`, `python3-pydantic`, `python3-fastapi`, `python3-jwt`, `python3-pyyaml`
- **Description**: Central configuration storage service and domain object REST API for RoostOS.

---

### C. `roostos-core`
Local router management daemon executing system-level actions (nftables, networkd, Kea DHCP, IWD).
- **Binary Package Name**: `roostos-core`
- **Architecture**: `amd64`, `arm64`
- **Installed Files**:
  - `/usr/bin/roostos-core`
  - `/usr/local/bin/roost-dhcp-hook`
  - `/etc/systemd/system/roostos-core.service`
  - `/etc/dbus-1/system.d/org.roostos.conf`
- **Dependencies (`Depends`)**: `python3`, `roostos-sdk`, `systemd`, `dbus`, `kea-dhcp4-server`, `nftables`, `iwd`, `ppp`, `pppoe`, `mdns-reflector`, `python3-paho-mqtt`
- **Description**: Local node execution daemon applying firewall rules, DHCP, and network configs for RoostOS.

---

### D. `roostos-web`
Web administration console serving the single-page application (SPA).
- **Binary Package Name**: `roostos-web`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/lib/python3/dist-packages/roostos_web/`
  - `/usr/share/roostos/web/` (HTML, CSS, JS SPA assets)
  - `/etc/systemd/system/roostos-web.service`
- **Dependencies (`Depends`)**: `python3`, `roostos-engine` | `roostos-sdk`, `python3-fastapi`, `python3-pam`, `python3-jwt`
- **Description**: Web administration panel and single-page management application for RoostOS.

---

### E. `roostos-timeguardd`
Family Controls screen time monitoring daemon for client workstations.
- **Binary Package Name**: `roostos-timeguardd`
- **Architecture**: `all`
- **Installed Files**:
  - `/usr/local/bin/roostos-timeguardd`
  - `/usr/local/bin/roostos-timeguard-setup`
  - `/etc/systemd/system/roostos-timeguardd.service`
- **Dependencies (`Depends`)**: `python3`, `python3-paho-mqtt`, `systemd`, `dbus`
- **Description**: Screen time monitoring daemon for RoostOS client workstations.

---

### F. `roostos-router` (Meta-Package)
All-in-one meta-package for deploying a complete standalone RoostOS router.
- **Binary Package Name**: `roostos-router`
- **Architecture**: `all`
- **Dependencies (`Depends`)**: `roostos-sdk`, `roostos-engine`, `roostos-core`, `roostos-web`
- **Description**: Standalone all-in-one RoostOS router distribution meta-package.

---

## 3. Package Build Automation

The packages are compiled using standard `dpkg-deb` automation scripts under `scripts/`:

```bash
# Build all Debian packages in order:
bash scripts/build-all-debs.sh
```

Or via `Makefile`:
```bash
make deb
```
