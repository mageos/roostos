# RoostOS

RoostOS is a free and open-source operating system built on the foundation of Ubuntu Server. It is a family-oriented router and firewall distribution focused on security, usability, and ease of management. 

All settings are declared in a strict split YAML configuration layout under `/etc/roostos/`, enabling precise terminal-based management and clean version control. A web-based interface built on top of Cockpit provides a secure, intuitive administration panel for the entire household.

---

## Key Features

*   **Rock-Solid Foundation**: Built on Ubuntu Server LTS (64-bit only).
*   **Decoupled DNS Engine**: DNS is isolated as a containerized plugin (supporting Technitium DNS, Pi-hole, or AdGuard Home) integrated via a standard D-Bus API (`org.roostos.DNSResolver`).
*   **High-Performance DHCP**: Uses **Kea DHCP** for address allocation, supporting asynchronous D-Bus event hooks for instant discovery.
*   **Modern Wi-Fi & Mesh**: Native support for Access Point configuration and 802.11s Mesh networks utilizing **IWD** (bypassing Netplan/wpa_supplicant conflicts).
*   **High-Performance Firewall**: Employs **nftables** for routing, NAT, port forwarding, and tag-based network isolation.
*   **Virtual Private Networks**: Out-of-the-box support for **Wireguard** client and server tunnel configurations.
*   **Parental Controls & Device Management**: Dynamic, MAC-address-based schedule rules, bedtime windows, daily accumulated screen time allowances, and temporary bypasses.
*   **Extensible Architecture**: Support for isolated, containerized plugins (running in Docker) that can run multiple sidecar containers, communicating securely with the host via D-Bus and a dedicated Python SDK.
*   **Split Configuration File Layout**:
    *   `system.yaml`: Identity, logins, Cockpit roles (Admin, Parent, Member).
    *   `network.yaml`: Interfaces, bridges, VLANs, SSIDs, and mesh settings.
    *   `devices.yaml`: People, locations, and registered MAC devices.
    *   `schedules.yaml`: Firewall schedules, bedtime windows, and usage limits.
    *   `plugins.yaml`: Installed plugin metadata and Docker settings.

---

## Technical Documentation

Before modifying the system, review the architectural blueprints and configurations:

*   **[Architecture Overview](file:///home/matt/source/github/mageos/roostos/docs/architecture.md)**: Details the layer-cake design, system components, split-file configuration layer, D-Bus system bus IPC, and system change lifecycles.
*   **[Features & Tools Mapping](file:///home/matt/source/github/mageos/roostos/docs/features_and_tools.md)**: Explains how system capabilities map to underlying Linux binaries (Kea, nftables, networkd, IWD) and outlines what custom code we build.
*   **[Configuration Schema](file:///home/matt/source/github/mageos/roostos/docs/config_schema.md)**: Documents the split configuration files under `/etc/roostos/`, including shared Domain Objects (Devices, Persons, Locations) and sidecar plugin settings.
*   **[Device Management & State Engine](file:///home/matt/source/github/mageos/roostos/docs/device_management.md)**: Explains the real-time DHCP lease discovery pipeline, the transient SQLite cache schema, and how nftables dynamic sets enforce bedtime schedules and daily time limits.
*   **[Extensibility & Plugins Guide](file:///home/matt/source/github/mageos/roostos/docs/extensibility.md)**: Details how to build and package third-party extensions as Docker containers, the `org.roostos.DNSResolver` D-Bus API, sidecar network namespace sharing, and how to use the `roostos-sdk`.

---

## Core System Concepts

### Device Management & Parental Controls
As a family-oriented network router/firewall, Device Management is a core feature. It allows you to see all devices on your network, map them to rooms or people, and create firewall and DNS-based filtering rules for tags or specific devices. In addition to static rules, you can create time-based schedules that block or restrict access at certain times of the day or days of the week. The web UI also provides simple ways to grant temporary access bypasses (e.g. "+30 minutes"). Each member of the family can have their own account, with access controls restricting what actions they can perform.

### Whole-Network VPN
If you want to route all network traffic (or traffic only from specific devices/tags) through a secure VPN tunnel, RoostOS makes it easy to configure Wireguard endpoints and routing policies directly from the Web UI or YAML.

### Network Isolation
You can create isolated subnets and VLANs for specific tags. For example, you can assign all smart home sensors to an IoT VLAN that is blocked from accessing the internet or talking to devices on the main LAN. Similarly, you can create a Guest network that allows internet access but isolates guests from the rest of the household devices.

---

## Building RoostOS Images

We use the **`debos`** tool to bootstrap, configure, and package RoostOS system images.

### 1. Build using Docker (Recommended)
Running `debos` in Docker avoids installing dependencies locally (like `systemd-nspawn`, `qemu-user-static`, and `debootstrap` tools):

*   **Build the x86_64 (amd64) bootable ISO**:
    ```bash
    docker run --rm --interactive --tty --device /dev/kvm --privileged \
      -v $(pwd):/workspace \
      -w /workspace \
      godebos/debos roostos-debos/roostos-amd64.yaml
    ```

*   **Build the ARM64 (arm64) flashable SD card image**:
    ```bash
    docker run --rm --interactive --tty --device /dev/kvm --privileged \
      -v $(pwd):/workspace \
      -w /workspace \
      godebos/debos roostos-debos/roostos-arm64.yaml
    ```

### 2. Build Natively
If you have `debos` installed on your host system:

*   **Build amd64 ISO**:
    ```bash
    sudo debos roostos-debos/roostos-amd64.yaml
    ```
*   **Build arm64 Image**:
    ```bash
    sudo debos roostos-debos/roostos-arm64.yaml
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

If you are deploying RoostOS to a new router device (or want to re-configure interface bindings at any time), you can run the guided setup wizard. This python utility prompts you to configure:
* The WAN (Internet) interface (DHCP or static IP parameters).
* IPv6 settings toggle.
* One or more LAN interface bindings.
* The LAN network scope (e.g. `192.168.1.0/24`) and router bridge IP.
* The Kea DHCP server range.
* Upstream DNS forwarders.
* Live diagnostic validations (ping checks, operstate verification, and DNS resolution).

### Running the Wizard

* **On a live RoostOS system (installed globally)**:
  ```bash
  sudo roostos-setup
  ```
* **In the local development environment (dry-run / custom folder)**:
  ```bash
  .venv/bin/roostos-setup --dir ./dev_root/etc/roostos
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