// RoostOS Mock Data Engine for UI Exploration & Prototyping
import { initialBlockedRequests } from './blocked-requests-data.js';

export const initialData = {
    system: {
        hostname: "roost-home-router",
        version: "0.2.0-preview",
        uptime: "6 days, 14 hours, 22 mins",
        wanIp: "100.64.14.82 (CGNAT Carrier IP)",
        gatewayIp: "192.168.1.1",
        ispName: "Fiber Gigabit (Carrier-Grade NAT)",
        pingMs: 11,
        downloadMbps: 942,
        uploadMbps: 884,
        cpuPercent: 14.8,
        ramPercent: 42.5,
        tempC: 46.2,
        unassignedDeviceAlert: true
    },
    // Cloud VPS Edge Gateway for CGNAT Bypass
    edgeGateway: {
        enabled: true,
        cgnatDetected: true,
        cgnatIspIp: "100.64.14.82",
        vpsPublicIp: "198.51.100.89",
        vpsHostname: "edge-us-east.roostos.net",
        tunnelSubnet: "10.42.0.0/24",
        localTunnelIp: "10.42.0.2",
        vpsTunnelIp: "10.42.0.1",
        tunnelPort: 51820,
        tunnelStatus: "Connected & Healthy (12ms latency)",
        handshake: "6s ago",
        rxBytes: "48.2 GB",
        txBytes: "12.6 GB",
        token: "roost-edge-wg://eyJ2ZXJzaW9uIjoiMS4wIiwidHlwZSI6IndpcmVndWFyZF9pbnZpdGUiLCJ2cHMiOiIxOTguNTEuMTAwLjg5In0=",
        ingressRules: [
            { id: "ing-1", domain: "ha.smithfamily.net", target: "192.168.1.50:8123", service: "Home Assistant", ssl: "Active (Let's Encrypt)", expires: "68 days", enabled: true },
            { id: "ing-2", domain: "cloud.smithfamily.net", target: "192.168.1.15:443", service: "Nextcloud Family Storage", ssl: "Active (Let's Encrypt)", expires: "68 days", enabled: true },
            { id: "ing-3", domain: "media.smithfamily.net", target: "192.168.1.20:32400", service: "Plex Media Server", ssl: "Active (Let's Encrypt)", expires: "42 days", enabled: true }
        ]
    },
    people: [
        { id: "dad", name: "Dad", role: "admin", color: "#3b82f6", avatar: "👨‍💻", screentimeLimit: 0, screentimeUsed: 180, bedtimeStart: "00:00", bedtimeEnd: "06:00", bedtimeActive: false, filterLevel: "Standard", deviceCount: 2 },
        { id: "mom", name: "Mom", role: "parent", color: "#ec4899", avatar: "👩‍🔬", screentimeLimit: 0, screentimeUsed: 140, bedtimeStart: "23:30", bedtimeEnd: "06:00", bedtimeActive: false, filterLevel: "Standard", deviceCount: 2 },
        { id: "alice", name: "Alice (11)", role: "kid", color: "#10b981", avatar: "👧", screentimeLimit: 120, screentimeUsed: 95, bedtimeStart: "20:30", bedtimeEnd: "06:30", bedtimeActive: false, filterLevel: "SafeSearch + AdBlock", deviceCount: 1 },
        { id: "bob", name: "Bob (8)", role: "kid", color: "#f59e0b", avatar: "👦", screentimeLimit: 90, screentimeUsed: 90, bedtimeStart: "20:00", bedtimeEnd: "06:30", bedtimeActive: true, filterLevel: "Strict Kids", deviceCount: 1 }
    ],
    devices: [
        { mac: "1a:2b:3c:4d:5e:6f", name: "Dad's Phone (iPhone 15)", owner: "dad", location: "Living Room", ip: "192.168.1.101", staticIp: "192.168.1.101", tags: ["personal", "mobile"], zone: "lan", status: "online", signal: -48, rxMbps: 4.2, txMbps: 0.8, icon: "📱", vendor: "Apple" },
        { mac: "2a:3b:4c:5d:6e:7f", name: "Dad's ThinkPad X1", owner: "dad", location: "Office", ip: "192.168.1.102", staticIp: "", tags: ["work", "laptop"], zone: "lan", status: "online", signal: -52, rxMbps: 18.5, txMbps: 2.1, icon: "💻", vendor: "Lenovo" },
        { mac: "3a:4b:5c:6d:7e:8f", name: "Mom's MacBook Pro 16", owner: "mom", location: "Office", ip: "192.168.1.105", staticIp: "192.168.1.105", tags: ["work", "laptop"], zone: "lan", status: "online", signal: -45, rxMbps: 35.1, txMbps: 4.6, icon: "💻", vendor: "Apple" },
        { mac: "4a:5b:6c:7d:8e:9f", name: "Mom's Phone (Pixel 8)", owner: "mom", location: "Kitchen", ip: "192.168.1.106", staticIp: "", tags: ["personal", "mobile"], zone: "lan", status: "online", signal: -58, rxMbps: 1.1, txMbps: 0.2, icon: "📱", vendor: "Google" },
        { mac: "5a:6b:7c:8d:9e:0f", name: "Alice's iPad 10", owner: "alice", location: "Kids Bedroom", ip: "192.168.1.150", staticIp: "192.168.1.150", tags: ["kids", "tablet"], zone: "lan", status: "online", signal: -62, rxMbps: 8.4, txMbps: 0.4, icon: "📲", vendor: "Apple" },
        { mac: "6a:7b:8c:9d:0e:1f", name: "Bob's Nintendo Switch", owner: "bob", location: "Living Room", ip: "192.168.1.151", staticIp: "", tags: ["kids", "gaming"], zone: "lan", status: "blocked", signal: -65, rxMbps: 0.0, txMbps: 0.0, icon: "🎮", vendor: "Nintendo" },
        { mac: "7a:8b:9c:0d:1e:2f", name: "Living Room Apple TV 4K", owner: "household", location: "Living Room", ip: "192.168.1.20", staticIp: "192.168.1.20", tags: ["entertainment", "streaming"], zone: "lan", status: "online", signal: -40, rxMbps: 42.0, txMbps: 1.2, icon: "📺", vendor: "Apple" },
        { mac: "8a:9b:0c:1d:2e:3f", name: "Smart Ecobee Thermostat", owner: "household", location: "Hallway", ip: "192.168.20.10", staticIp: "192.168.20.10", tags: ["iot"], zone: "iot", status: "online", signal: -70, rxMbps: 0.05, txMbps: 0.02, icon: "🌡️", vendor: "Ecobee" },
        { mac: "9a:0b:1c:2d:3e:4f", name: "Kitchen Smart Fridge", owner: "household", location: "Kitchen", ip: "192.168.20.11", staticIp: "", tags: ["iot"], zone: "iot", status: "online", signal: -66, rxMbps: 0.1, txMbps: 0.05, icon: "🧊", vendor: "Samsung" },
        { mac: "aa:bb:cc:dd:ee:01", name: "Philips Hue Smart Bridge", owner: "household", location: "Office", ip: "192.168.20.12", staticIp: "192.168.20.12", tags: ["iot"], zone: "iot", status: "online", signal: -44, rxMbps: 0.08, txMbps: 0.04, icon: "💡", vendor: "Signify" },
        { mac: "bb:cc:dd:ee:ff:02", name: "Guest iPhone 13", owner: "guest", location: "Living Room", ip: "192.168.10.45", staticIp: "", tags: ["guest"], zone: "guest", status: "online", signal: -55, rxMbps: 5.2, txMbps: 0.6, icon: "📱", vendor: "Apple" },
        { mac: "cc:dd:ee:ff:00:99", name: "Unknown Samsung Galaxy S23", owner: "", location: "Front Yard", ip: "192.168.1.188", staticIp: "", tags: ["new", "unregistered"], zone: "lan", status: "quarantined", signal: -78, rxMbps: 0.0, txMbps: 0.0, icon: "❓", vendor: "Samsung" }
    ],
    rooms: [
        { id: "living_room", name: "Living Room", deviceCount: 3 },
        { id: "office", name: "Home Office", deviceCount: 3 },
        { id: "kitchen", name: "Kitchen", deviceCount: 2 },
        { id: "kids_bedroom", name: "Kids Bedroom", deviceCount: 1 },
        { id: "hallway", name: "Hallway", deviceCount: 1 }
    ],
    wifiNetworks: [
        { ssid: "RoostHome", band: "Dual-Band (2.4/5GHz)", security: "WPA3-Personal", clients: 9, channel: "36 (80MHz)", status: "Active", isolate: false },
        { ssid: "RoostHome-Guest", band: "5GHz", security: "WPA2-Personal", clients: 1, channel: "149 (80MHz)", status: "Active", isolate: true, qr: "WIFI:S:RoostHome-Guest;T:WPA;P:GuestWelcome2026;;" },
        { ssid: "RoostHome-IoT", band: "2.4GHz", security: "WPA2-Personal", clients: 3, channel: "6 (20MHz)", status: "Active", isolate: true, vlan: 20 }
    ],
    protection: {
        adBlocking: { enabled: true, blockedToday: 18432, blocklistPercent: 24.3, queriesToday: 75890 },
        safeSearch: { enabled: true, forcedForKids: true },
        malwareProtection: { enabled: true, threatsBlocked: 4 },
        vpnTunnel: { enabled: false, name: "WireGuard - NordVPN Swiss Gateway", endpoint: "ch45.nordvpn.com:51820", handshake: "Never" },
        blockedRequests: initialBlockedRequests
    },
    // Distributed Multi-Node Cluster Fleet
    cluster: {
        activeNodeFilter: "all",
        nodes: [
            {
                id: "roost-gateway-01",
                hostname: "roost-gateway-01",
                role: "Edge Gateway Router",
                ip: "192.168.1.1",
                status: "Master",
                model: "Protectli Vault 4-Port",
                cpu: 14.8,
                ram: "42% (1.7 GB)",
                temp: "46°C",
                uptime: "6d 14h",
                interfaces: [
                    { name: "eth0", role: "WAN (CGNAT)", speed: "1000 Mbps Full", ip: "100.64.14.82/24", gateway: "100.64.14.1", rxBytes: "14.2 GB", txBytes: "3.8 GB", status: "UP", mtu: 1500 },
                    { name: "eth1", role: "LAN Trunk", speed: "1000 Mbps Full", ip: "-", gateway: "-", rxBytes: "8.5 GB", txBytes: "12.1 GB", status: "UP", mtu: 1500 },
                    { name: "eth2", role: "LAN Port", speed: "1000 Mbps Full", ip: "-", gateway: "-", rxBytes: "2.1 GB", txBytes: "4.3 GB", status: "UP", mtu: 1500 },
                    { name: "wlan0", role: "Access Point", speed: "Wi-Fi 6 (AX)", ip: "-", gateway: "-", rxBytes: "6.8 GB", txBytes: "8.9 GB", status: "UP", mtu: 1500 },
                    { name: "wg-edge", role: "CGNAT Tunnel", speed: "WireGuard Tunnel", ip: "10.42.0.2/24", gateway: "10.42.0.1", rxBytes: "48.2 GB", txBytes: "12.6 GB", status: "UP", mtu: 1420 }
                ],
                services: ["systemd-networkd", "kea-dhcp4", "nftables", "iwd"]
            },
            {
                id: "roost-controller-01",
                hostname: "roost-controller-01",
                role: "Central Controller & Apps",
                ip: "192.168.1.10",
                status: "Worker",
                model: "Dell OptiPlex Micro i5",
                cpu: 35.2,
                ram: "65% (5.2 GB)",
                temp: "41°C",
                uptime: "18d 02h",
                interfaces: [
                    { name: "enp3s0", role: "Management LAN", speed: "1000 Mbps Full", ip: "192.168.1.10/24", gateway: "192.168.1.1", rxBytes: "52.4 GB", txBytes: "48.1 GB", status: "UP", mtu: 1500 },
                    { name: "docker0", role: "Container Bridge", speed: "Virtual Bridge", ip: "172.17.0.1/16", gateway: "-", rxBytes: "28.1 GB", txBytes: "34.0 GB", status: "UP", mtu: 1500 }
                ],
                services: ["roostos-engine", "mosquitto", "technitium-dns", "docker"]
            },
            {
                id: "living-room-ap",
                hostname: "living-room-ap",
                role: "Wi-Fi 6 Mesh Satellite",
                ip: "192.168.1.4",
                status: "Mesh Node",
                model: "Cudy X6 AX1800 AP",
                cpu: 8.1,
                ram: "28% (280 MB)",
                temp: "39°C",
                uptime: "6d 14h",
                interfaces: [
                    { name: "eth0", role: "PoE Mesh Backhaul", speed: "1000 Mbps Full", ip: "192.168.1.4/24", gateway: "192.168.1.1", rxBytes: "18.2 GB", txBytes: "22.6 GB", status: "UP", mtu: 1500 },
                    { name: "wlan0", role: "5GHz Radio (80MHz)", speed: "Wi-Fi 6 (1201 Mbps)", ip: "-", gateway: "-", rxBytes: "14.1 GB", txBytes: "16.8 GB", status: "UP", mtu: 1500 },
                    { name: "wlan1", role: "2.4GHz Radio", speed: "Wi-Fi 6 (574 Mbps)", ip: "-", gateway: "-", rxBytes: "4.1 GB", txBytes: "5.8 GB", status: "UP", mtu: 1500 }
                ],
                services: ["iwd", "roostos-node"]
            },
            {
                id: "vps-edge-01",
                hostname: "vps-edge-01",
                role: "Cloud VPS Edge Gateway",
                ip: "198.51.100.89",
                status: "Cloud Ingress",
                model: "Hetzner Cloud CX22",
                cpu: 6.4,
                ram: "18% (720 MB)",
                temp: "Virtual",
                uptime: "45d 11h",
                interfaces: [
                    { name: "eth0", role: "Public Static WAN", speed: "10 Gbps Cloud", ip: "198.51.100.89/24", gateway: "198.51.100.1", rxBytes: "64.8 GB", txBytes: "68.2 GB", status: "UP", mtu: 1500 },
                    { name: "wg-edge", role: "WireGuard Hub", speed: "WireGuard Ingress", ip: "10.42.0.1/24", gateway: "-", rxBytes: "12.6 GB", txBytes: "48.2 GB", status: "UP", mtu: 1420 }
                ],
                services: ["caddy-reverse-proxy", "wireguard", "systemd-networkd"]
            }
        ]
    },
    admin: {
        bridgesVlans: [
            { name: "br-lan", type: "Bridge", ip: "192.168.1.1/24", ports: "eth1, eth2", dhcp: "Active (Kea)", isolate: false },
            { name: "vlan-guest", type: "VLAN 10", ip: "192.168.10.1/24", ports: "br-lan.10", dhcp: "Active (Kea)", isolate: true },
            { name: "vlan-iot", type: "VLAN 20", ip: "192.168.20.1/24", ports: "br-lan.20", dhcp: "Active (Kea)", isolate: true }
        ],
        dhcpScopes: [
            {
                id: "scope-lan",
                name: "Household LAN",
                nodeId: "roost-gateway-01",
                haStandby: "roost-controller-01",
                interface: "br-lan",
                subnet: "192.168.1.0/24",
                gateway: "192.168.1.1",
                enabled: true,
                poolStart: "192.168.1.100",
                poolEnd: "192.168.1.250",
                leaseTime: "86400",
                leaseTimeHuman: "24 Hours",
                dnsServers: "192.168.1.1",
                domainName: "lan.roost",
                authoritative: true,
                activeLeasesCount: 5,
                poolSize: 151
            },
            {
                id: "scope-guest",
                name: "Guest Network",
                nodeId: "roost-gateway-01",
                haStandby: "none",
                interface: "vlan-guest",
                subnet: "192.168.10.0/24",
                gateway: "192.168.10.1",
                enabled: true,
                poolStart: "192.168.10.50",
                poolEnd: "192.168.10.200",
                leaseTime: "7200",
                leaseTimeHuman: "2 Hours",
                dnsServers: "1.1.1.1, 1.0.0.1",
                domainName: "guest.roost",
                authoritative: true,
                activeLeasesCount: 1,
                poolSize: 151
            },
            {
                id: "scope-iot",
                name: "Smart Home IoT",
                nodeId: "roost-gateway-01",
                haStandby: "none",
                interface: "vlan-iot",
                subnet: "192.168.20.0/24",
                gateway: "192.168.20.1",
                enabled: true,
                poolStart: "192.168.20.100",
                poolEnd: "192.168.20.240",
                leaseTime: "604800",
                leaseTimeHuman: "7 Days",
                dnsServers: "192.168.1.1",
                domainName: "iot.roost",
                authoritative: false,
                activeLeasesCount: 3,
                poolSize: 141
            },
            {
                id: "scope-lab",
                name: "Lab & Containers",
                nodeId: "roost-controller-01",
                haStandby: "none",
                interface: "docker0",
                subnet: "172.17.0.0/16",
                gateway: "172.17.0.1",
                enabled: true,
                poolStart: "172.17.1.10",
                poolEnd: "172.17.1.200",
                leaseTime: "43200",
                leaseTimeHuman: "12 Hours",
                dnsServers: "172.17.0.1",
                domainName: "lab.roost",
                authoritative: true,
                activeLeasesCount: 2,
                poolSize: 191
            }
        ],
        activeLeases: [
            { ip: "192.168.1.101", mac: "10:9a:dd:33:44:55", hostname: "Dads-MacBook-Pro", network: "br-lan", expires: "18h 42m", vendor: "Apple Inc." },
            { ip: "192.168.1.102", mac: "22:33:44:55:66:77", hostname: "Moms-iPhone-15", network: "br-lan", expires: "21h 10m", vendor: "Apple Inc." },
            { ip: "192.168.1.103", mac: "33:44:55:66:77:88", hostname: "Alices-iPad", network: "br-lan", expires: "9h 15m", vendor: "Apple Inc." },
            { ip: "192.168.1.104", mac: "44:55:66:77:88:99", hostname: "Bobs-Chromebook", network: "br-lan", expires: "14h 05m", vendor: "Google" },
            { ip: "192.168.1.105", mac: "55:66:77:88:99:aa", hostname: "Sony-Bravia-OLED", network: "br-lan", expires: "23h 50m", vendor: "Sony" },
            { ip: "192.168.10.51", mac: "88:99:aa:bb:cc:dd", hostname: "Guest-Pixel-7", network: "vlan-guest", expires: "1h 12m", vendor: "Google" },
            { ip: "192.168.20.101", mac: "99:aa:bb:cc:dd:ee", hostname: "hue-bridge-hub", network: "vlan-iot", expires: "6d 14h", vendor: "Signify Philips" },
            { ip: "192.168.20.102", mac: "aa:bb:cc:dd:ee:ff", hostname: "ecobee-thermostat", network: "vlan-iot", expires: "5d 20h", vendor: "Ecobee" },
            { ip: "192.168.20.103", mac: "bb:cc:dd:ee:ff:00", hostname: "sonos-arc-soundbar", network: "vlan-iot", expires: "6d 22h", vendor: "Sonos" }
        ],
        nftSets: {
            quarantined: ["192.168.1.188"],
            schedule_blocked: ["192.168.1.151"],
            admin_blocked: []
        },
        portForwards: [
            { id: "pf-1", name: "Synology NAS HTTPS", wanPort: 8443, lanIp: "192.168.1.15", lanPort: 443, proto: "TCP", hits: 1420 },
            { id: "pf-2", name: "Plex Media Server", wanPort: 32400, lanIp: "192.168.1.20", lanPort: 32400, proto: "TCP", hits: 8940 },
            { id: "pf-3", name: "WireGuard Ingress", wanPort: 51820, lanIp: "Router Local", lanPort: 51820, proto: "UDP", hits: 324 }
        ],
        dnsRecords: [
            { id: "dns-1", domain: "roost-router.home.lan", ip: "192.168.1.1", type: "A" },
            { id: "dns-2", domain: "nas.home.lan", ip: "192.168.1.15", type: "A" },
            { id: "dns-3", domain: "proxmox.home.lan", ip: "192.168.1.30", type: "A" }
        ],
        yamlFiles: {
            "network.yaml": `network:
  interfaces:
    - name: eth0
      role: wan
      dhcp: true
    - name: eth1
      role: lan
      bridge: br-lan
  bridges:
    - name: br-lan
      ip: 192.168.1.1/24`,
            "devices.yaml": `people:
  - id: dad
    name: Dad
devices:
  - mac: "1a:2b:3c:4d:5e:6f"
    name: "Dad's Phone"`
        }
    }
};
