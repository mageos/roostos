// RoostOS Prototype State Store & Event Bus
import { initialData } from './data.js';

class StateStore {
    constructor() {
        this.data = JSON.parse(JSON.stringify(initialData));
        this.listeners = new Set();
        this.currentConcept = "concept1"; // 'concept1' | 'concept2'
        this.concept1Persona = "household"; // 'household' | 'admin'
        this.concept2Density = "standard"; // 'standard' | 'expert'
        this.deviceMode = "responsive"; // 'responsive' | 'mobile' | 'tablet'
    }

    subscribe(fn) {
        this.listeners.add(fn);
        return () => this.listeners.delete(fn);
    }

    notify(event = "change") {
        for (const listener of this.listeners) {
            listener(this.data, event);
        }
    }

    togglePauseDevice(mac) {
        const dev = this.data.devices.find(d => d.mac === mac);
        if (!dev) return;
        if (dev.status === "paused") {
            dev.status = "online";
            const idx = this.data.admin.nftSets.admin_blocked.indexOf(dev.ip);
            if (idx > -1) this.data.admin.nftSets.admin_blocked.splice(idx, 1);
        } else {
            dev.status = "paused";
            if (!this.data.admin.nftSets.admin_blocked.includes(dev.ip)) {
                this.data.admin.nftSets.admin_blocked.push(dev.ip);
            }
        }
        this.notify("devices");
    }

    addBonusScreentime(personId, minutes = 30) {
        const p = this.data.people.find(x => x.id === personId);
        if (p) {
            p.screentimeLimit = (p.screentimeLimit || 60) + minutes;
            if (p.bedtimeActive && p.screentimeUsed < p.screentimeLimit) {
                p.bedtimeActive = false;
            }
            this.notify("people");
        }
    }

    toggleBedtime(personId) {
        const p = this.data.people.find(x => x.id === personId);
        if (p) {
            p.bedtimeActive = !p.bedtimeActive;
            const pDevices = this.data.devices.filter(d => d.owner === personId);
            pDevices.forEach(d => {
                if (p.bedtimeActive) {
                    d.status = "blocked";
                    if (!this.data.admin.nftSets.schedule_blocked.includes(d.ip)) {
                        this.data.admin.nftSets.schedule_blocked.push(d.ip);
                    }
                } else {
                    d.status = "online";
                    const idx = this.data.admin.nftSets.schedule_blocked.indexOf(d.ip);
                    if (idx > -1) this.data.admin.nftSets.schedule_blocked.splice(idx, 1);
                }
            });
            this.notify("people");
        }
    }

    toggleAdBlock() {
        this.data.protection.adBlocking.enabled = !this.data.protection.adBlocking.enabled;
        this.notify("protection");
    }

    toggleVpn() {
        this.data.protection.vpnTunnel.enabled = !this.data.protection.vpnTunnel.enabled;
        this.data.protection.vpnTunnel.handshake = this.data.protection.vpnTunnel.enabled ? "12s ago (Active)" : "Never";
        this.notify("protection");
    }

    addDevice(dev) {
        if (!dev.mac) return;
        const existing = this.data.devices.find(d => d.mac.toLowerCase() === dev.mac.toLowerCase());
        if (existing) return;
        const newDev = {
            mac: dev.mac,
            name: dev.name || "New Device",
            owner: dev.owner || "",
            location: dev.location || "Living Room",
            ip: dev.staticIp || `192.168.1.${120 + this.data.devices.length}`,
            staticIp: dev.staticIp || "",
            tags: dev.tags ? (Array.isArray(dev.tags) ? dev.tags : dev.tags.split(",").map(t => t.trim())) : ["personal"],
            zone: dev.zone || "lan",
            status: "online",
            signal: -50,
            rxMbps: 0.1,
            txMbps: 0.05,
            icon: dev.icon || "📱",
            vendor: dev.vendor || "Generic"
        };
        this.data.devices.unshift(newDev);
        this.notify("devices");
    }

    updateDevice(mac, updated) {
        const idx = this.data.devices.findIndex(d => d.mac === mac);
        if (idx !== -1) {
            this.data.devices[idx] = {
                ...this.data.devices[idx],
                ...updated,
                tags: updated.tags ? (Array.isArray(updated.tags) ? updated.tags : updated.tags.split(",").map(t => t.trim())) : this.data.devices[idx].tags
            };
            this.notify("devices");
        }
    }

    deleteDevice(mac) {
        this.data.devices = this.data.devices.filter(d => d.mac !== mac);
        this.notify("devices");
    }

