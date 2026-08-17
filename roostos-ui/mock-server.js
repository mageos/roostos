/**
 * Standalone RoostOS UI Mock Server
 * Serves static assets and provides mock REST API responses for frontend development & UI testing.
 * Runs with standard Node.js without requiring extra npm packages.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const PUBLIC_DIR = __dirname;

// In-memory mock database for dynamic testing
const mockDb = {
    user: {
        username: "admin",
        role: "admin",
        email: "admin@roostos.local"
    },
    system: {
        hostname: "roost-router-mock",
        version: "0.1.0-dev",
        cpu_load: 14.2,
        ram_usage: 42.8,
        uptime: "4 days, 6 hours",
        rx_rate: 1048576,
        tx_rate: 262144
    },
    network: {
        interfaces: [
            { name: "eth0", status: "up", mac: "52:54:00:12:34:56", ip: "192.168.100.45/24", mtu: 1500, speed: "1000 Mbps", duplex: "Full", rx_rate: 1048576, tx_rate: 262144 },
            { name: "eth1", status: "up", mac: "52:54:00:78:9a:bc", ip: "192.168.1.1/24", mtu: 1500, speed: "1000 Mbps", duplex: "Full", rx_rate: 524288, tx_rate: 1048576 },
            { name: "wlan0", status: "up", mac: "52:54:00:de:f0:12", ip: "", mtu: 1500, speed: "Wi-Fi 6 (AX)", duplex: "Full", rx_rate: 131072, tx_rate: 65536 }
        ],
        wan: {
            interface: "eth0",
            proto: "dhcp",
            ip: "192.168.100.45/24",
            gateway: "192.168.100.1",
            dns: ["1.1.1.1", "8.8.8.8"],
            mtu: 1500
        },
        bridges: [
            { name: "br0", ip: "192.168.1.1/24", interfaces: ["eth1"], dhcp_enabled: true, isolate: false },
            { name: "br-guest", ip: "192.168.10.1/24", interfaces: ["vlan-guest"], dhcp_enabled: true, isolate: true }
        ],
        vlans: [
            { id: 10, name: "vlan10", parent: "eth1", ip: "10.10.10.1/24" },
            { id: 20, name: "vlan-guest", parent: "eth1", ip: "192.168.10.1/24" }
        ],
        zones: [
            { id: "lan", name: "Household LAN", interfaces: ["br0"], isolate: false, allow_zones: ["wan", "iot", "guest"], masquerade: false },
            { id: "wan", name: "Internet WAN", interfaces: ["eth0"], isolate: false, allow_zones: [], masquerade: true },
            { id: "iot", name: "Smart Home IoT Zone", interfaces: ["vlan-iot"], isolate: true, allow_zones: ["wan"], masquerade: false },
            { id: "guest", name: "Guest Wi-Fi Zone", interfaces: ["vlan-guest"], isolate: true, allow_zones: ["wan"], masquerade: false }
        ],
        qos: {
            enabled: true,
            algorithm: "cake",
            download_mbps: 1000,
            upload_mbps: 100,
            interface: "eth0",
            diffserv: "diffserv4"
        }
    },
    wifi: {
        access_points: [
            { ssid: "Roost-Home", radio: "wlan0 (5GHz)", security: "wpa3-sae", passphrase: "", channel: "36", channel_width: "80MHz", bridge: "br0", isolate: false },
            { ssid: "Roost-IoT", radio: "wlan1 (2.4GHz)", security: "wpa2-psk", passphrase: "", channel: "6", channel_width: "20MHz", bridge: "br0", isolate: true },
            { ssid: "Roost-Guest", radio: "wlan0 (5GHz)", security: "wpa2-psk", passphrase: "", channel: "149", channel_width: "80MHz", bridge: "br-guest", isolate: true }
        ]
    },
    vpns: [
        { id: "wg-home", type: "wireguard", name: "Home WireGuard Tunnel", status: "active", endpoint: "vpn.roostos.net:51820" }
    ],
    devices: [
        { mac: "a4:83:e7:12:34:56", name: "Matt MacBook Pro", owner: "matt", location: "office", static_ip: "192.168.1.50", tags: ["work", "laptop"] },
        { mac: "52:54:00:11:22:33", name: "Living Room Apple TV", owner: "household", location: "living_room", static_ip: "192.168.1.20", tags: ["entertainment"] },
        { mac: "60:01:94:aa:bb:cc", name: "Nest Thermostat", owner: "household", location: "hallway", static_ip: "", tags: ["iot"] }
    ],
    active_leases: [
        { ip: "192.168.1.105", mac: "a4:83:e7:99:88:77", hostname: "iphone-matt", expires: "18h 45m" },
        { ip: "192.168.1.142", mac: "b2:c3:d4:ee:ff:01", hostname: "kindle-paperwhite", expires: "22h 10m" }
    ],
    active_arp: [
        { ip: "192.168.1.50", mac: "a4:83:e7:12:34:56" },
        { ip: "192.168.1.20", mac: "52:54:00:11:22:33" },
        { ip: "192.168.1.105", mac: "a4:83:e7:99:88:77" }
    ],
    users: [
        { username: "admin", role: "admin" },
        { username: "parent", role: "parent" }
    ],
    schedules: [
        { name: "Kids Bedtime", days: ["mon", "tue", "wed", "thu", "sun"], start: "21:00", end: "06:30", targets: ["kids-tablets"] }
    ],
    firewallRules: [
        { name: "Allow-SSH-Admin", interface: "lan", protocol: "tcp", port: 22, source: "192.168.1.0/24", action: "accept", enabled: true },
        { name: "Block-Telnet", interface: "*", protocol: "tcp", port: 23, source: "", action: "drop", enabled: true }
    ],
    dns: {
        forwarders: ["1.1.1.1", "8.8.8.8"],
        ad_blocking_enabled: true
    },
    buildings: [{ id: "main", name: "Main House" }],
    rooms: [
        { id: "office", name: "Home Office", building_id: "main" },
        { id: "living_room", name: "Living Room", building_id: "main" }
    ],
    plugins: [
        { id: "dns-technitium", name: "Technitium DNS Server", enabled: true, status: "running" }
    ]
};

const mimeTypes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon'
};

function sendJson(res, data, status = 200) {
    res.writeHead(status, {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
    });
    res.end(JSON.stringify(data));
}

function parseBody(req) {
    return new Promise((resolve) => {
        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', () => {
            try {
                resolve(body ? JSON.parse(body) : {});
            } catch (e) {
                resolve({});
            }
        });
    });
}

const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const pathname = url.pathname;

    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
        res.writeHead(204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
        });
        return res.end();
    }

    // --- Mock API Routes ---
    if (pathname.startsWith('/api/')) {
        if (pathname === '/api/auth/me') {
            return sendJson(res, mockDb.user);
        }
        if (pathname === '/api/system') {
            return sendJson(res, mockDb.system);
        }
        if (pathname === '/api/network') {
            if (req.method === 'POST') {
                const payload = await parseBody(req);
                if (payload.network) mockDb.network = { ...mockDb.network, ...payload.network };
                if (payload.wifi) mockDb.wifi = { ...mockDb.wifi, ...payload.wifi };
                if (payload.vpns) mockDb.vpns = payload.vpns;
                return sendJson(res, { status: "success", message: "Network settings updated." });
            }
            return sendJson(res, { network: mockDb.network, wifi: mockDb.wifi, vpns: mockDb.vpns });
        }
        if (pathname === '/api/devices') {
            return sendJson(res, { devices: mockDb.devices, active_leases: mockDb.active_leases, active_arp: mockDb.active_arp });
        }
        if (pathname === '/api/schedules') {
            return sendJson(res, { schedules: mockDb.schedules, port_forwards: [] });
        }
        if (pathname === '/api/firewall/rules') {
            return sendJson(res, { rules: mockDb.firewallRules });
        }
        if (pathname === '/api/dns/config') {
            return sendJson(res, mockDb.dns);
        }
        if (pathname === '/api/users') {
            return sendJson(res, mockDb.users);
        }
        if (pathname === '/api/buildings') {
            return sendJson(res, mockDb.buildings);
        }
        if (pathname === '/api/rooms') {
            return sendJson(res, mockDb.rooms);
        }
        if (pathname === '/api/plugins') {
            return sendJson(res, mockDb.plugins);
        }
        return sendJson(res, { status: "ok" });
    }

    // --- Static File Serving ---
    let filePath = path.join(PUBLIC_DIR, pathname === '/' ? 'index.html' : pathname);
    
    // Fallback to index.html for unknown routes if file not found
    if (!fs.existsSync(filePath)) {
        filePath = path.join(PUBLIC_DIR, 'index.html');
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';

    fs.readFile(filePath, (err, content) => {
        if (err) {
            res.writeHead(500);
            return res.end(`Server Error: ${err.code}`);
        }

        // If serving index.html, inject mock auth token auto-setter so login isn't required in dev
        if (ext === '.html') {
            const htmlStr = content.toString('utf8');
            const injectedHtml = htmlStr.replace(
                '<head>',
                '<head><script>if(!localStorage.getItem("roostos_token")){localStorage.setItem("roostos_token","mock-dev-token");}</script>'
            );
            res.writeHead(200, { 'Content-Type': contentType });
            return res.end(injectedHtml, 'utf8');
        }

        res.writeHead(200, { 'Content-Type': contentType });
        res.end(content, 'utf8');
    });
});

server.listen(PORT, () => {
    console.log(`\n======================================================`);
    console.log(`  RoostOS Mock UI Dev Server Running!`);
    console.log(`  Access the Web UI at: http://localhost:${PORT}`);
    console.log(`  Auto-authenticates as admin with full mock backend.`);
    console.log(`======================================================\n`);
});
