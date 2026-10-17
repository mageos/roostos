// RoostOS Initial State Definition & Mock Factory
import { initialMockData } from './mock-data.js';

export const emptyInitialData = {
    system: {
        hostname: "roost-router",
        domain: "local",
        version: "0.3.0",
        uptime: "-",
        wanIp: "-",
        gatewayIp: "-",
        ispName: "Network Gateway",
        pingMs: 0,
        downloadMbps: 0,
        uploadMbps: 0,
        cpuPercent: 0,
        ramPercent: 0,
        cpuCores: 1,
        kernelVersion: "Linux",
        ramTotalGb: 0,
        ramUsedGb: 0,
        tempC: 0,
        unassignedDeviceAlert: false,
        unassignedDevice: null,
    },
    edgeGateway: {
        enabled: false,
        cgnatDetected: false,
        cgnatIspIp: "-",
        vpsPublicIp: "-",
        vpsHostname: "-",
        tunnelSubnet: "-",
        localTunnelIp: "-",
        vpsTunnelIp: "-",
        tunnelPort: 51820,
        tunnelStatus: "Not Enrolled",
        handshake: "-",
        rxBytes: "0 B",
        txBytes: "0 B",
        token: "",
        ingressRules: []
    },
    people: [],
    devices: [],
    rooms: [],
    wifiNetworks: [],
    protection: {
        adBlocking: { enabled: true, blockedToday: 0, blocklistPercent: 0, queriesToday: 0 },
        safeSearch: { enabled: false, forcedForKids: false },
        malwareProtection: { enabled: true, threatsBlocked: 0 },
        vpnTunnel: { enabled: false, name: "", endpoint: "", handshake: "" },
        blockedRequests: []
    },
    cluster: {
        activeNodeFilter: "all",
        nodes: []
    },
    admin: {
        bridgesVlans: [],
        dhcpScopes: [],
        activeLeases: [],
        dhcpReservations: [],
        firewallRules: [],
        portForwards: [],
        dnsRecords: [],
        yamlFiles: {},
        nftSets: {
            quarantined: [],
            schedule_blocked: [],
            admin_blocked: []
        },
        network: {
            interfaces: [],
            zones: [
                { name: "wan", label: "WAN / Internet", egress: true, ingress: false, isolate: true, color: "#3b82f6" },
                { name: "lan", label: "Trusted Home LAN", egress: true, ingress: true, isolate: false, color: "#10b981" },
                { name: "guest", label: "Guest Network", egress: true, ingress: false, isolate: true, color: "#f59e0b" },
                { name: "iot", label: "IoT Isolated Zone", egress: true, ingress: false, isolate: true, color: "#8b5cf6" },
                { name: "edge", label: "Cloud VPS Edge", egress: true, ingress: true, isolate: false, color: "#06b6d4" }
            ]
        }
    }
};

export { initialMockData };

// Default initial state: use mock only if running in mock container mode
export const initialData = (typeof window !== 'undefined' && (window.ROOSTOS_MOCK || localStorage.getItem('roostos_mock') === '1'))
    ? JSON.parse(JSON.stringify(initialMockData))
    : JSON.parse(JSON.stringify(emptyInitialData));