    addPerson(p) {
        if (!p.id || !p.name) return;
        this.data.people.push({
            id: p.id,
            name: p.name,
            role: p.role || "member",
            color: p.color || "#8b5cf6",
            avatar: p.avatar || "👤",
            screentimeLimit: Number(p.screentimeLimit) || 120,
            screentimeUsed: 0,
            bedtimeStart: p.bedtimeStart || "21:00",
            bedtimeEnd: p.bedtimeEnd || "06:30",
            bedtimeActive: false,
            filterLevel: p.filterLevel || "Standard",
            deviceCount: 0
        });
        this.notify("people");
    }

    updatePerson(id, updated) {
        const p = this.data.people.find(x => x.id === id);
        if (p) {
            Object.assign(p, updated);
            this.notify("people");
        }
    }

    deletePerson(id) {
        this.data.people = this.data.people.filter(x => x.id !== id);
        this.data.devices.forEach(d => {
            if (d.owner === id) d.owner = "";
        });
        this.notify("people");
    }

    allowQuarantinedDevice(mac, owner = "dad", name = "Samsung Galaxy S23") {
        const d = this.data.devices.find(x => x.mac === mac);
        if (d) {
            d.status = "online";
            d.owner = owner;
            d.name = name;
            d.tags = ["personal", "mobile"];
            const idx = this.data.admin.nftSets.quarantined.indexOf(d.ip);
            if (idx > -1) this.data.admin.nftSets.quarantined.splice(idx, 1);
            this.data.system.unassignedDeviceAlert = false;
            this.notify("devices");
        }
    }

    addPortForward(pf) {
        this.data.admin.portForwards.push({
            id: `pf-${Date.now()}`,
            name: pf.name || "Custom Rule",
            wanPort: Number(pf.wanPort) || 8080,
            lanIp: pf.lanIp || "192.168.1.50",
            lanPort: Number(pf.lanPort) || 8080,
            proto: pf.proto || "TCP",
            hits: 0
        });
        this.notify("firewall");
    }

    deletePortForward(id) {
        this.data.admin.portForwards = this.data.admin.portForwards.filter(p => p.id !== id);
        this.notify("firewall");
    }

    addDnsRecord(rec) {
        this.data.admin.dnsRecords.push({
            id: `dns-${Date.now()}`,
            domain: rec.domain || "custom.home.lan",
            ip: rec.ip || "192.168.1.1",
            type: rec.type || "A"
        });
        this.notify("dns");
    }

    deleteDnsRecord(id) {
        this.data.admin.dnsRecords = this.data.admin.dnsRecords.filter(r => r.id !== id);
        this.notify("dns");
    }

    updateDhcpScope(id, updated) {
        const sc = this.data.admin.dhcpScopes.find(s => s.id === id);
        if (sc) {
            Object.assign(sc, updated);
            this.notify("dhcp");
        }
    }

    addDhcpScope(scope) {
        this.data.admin.dhcpScopes.push({
            id: `scope-${Date.now()}`,
            name: scope.name || "Custom Network",
            interface: scope.interface || "vlan-custom",
            subnet: scope.subnet || "192.168.30.0/24",
            gateway: scope.gateway || "192.168.30.1",
            enabled: scope.enabled !== false,
            poolStart: scope.poolStart || "192.168.30.100",
            poolEnd: scope.poolEnd || "192.168.30.200",
            leaseTime: scope.leaseTime || "86400",
            leaseTimeHuman: scope.leaseTimeHuman || "24 Hours",
            dnsServers: scope.dnsServers || scope.gateway || "192.168.30.1",
            domainName: scope.domainName || "custom.roost",
            authoritative: true,
            activeLeasesCount: 0,
            poolSize: 101
        });
        this.notify("dhcp");
    }

    deleteDhcpScope(id) {
        this.data.admin.dhcpScopes = this.data.admin.dhcpScopes.filter(s => s.id !== id);
        this.notify("dhcp");
    }

    reserveDynamicLease(lease) {
        const existing = this.data.devices.find(d => d.mac.toLowerCase() === lease.mac.toLowerCase());
        if (existing) {
            existing.staticIp = lease.ip;
        } else {
            this.data.devices.push({
                mac: lease.mac,
                name: lease.hostname || "Reserved Device",
                owner: "",
                location: "Main",
                ip: lease.ip,
                staticIp: lease.ip,
                tags: ["static-dhcp"],
                zone: lease.network.includes("guest") ? "guest" : lease.network.includes("iot") ? "iot" : "lan",
                status: "online",
                signal: -55,
                rxMbps: 0.1,
                txMbps: 0.1,
                icon: "📌",
                vendor: lease.vendor || "Hardware"
            });
        }
        this.notify("devices");
        this.notify("dhcp");
    }

    allowBlockedRequest(id) {
        const blk = this.data.protection.blockedRequests.find(b => b.id === id);
        if (blk) {
            blk.allowed = true;
            this.notify("protection");
        }
    }
}

export const store = new StateStore();
