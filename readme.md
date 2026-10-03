# RoostOS

As a software engineer, father and technology enthusiast, I have been consistently frustrated with the difficulty of finding
open source, easy-to-use, family focused solutions for easily managing my home network.  While there are a number of great products out there on their own, they do not integrate well

RoostOS is a free and open-source operating system built on the foundation of Ubuntu Server. It is a family-oriented router and firewall distribution focused on security, usability, and ease of management. 

All settings are declared in a strict split YAML configuration layout under `/etc/roostos/`, enabling precise terminal-based management and clean version control. A web-based management interface (`roostos-web`) provides a secure, intuitive administration panel for the entire household.

---

## Key Features

*   **Rock-Solid Foundation**: Built on Ubuntu Server LTS (64-bit only).
*   **Three-Service Distributed Architecture**: Clear decoupling between central domain object storage (`roostos-engine`), node system management (`roostos-core`), and web administration (`roostos-web`).
*   **Decoupled DNS Engine**: DNS is isolated as a containerized plugin (supporting Technitium DNS, Pi-hole, or AdGuard Home) integrated via a standard D-Bus API (`org.roostos.DNSResolver`) and bridged to MQTT.
*   **High-Performance DHCP**: Uses **Kea DHCP** for address allocation, supporting asynchronous D-Bus and MQTT event hooks for instant discovery.
*   **Modern Wi-Fi & Mesh**: Native support for Access Point configuration and 802.11s Mesh networks utilizing **IWD** (bypassing Netplan/wpa_supplicant conflicts).
*   **High-Performance Firewall**: Employs **nftables** with dynamic sets (`quarantined`, `schedule_blocked`, `admin_blocked`) for routing, NAT, port forwarding, and tag-based network isolation.
*   **Virtual Private Networks**: Out-of-the-box support for **Wireguard** client and server tunnel configurations.
*   **Parental Controls & Family Controls**: Dynamic MAC-address-based schedule rules, bedtime windows, daily accumulated screen time allowances, temporary bypasses, and cross-device session tracking (`roostos-timeguardd`).
*   **Extensible Architecture**: Support for isolated, containerized plugins (core services and application workloads) with mTLS certificate security, scope consent, dynamic Web Component UI extensions, and multi-architecture OCI image registry distribution.
*   **Split Configuration File Layout**:
    *   `system.yaml`: Host identity, logins, HTTPS ACME, unattended update windows, and unregistered device policy.
    *   `network.yaml`: Interfaces, bridges, subnets, VLANs, gateways, QoS, and mesh settings.
    *   `devices.yaml`: People, buildings, rooms, registered MAC devices, static IP reservations, and UPnP trust.
    *   `schedules.yaml`: Time-window access rules and daily screen time allowance limits.
    *   `firewall.yaml`: Static input rules, port forwards, and custom firewall policies.
    *   `plugins.yaml`: Installed plugin metadata, requested scopes, containers, and settings overrides.

---

## Technical Documentation

Before modifying the system, review the architectural blueprints and configurations:

