// RoostOS Reactive State Store, Pub/Sub Event Bus & API Synchronization
import { initialData } from './data.js';
import { api } from './api.js';
import { syncStateWithBackend } from './state-sync.js';
import { deviceActions, dhcpActions } from './state-actions.js';

class StateStore {
    constructor() {
        this.data = JSON.parse(JSON.stringify(initialData));
        this.listeners = new Set();
        this.currentConcept = "concept1";
        this.concept1Persona = "household"; // 'household' | 'admin'
        this.concept2Density = "standard";
        this.deviceMode = "responsive";
    }

    subscribe(fn) {
        this.listeners.add(fn);
        return () => this.listeners.delete(fn);
    }

    notify(event = "change") {
        for (const listener of this.listeners) {
            try { listener(this.data, event); } catch (e) { console.error(e); }
        }
    }

    async syncWithBackend() {
        await syncStateWithBackend(this.data, (ev) => this.notify(ev));
    }

    // Devices Delegation
    addDevice(dev) { return deviceActions.addDevice(this, dev); }
    updateDevice(mac, updates) { return deviceActions.updateDevice(this, mac, updates); }
    deleteDevice(mac) { return deviceActions.deleteDevice(this, mac); }
    togglePauseDevice(mac) { return deviceActions.togglePauseDevice(this, mac); }

