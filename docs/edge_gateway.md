# RoostOS Edge Gateway & CGNAT Bypass Guide

This guide details how to configure and deploy a **VPS Edge Gateway** to bypass Carrier-Grade NAT (CGNAT) and securely expose home network services using **WireGuard-First zero-exposure onboarding**.

---

## 1. Architecture Overview

Many residential internet service providers place home routers behind CGNAT or dynamic IP addresses without port forwarding. The RoostOS Edge Gateway solves this by establishing an encrypted WireGuard tunnel between a low-cost cloud VPS (with a static public IP) and your home RoostOS router.

```
       Internet Users
             │
             ▼ HTTPS (443) / HTTP (80)
   ┌───────────────────┐
   │  Cloud VPS Edge   │ (Public Static IPv4)
   │  Ingress Proxy    │ (UDP 51820 Only)
   └─────────┬─────────┘
             │  Encrypted WireGuard Tunnel
             │  (10.42.0.1 ➔ 10.42.0.2)
             ▼
   ┌───────────────────┐
   │  Home RoostOS     │ (Behind CGNAT / Firewalled)
   │  Router / Gateway │
   └─────────┬─────────┘
             │  Internal LAN Routing
             ▼
   Local Devices / Applications (e.g. 192.168.1.50:8123)
```

---

## 2. Security Model: Zero Web Exposure ("Stealth VPS")

Traditional VPN or proxy enrollment often exposes a REST API or setup web interface on the VPS public WAN IP (e.g. port 8000). This presents several security challenges:
* Exposure to automated port scanners, botnets, and brute-force attacks.
* Requiring self-signed TLS certificates or complex domain setup for IP addresses.
* Potential attack surface on the unhardened VPS before firewall rules are active.

### How RoostOS Solves This
RoostOS uses a **WireGuard-First bootstrap protocol**:
1. **No Public HTTP/S**: Port 8000 is never exposed on the public WAN of the VPS.
2. **Dark UDP Port 51820**: The VPS WAN only listens on WireGuard's UDP port 51820. Because WireGuard silently drops all unauthenticated packets, port scanners see closed ports.
3. **Cryptographic Pre-Allocation**: When you generate an invite on the VPS, the server pre-provisions a cryptographic WireGuard keypair and tunnel IP for the home router.
4. **Offline Transfer**: Credentials are exchanged via a compact token (`roost-edge-wg://`) or an exported JSON bundle file (`roost-edge.json`).
5. **Zero Public Web API Calls**: Once the home router imports the invite, the WireGuard tunnel comes up immediately. Any subsequent API communication runs exclusively inside the private tunnel (`10.42.0.0/24`).

---

## 3. Step-by-Step Setup Guide

### Step 1: Provision the VPS Edge Gateway
On your Debian or Ubuntu cloud VPS (e.g., AWS, Hetzner, DigitalOcean):

1. **Install RoostOS**:
   ```bash
   sudo dpkg -i roostos_0.1.4_amd64.deb
   ```

2. **Configure the Edge Gateway Role**:
   ```bash
   sudo roostos setup --role edge_gateway
   ```
   The setup wizard installs WireGuard, configures `systemd-networkd`, and designates the external network adapter as the WAN interface.

3. **Generate an Invitation**:
   If your VPS has multiple network interfaces, specify the public IP explicitly:
   ```bash
   # Display compact token in terminal:
   sudo roostos edge token --ip <VPS_PUBLIC_IP>

   # OR export to a secure bundle file:
   sudo roostos edge token --ip <VPS_PUBLIC_IP> --export roost-edge.json
   ```

   The generated invitation token looks like:
   ```text
   roost-edge-wg://eyJ2ZXJzaW9uIjoiMS4wIiwidHlwZSI6IndpcmVndWFyZF9pbnZpdGUiLC...
   ```

---

### Step 2: Connect from Your Home Router
On your home RoostOS router, connect to the VPS using either the Web UI or CLI.

#### Option A: Web Management Console
1. Navigate to the **Edge Gateway** tab in the RoostOS Web Console.
2. Click **+ Connect Edge Gateway**.
3. Either paste the `roost-edge-wg://...` token or upload `roost-edge.json`.
4. Click **Connect & Establish Tunnel**.

#### Option B: Terminal CLI
Run the `roostos edge connect` command:
```bash
# Using the token:
sudo roostos edge connect --token "roost-edge-wg://..."

# OR using the exported file:
sudo roostos edge connect --file roost-edge.json
```

---

### Step 3: Verify the Tunnel
Check the connection status on either node:

```bash
# Check RoostOS edge status:
sudo roostos edge status

# Inspect WireGuard interface:
sudo wg show wg-edge

# Test ping across tunnel:
ping -c 3 10.42.0.1
```

Once established, the home router is reachable by the VPS at `10.42.0.2`, and the VPS is reachable at `10.42.0.1`.

---

### Step 4: Join the Edge Gateway to the Cluster

Now that the private tunnel is active, join the VPS to the central RoostOS cluster so it can be managed centrally, receive configuration updates, and report telemetry.

#### Zero-Friction Interactive Join (Auto-Discovery)
On the VPS, simply run:
```bash
sudo roostos cluster join
```
1. **Auto-Discovery**: Probes for the controller across mDNS and the WireGuard tunnel (`10.42.0.2:8000`).
2. **Authentication**: Choose between:
   * **1) Admin Username & Password**: Authenticates against the controller and generates a session.
   * **2) Pre-shared Join Token**: Enter a token previously generated on the controller with `roostos cluster token`.
3. **mTLS Cryptographic Enrollment**: The controller issues an X.509 client certificate and delivers its Root CA. Certificates are automatically installed to `/etc/roostos/certs/`.

#### Single-Command Join (Non-Interactive)
If you already know the parameters, you can run the join in a single command:
```bash
# With username (prompts for password):
sudo roostos cluster join 10.42.0.2:8000 --username admin --role edge_gateway

# Or with a pre-shared token:
sudo roostos cluster join 10.42.0.2:8000 --token roost-a1b2c3d4 --role edge_gateway
```

Once joined, verify on the home controller:
```bash
sudo roostos cluster list
```

---

## 4. Ingress Reverse Proxy Configuration

Once the tunnel is active, you can route external domains hitting your VPS static IP directly to internal home network services.

### Adding Ingress Routes
In the Web Console (**Edge Gateway ➔ Ingress Reverse Proxy Routes**) or via API:
* **Public Domain**: `ha.yourdomain.com`
* **Target LAN Destination**: `192.168.1.10:8123`
* **Automated SSL/TLS**: Enabled (Let's Encrypt automated certificate issuance)

External traffic arriving at `https://ha.yourdomain.com` on the VPS is terminated with SSL and securely tunneled over WireGuard directly to your internal service.

---

## 5. Hardening & Port Lockdown

If legacy HTTP onboarding (`--legacy-http`) was used, WAN port 8000 can be locked down so the management API is only accessible over the encrypted WireGuard tunnel:

```bash
sudo roostos edge lockdown --wan eth0
```

This applies an `nftables` rule dropping incoming TCP traffic on port 8000 from the external WAN interface, ensuring administrative traffic only flows across `10.42.0.0/24`.

---

## 6. Troubleshooting

* **Handshake not completing**: Ensure UDP port 51820 is open in your cloud provider's firewall / security group (e.g. AWS Security Group or Hetzner Firewall).
* **Multi-homed VPS**: If the VPS has both an internal VPC IP and a public elastic IP, ensure you supply the public IP to `roostos edge token --ip <PUBLIC_IP>`.
* **Interface status**: Run `networkctl status wg-edge` to inspect `systemd-networkd` link state.
