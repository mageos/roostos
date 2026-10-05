# RoostOS Debian Package Architecture & Specification

RoostOS provides a unified, self-contained Debian (`.deb`) package for Debian and Ubuntu systems. To eliminate package fragmentation, dependency hell, and outdated system distribution packages, RoostOS bundles a self-contained Python 3.13 runtime and locked virtual environment into a single package: `roostos`.

Role-specific system dependencies (such as Kea DHCP, nftables, or Mosquitto) are provisioned on demand by the guided setup wizard (`roostos setup`).

---

## 1. Unified Package Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       roostos (Unified Debian Package)                      │
│                                                                             │
│  • Bundled Python 3.13 standalone runtime & locked virtualenv               │
│  • Universal CLI (/usr/bin/roostos)                                         │
│  • Node Agent & REST API (/usr/bin/roostos-node)                            │
│  • Central Controller Daemon (/usr/bin/roostos-engine)                      │
│  • TimeGuard Screen-Time Client (/usr/local/bin/roostos-timeguardd)         │
│  • Web Console SPA assets (/usr/share/roostos/web)                          │
│  • Systemd units (roostos-node, roostos-engine, roostos-timeguardd)         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                         roostos setup --role <role>
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
 ┌─────────────┐                ┌─────────────┐                ┌─────────────┐
 │   Gateway   │                │ Controller  │                │ Workstation │
 │   Router    │                │ Application │                │   Client    │
 ├─────────────┤                ├─────────────┤                ├─────────────┤
 │ • Kea DHCP  │                │ • Mosquitto │                │ • TimeGuard │
 │ • nftables  │                │ • roostos-  │                │   daemon    │
 │ • WireGuard │                │   engine    │                │ • SSSD (opt)│
 └─────────────┘                └─────────────┘                └─────────────┘
```

---

## 2. Package Specification

* **Binary Package Name**: `roostos`
* **Architecture**: `amd64`, `arm64`
* **Installed Files**:
  * `/usr/lib/roostos/runtime/` (Python 3.13 interpreter, stdlib, site-packages, and CLI entrypoint binaries)
  * `/usr/bin/roostos` (Universal root CLI)
  * `/usr/bin/roostos-node` (Local node agent and REST API service)
  * `/usr/bin/roostos-engine` (Central domain controller daemon)
  * `/usr/local/bin/roostos-timeguardd` (Workstation screen-time monitoring client)
  * `/usr/local/bin/roost-dhcp-hook` (Kea DHCP lease update hook)
  * `/usr/local/bin/roostos-workstation-join` / `roostos-workstation-enroll` (Domain enrollment helpers)
  * `/usr/local/bin/roostos-edge-setup` (VPS edge gateway provisioning helper)
  * `/usr/share/roostos/web/` (Web Console Single Page Application assets)
  * `/etc/dbus-1/system.d/org.roostos.conf` (DBus security policy)
  * `/etc/systemd/system/roostos-node.service` (Base node agent service)
  * `/etc/systemd/system/roostos-engine.service` (Controller service)
  * `/etc/systemd/system/roostos-timeguardd.service` (Client screen-time service)
* **Base Dependencies (`Depends`)**: `libc6 (>= 2.31)`
* **Recommended Packages (`Recommends`)**: `nftables`, `wireguard`
* **Suggested Packages (`Suggests`)**: `kea-dhcp4-server`, `mosquitto`
* **Transitional Compatibility (`Provides` / `Replaces`)**:
  * `roostos-runtime`, `roostos-cli`, `roostos-node`, `roostos-web`, `roostos-gateway`, `roostos-core`, `roostos-engine`, `roostos-workstation`, `roostos-timeguardd`, `roostos-edge-node`, `roostos-router`, `roostos-gateway-node`, `roostos-controller-node`

---

## 3. Dynamic Dependency Management

Instead of maintaining separate Debian packages for each hardware role, `roostos setup` detects and installs external system daemons dynamically via `apt`:

1. **Gateway Router (`--role gateway` or `--role standalone`)**:
   * Inspects host packages; installs `kea-dhcp4-server`, `nftables`, and `wireguard` if absent.
   * Generates `/etc/roostos/network.yaml` and `/etc/roostos/system.yaml`.
   * Enables `kea-dhcp4-server.service`, `nftables.service`, and `roostos-node.service`.

2. **Central Controller (`--role controller` or `--role standalone`)**:
   * Installs `mosquitto` message broker if absent.
   * Generates `/etc/roostos/nodes.yaml` and `/etc/roostos/system.yaml`.
   * Enables `mosquitto.service`, `roostos-engine.service`, and `roostos-node.service`.

3. **Client Workstation (`--role workstation`)**:
   * Connects to central controller; generates `/etc/roostos-timeguardd/config.json`.
   * Enables `roostos-timeguardd.service`.
   * Optionally installs `sssd`, `realmd`, and `adcli` if Active Directory/LDAP domain login is selected.

4. **Edge Gateway VPS (`--role edge_gateway`)**:
   * Installs `wireguard` and `nftables`.
   * Generates `/etc/roostos/network.yaml` with public ingress configuration.

---

## 4. Package Build Automation

The unified package is built via `scripts/build-all-debs.sh`:

```bash
# Build for host architecture
bash scripts/build-all-debs.sh

# Build for specific architecture
ARCH=amd64 bash scripts/build-all-debs.sh
ARCH=arm64 bash scripts/build-all-debs.sh

# Cross-compiling for ARM64 on an x86_64 host (automatic via Docker builder)
make deb ARCH=arm64
```
