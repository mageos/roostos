// Action Handlers for RoostOS StateStore
import { api } from './api.js';

export const deviceActions = {
    async addDevice(store, dev) {
        try {
            await api.registerDevice({
                mac: dev.mac,
                name: dev.name,
                owner: dev.owner || "",
                location: dev.location || "",
                tags: [dev.zone || 'lan'],
                static_ip: dev.staticIp || ""
            });
            await store.syncWithBackend();
        } catch (e) {
            console.warn('API registerDevice failed, updating locally:', e);
            const exists = store.data.devices.find(d => d.mac === dev.mac);
            if (!exists) {
                store.data.devices.push({
                    mac: dev.mac,
                    name: dev.name,
                    owner: dev.owner || '',
                    location: dev.location || '',
                    ip: dev.staticIp || dev.ip || '192.168.1.150',
                    staticIp: dev.staticIp || '',
                    zone: dev.zone || 'lan',
                    status: 'online',
                    signal: -50,
                    rxMbps: 0,
                    txMbps: 0,
                    icon: '📱',
                    vendor: 'Client Device'
                });
            }
        }
        store.notify('devices');
    },

    async updateDevice(store, mac, updates) {
        const d = store.data.devices.find(x => x.mac === mac);
        if (d) {
            Object.assign(d, updates);
            try {
                await api.registerDevice({
                    mac: d.mac,
                    name: d.name,
                    owner: d.owner || "",
                    location: d.location || "",
                    tags: [d.zone || 'lan'],
                    static_ip: d.staticIp || ""
                });
            } catch (e) { console.warn('API update device failed:', e); }
            store.notify('devices');
        }
    },

    async deleteDevice(store, mac) {
        try { await api.deleteDevice(mac); } catch (e) { console.warn(e); }
        store.data.devices = store.data.devices.filter(d => d.mac !== mac);
        store.notify('devices');
    },

    togglePauseDevice(store, mac) {
        const d = store.data.devices.find(x => x.mac === mac);
        if (d) {
            d.status = (d.status === 'paused' || d.status === 'blocked') ? 'online' : 'paused';
            store.notify('devices');
        }
    }
};

export const dhcpActions = {
    async addDhcpScope(store, scope) {
        const id = scope.id || `scope-${Date.now().toString(36)}`;
        const fullScope = { id, ...scope };
        try {
            await api.createDhcpScope({
                id: fullScope.id,
                name: fullScope.name,
                node_id: fullScope.nodeId || 'roost-gateway-01',
                ha_standby_node: fullScope.haStandby || 'none',
                interface: fullScope.interface,
                subnet: fullScope.subnet,
                gateway: fullScope.gateway,
                enabled: fullScope.enabled ?? true,
                pool_start: fullScope.poolStart,
                pool_end: fullScope.poolEnd,
                lease_time_seconds: Number(fullScope.leaseTime) || 86400,
                dns_servers: [fullScope.gateway],
                domain_name: 'local',
                authoritative: true
            });
            await store.syncWithBackend();
        } catch (e) {
            console.warn('createDhcpScope failed, updating locally:', e);
            store.data.admin.dhcpScopes.push(fullScope);
        }
        store.notify('dhcp');
    },

    async updateDhcpScope(store, id, updates) {
        const sc = store.data.admin.dhcpScopes.find(s => s.id === id);
        if (sc) {
            Object.assign(sc, updates);
            try {
                await api.updateDhcpScope(id, {
                    id: sc.id,
                    name: sc.name,
                    node_id: sc.nodeId,
                    ha_standby_node: sc.haStandby,
                    interface: sc.interface,
                    subnet: sc.subnet,
                    gateway: sc.gateway,
                    enabled: sc.enabled,
                    pool_start: sc.poolStart,
                    pool_end: sc.poolEnd,
                    lease_time_seconds: Number(sc.leaseTime) || 86400,
                    dns_servers: [sc.gateway],
                    domain_name: 'local',
                    authoritative: true
                });
            } catch (e) { console.warn('updateDhcpScope failed:', e); }
            store.notify('dhcp');
        }
    },

    deleteDhcpScope(store, id) {
        store.data.admin.dhcpScopes = store.data.admin.dhcpScopes.filter(s => s.id !== id);
        store.notify('dhcp');
    },

    async convertLeaseToStatic(store, mac, hostname = null) {
        try {
            await api.convertLeaseToStatic(mac, hostname);
            await store.syncWithBackend();
        } catch (e) {
            console.warn('convertLeaseToStatic fallback:', e);
            const lease = store.data.admin.activeLeases.find(l => l.mac === mac);
            let d = store.data.devices.find(x => x.mac === mac);
            if (d && lease) d.staticIp = lease.ip;
            else if (lease) {
                store.data.devices.push({
                    mac: lease.mac,
                    name: hostname || lease.hostname || 'Reserved Device',
                    owner: '',
                    location: 'Living Room',
                    ip: lease.ip,
                    staticIp: lease.ip,
                    zone: 'lan',
                    status: 'online',
                    signal: -50,
                    rxMbps: 0,
                    txMbps: 0,
                    icon: '🖥️',
                    vendor: lease.vendor || 'Hardware'
                });
            }
        }
        store.notify('dhcp');
        store.notify('devices');
    }
};