*   **[Architecture Overview](file:///home/matt/source/github/mageos/roostos/docs/architecture.md)**: Details the layer-cake design, system components, split-file configuration layer, D-Bus system bus IPC, and system change lifecycles.
*   **[Features & Tools Mapping](file:///home/matt/source/github/mageos/roostos/docs/features_and_tools.md)**: Explains how system capabilities map to underlying Linux binaries (Kea, nftables, networkd, IWD) and outlines what custom code we build.
*   **[Configuration Schema](file:///home/matt/source/github/mageos/roostos/docs/config_schema.md)**: Documents the split configuration files under `/etc/roostos/`, including shared Domain Objects (Devices, Persons, Locations) and sidecar plugin settings.
*   **[Device Management & State Engine](file:///home/matt/source/github/mageos/roostos/docs/device_management.md)**: Explains the real-time DHCP lease discovery pipeline, the transient SQLite cache schema, and how nftables dynamic sets enforce bedtime schedules and daily time limits.
*   **[Extensibility & Plugins Guide](file:///home/matt/source/github/mageos/roostos/docs/extensibility.md)**: Details how to build and package third-party extensions as Docker containers, the `org.roostos.DNSResolver` D-Bus API, sidecar network namespace sharing, and how to use the `roostos-sdk`.
*   **[Multi-Node Test Harness](file:///home/matt/source/github/mageos/roostos/docs/test_harness.md)**: Explains the containerized multi-node virtual network environment, real socket automation testing with pytest, manual Web UI testing mode, and deployment scenarios.

---

## Core System Concepts

### Device Management & Parental Controls
As a family-oriented network router/firewall, Device Management is a core feature. It allows you to see all devices on your network, map them to rooms or people, and create firewall and DNS-based filtering rules for tags or specific devices. In addition to static rules, you can create time-based schedules that block or restrict access at certain times of the day or days of the week. The web UI also provides simple ways to grant temporary access bypasses (e.g. "+30 minutes"). Each member of the family can have their own account, with access controls restricting what actions they can perform.

### Whole-Network VPN
If you want to route all network traffic (or traffic only from specific devices/tags) through a secure VPN tunnel, RoostOS makes it easy to configure Wireguard endpoints and routing policies directly from the Web UI or YAML.

### Network Isolation
You can create isolated subnets and VLANs for specific tags. For example, you can assign all smart home sensors to an IoT VLAN that is blocked from accessing the internet or talking to devices on the main LAN. Similarly, you can create a Guest network that allows internet access but isolates guests from the rest of the household devices.

---

## Installation via Debian Packages (`.deb`)

RoostOS is packaged as modular, role-oriented `.deb` packages for Debian and Ubuntu Server LTS (both `amd64` and `arm64`). This enables installing an all-in-one router, separating routing gateways from compute application nodes, or provisioning VPS edge proxies.

### 1. Compile Packages from Source
To compile all architecture-independent and architecture-specific packages:
```bash
make deb
```
This generates all `.deb` artifacts in `dist/debs/`:
* `roostos-router_*.deb`: Complete standalone all-in-one router (Gateway + Controller).
* `roostos-gateway-node_*.deb`: Dedicated Edge Gateway Router (packet filtering, Kea DHCP, Wi-Fi mesh).
* `roostos-controller-node_*.deb`: Central Controller & Application Server (domain registry, MQTT broker, container workloads).
* `roostos-workstation_*.deb`: Client Workstation agent (screen time limits, PAM session locking).
* `roostos-edge-node_*.deb`: Cloud VPS Edge Gateway (CGNAT bypass & reverse-proxy ingress).

### 2. Install on a Target Node
Copy the appropriate `.deb` package to your target Debian/Ubuntu machine and install via `apt`:

* **All-in-One Home Router**:
  ```bash
  sudo apt update && sudo apt install -y ./dist/debs/roostos-router_*.deb
  ```
* **Dedicated Gateway Node**:
  ```bash
  sudo apt update && sudo apt install -y ./dist/debs/roostos-gateway-node_*.deb
  ```
* **Dedicated Controller / App Server**:
  ```bash
  sudo apt update && sudo apt install -y ./dist/debs/roostos-controller-node_*.deb
  ```

---


## Local Development & Testing Sandbox

To enable rapid development and iteration without affecting your host operating system or requiring root permissions, RoostOS includes a fully containerized/isolated developer sandbox.

The sandbox spawns an isolated private D-Bus session, configures target directory variables (`ROOSTOS_SYSTEMD_NETWORK_DIR`, `ROOSTOS_KEA_CONF_DIR`, etc.) to write locally inside `./dev_root`, seeds default mock configurations, and launches the core daemon and the FastAPI web console.

### Running the Sandbox

Run the orchestration script:
```bash
./scripts/run_dev.py
```

Once running:
* **Web UI Access**: Open `http://localhost:8000` in your web browser. 
* **Admin Login**: You can log in using `admin` (password: `password`). To log in with your local host user, add your username to [dev_root/etc/roostos/system.yaml](file:///home/matt/source/github/mageos/roostos/dev_root/etc/roostos/system.yaml) under the `users` list with `role: admin`.
* **Output inspection**: All generated system config files (systemd-networkd network files, Kea DHCP settings, and nftables rulesets) will be written to `./dev_root/` for validation.
* **Stop Sandbox**: Press `Ctrl+C` in your terminal to safely tear down all background processes and D-Bus sockets.

---

## Initial Guided Setup Wizard

RoostOS includes a universal hardware-aware setup wizard (`roostos setup`) that inspects physical interfaces, detects form factors, and guides configuration:
* The WAN (Internet) interface (DHCP or static IP parameters).
* IPv6 settings toggle.
* One or more LAN interface bindings and bridge IP (e.g. `192.168.1.1/24`).
* Kea DHCP server range and dynamic lease scope.
* Upstream DNS forwarders.
* Live diagnostic validations (ping checks, operstate verification, and DNS resolution).

### Running the Wizard

* **On a live RoostOS system (installed globally)**:
  ```bash
  sudo roostos setup
  ```
* **In the local development environment (dry-run / custom folder)**:
  ```bash
  .venv/bin/roostos setup --config-dir ./dev_root/etc/roostos
  ```

---

## Running Unit & Integration Tests

We enforce comprehensive testing across both the Python engine services (using `pytest`) and the JavaScript Web UI console (using `jest` in a simulated JSDOM environment).

### Run All Tests
To run both backend and frontend tests under a single command:
```bash
make test
```

### Run Frontend JavaScript Tests
```bash
make test-ui
```

### Install UI Test Dependencies
If testing for the first time or updating dependencies:
```bash
make install-ui-deps
```