    // Family Profiles & Parental Controls
    async addPerson(person) {
        const personId = person.id || person.name.toLowerCase().replace(/\s+/g, '-').replace(/'/g, '');
        try {
            await api.createFamilyPerson({
                id: personId,
                name: person.name,
                role: person.role || 'member',
                screentime_limit_minutes: Number(person.screentimeLimit) || 120,
                bedtime: {
                    start_time: person.bedtimeStart || '21:00',
                    end_time: person.bedtimeEnd || '06:30',
                    enabled: true,
                    active_now: false
                },
                filter_level: person.filterLevel || 'Standard'
            });
            await this.syncWithBackend();
        } catch (e) {
            console.warn('createFamilyPerson API failed, fallback local:', e);
            this.data.people.push({
                id: personId, name: person.name, role: person.role || 'member',
                avatar: person.role === 'kid' ? '🧒' : '👤', color: '#3b82f6',
                screentimeLimit: Number(person.screentimeLimit) || 120, screentimeUsed: 0,
                bedtimeStart: person.bedtimeStart || '21:00', bedtimeEnd: person.bedtimeEnd || '06:30',
                bedtimeActive: false, filterLevel: person.filterLevel || 'Standard', deviceCount: 0
            });
        }
        this.notify('people');
    }

    async updatePerson(id, updates) {
        const p = this.data.people.find(x => x.id === id);
        if (p) {
            Object.assign(p, updates);
            try {
                await api.updateFamilyPerson(id, {
                    id: p.id,
                    name: p.name,
                    role: p.role,
                    screentime_limit_minutes: Number(p.screentimeLimit) || 0,
                    screentime_used_minutes: p.screentimeUsed || 0,
                    bedtime: {
                        start_time: p.bedtimeStart || '21:00',
                        end_time: p.bedtimeEnd || '06:30',
                        enabled: true,
                        active_now: p.bedtimeActive || false
                    },
                    filter_level: p.filterLevel || 'Standard'
                });
            } catch (e) { console.warn('updateFamilyPerson API failed:', e); }
            this.notify('people');
        }
    }

    async deletePerson(id) {
        try { await api.deleteFamilyPerson(id); }
        catch (e) { console.warn('deleteFamilyPerson API failed:', e); }
        this.data.people = this.data.people.filter(p => p.id !== id);
        this.notify('people');
    }

    async togglePauseKids(paused = true) {
        try { await api.pauseKids(paused); } catch (e) { console.warn(e); }
        this.data.people.filter(p => p.role === 'kid').forEach(k => { k.bedtimeActive = paused; });
        this.notify('people');
    }

    async triggerDinnerTime(minutes = 60) {
        try { await api.triggerDinnerTime(minutes); } catch (e) { console.warn(e); }
        this.data.people.filter(p => p.role === 'kid').forEach(k => { k.bedtimeActive = true; });
        this.notify('people');
    }

    async addBonusScreentime(personId, minutes = 30) {
        try { await api.grantScreentimeBonus(personId, minutes); } catch (e) { console.warn(e); }
        const p = this.data.people.find(x => x.id === personId);
        if (p) {
            p.screentimeLimit = (p.screentimeLimit || 60) + minutes;
            if (p.bedtimeActive && p.screentimeUsed < p.screentimeLimit) p.bedtimeActive = false;
            this.notify('people');
        }
    }

    async toggleBedtime(personId) {
        const p = this.data.people.find(x => x.id === personId);
        if (p) {
            p.bedtimeActive = !p.bedtimeActive;
            try {
                await api.pausePerson(personId, p.bedtimeActive);
            } catch (e) { console.warn('pausePerson API failed:', e); }
            this.notify('people');
        }
    }

    // DHCP Delegation
    addDhcpScope(scope) { return dhcpActions.addDhcpScope(this, scope); }
    updateDhcpScope(id, updates) { return dhcpActions.updateDhcpScope(this, id, updates); }
    deleteDhcpScope(id) { return dhcpActions.deleteDhcpScope(this, id); }
    reserveDynamicLease(lease) { return dhcpActions.convertLeaseToStatic(this, lease.mac, lease.hostname); }
    convertLeaseToStatic(mac, hostname = null) { return dhcpActions.convertLeaseToStatic(this, mac, hostname); }

    // Protection, DNS & Firewall
    async toggleAdBlock() {
        this.data.protection.adBlocking.enabled = !this.data.protection.adBlocking.enabled;
        try {
            await api.updateSecurityShields({ ad_blocking_enabled: this.data.protection.adBlocking.enabled });
        } catch (e) { console.warn(e); }
        this.notify('protection');
    }

    async toggleGuestWifi(enabled) {
        try {
            const res = await api.toggleGuestWifi(enabled);
            const guestNet = this.data.wifiNetworks.find(w => w.ssid.includes('Guest') || w.isolate);
            if (guestNet) guestNet.status = res.enabled ? 'Active' : 'Disabled';
        } catch (e) { console.warn(e); }
        this.notify('wifi');
    }

    async toggleSafeSearch() {
        this.data.protection.safeSearch.enabled = !this.data.protection.safeSearch.enabled;
        try {
            await api.updateSecurityShields({ safe_search_enabled: this.data.protection.safeSearch.enabled });
        } catch (e) { console.warn(e); }
        this.notify('protection');
    }

    async toggleVpn() {
        this.data.protection.vpnTunnel.enabled = !this.data.protection.vpnTunnel.enabled;
        try {
            await api.updateSecurityShields({ privacy_vpn_enabled: this.data.protection.vpnTunnel.enabled });
        } catch (e) { console.warn(e); }
        this.notify('protection');
    }

    async runSpeedTest() {
        try {
            const res = await api.runSpeedTest();
            if (res) {
                this.data.system.downloadMbps = Math.round(res.download_mbps);
                this.data.system.uploadMbps = Math.round(res.upload_mbps);
                this.data.system.pingMs = res.ping_ms;
                this.notify('system');
                return res;
            }
        } catch (e) { console.warn('runSpeedTest API failed:', e); }
        return null;
    }

    async allowBlockedRequest(id) {
        const item = this.data.protection.blockedRequests?.find(b => b.id === id);
        if (item) {
            item.allowed = true;
            try { await api.allowThreatTarget(item.target, item.subsystem); } catch (e) { console.warn(e); }
            this.notify('protection');
        }
    }

    allowQuarantinedDevice(mac, owner, name) {
        this.data.system.unassignedDeviceAlert = false;
        let d = this.data.devices.find(x => x.mac === mac);
        if (d) {
            d.owner = owner;
            d.name = name;
            d.status = 'online';
        }
        this.notify('devices');
        this.notify('system');
    }

    async addDnsRecord(rec) {
        const id = rec.id || `dns-${Date.now().toString(36)}`;
        try {
            await api.createDnsRecord({
                id,
                domain: rec.domain,
                type: rec.type || 'A',
                ip: rec.ip
            });
            await this.syncWithBackend();
        } catch (e) {
            console.warn('createDnsRecord API fallback:', e);
            this.data.admin.dnsRecords.push({ id, ...rec });
        }
        this.notify('dns');
    }

    async deleteDnsRecord(id) {
        try {
            await api.deleteDnsRecord(id);
        } catch (e) {
            console.warn('deleteDnsRecord API fallback:', e);
        }
        this.data.admin.dnsRecords = this.data.admin.dnsRecords.filter(r => r.id !== id && r.domain !== id);
        this.notify('dns');
    }

    async addPortForward(pf) {
        const id = pf.id || `pf-${Date.now().toString(36)}`;
        try {
            await api.createPortForward({
                name: pf.name,
                protocol: (pf.proto || 'tcp').toLowerCase(),
                external_port: Number(pf.wanPort),
                internal_ip: pf.lanIp,
                internal_port: Number(pf.lanPort || pf.wanPort),
                enabled: true
            });
            await this.syncWithBackend();
        } catch (e) {
            console.warn('createPortForward API fallback:', e);
            this.data.admin.portForwards.push({ id, hits: 0, ...pf });
        }
        this.notify('firewall');
    }

    async deletePortForward(nameOrId) {
        const pf = this.data.admin.portForwards.find(p => p.id === nameOrId || p.name === nameOrId);
        const name = pf ? pf.name : nameOrId;
        try {
            await api.deletePortForward(name);
        } catch (e) {
            console.warn('deletePortForward API fallback:', e);
        }
        this.data.admin.portForwards = this.data.admin.portForwards.filter(p => p.id !== nameOrId && p.name !== nameOrId);
        this.notify('firewall');
    }
}

export const store = new StateStore();
