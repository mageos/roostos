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
        try {
            await api.request('/api/people', {
                method: 'POST',
                body: JSON.stringify({ id: person.id, name: person.name, dns_profile: person.filterLevel })
            });
            await this.syncWithBackend();
        } catch (e) {
            console.warn('addPerson failed, fallback local:', e);
            this.data.people.push({
                id: person.id, name: person.name, role: person.role || 'member',
                avatar: person.role === 'kid' ? '🧒' : '👤', color: '#3b82f6',
                screentimeLimit: person.screentimeLimit || 120, screentimeUsed: 0,
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
                await api.request('/api/people', {
                    method: 'POST',
                    body: JSON.stringify({ id: p.id, name: p.name, dns_profile: p.filterLevel })
                });
            } catch (e) { console.warn('updatePerson API failed:', e); }
            this.notify('people');
        }
    }

    async deletePerson(id) {
        try { await api.request(`/api/people/${encodeURIComponent(id)}`, { method: 'DELETE' }); }
        catch (e) { console.warn('deletePerson API failed:', e); }
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
                if (p.bedtimeActive) await api.pauseKids(true);
                else await api.grantScreentimeBonus(personId, 30);
            } catch (e) { console.warn(e); }
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

    toggleVpn() {
        this.data.protection.vpnTunnel.enabled = !this.data.protection.vpnTunnel.enabled;
        this.notify('protection');
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

    addDnsRecord(rec) {
        this.data.admin.dnsRecords.push({ id: `dns-${Date.now().toString(36)}`, ...rec });
        this.notify('dns');
    }

    deleteDnsRecord(id) {
        this.data.admin.dnsRecords = this.data.admin.dnsRecords.filter(r => r.id !== id);
        this.notify('dns');
    }

    addPortForward(pf) {
        this.data.admin.portForwards.push({ id: `pf-${Date.now().toString(36)}`, ...pf });
        this.notify('firewall');
    }

    deletePortForward(id) {
        this.data.admin.portForwards = this.data.admin.portForwards.filter(p => p.id !== id);
        this.notify('firewall');
    }
}

export const store = new StateStore();
