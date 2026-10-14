// Backend Synchronization Helper for RoostOS StateStore
import { api } from './api.js';

export async function syncStateWithBackend(data, notify) {
    try {
        const [pulse, people, devData, guestWifi, shields, scopes, leases] = await Promise.allSettled([
            api.getHouseholdPulse(),
            api.getFamilyPeople(),
            api.getDevices(),
            api.getGuestWifi(),
            api.getSecurityShields(),
            api.getDhcpScopes(),
            api.getDhcpLeases(),
        ]);

        if (pulse.status === 'fulfilled' && pulse.value) {
            const p = pulse.value;
            data.system.hostname = p.hostname || data.system.hostname;
            data.system.version = p.version || data.system.version;
            data.system.uptime = p.uptime || data.system.uptime;
            data.system.wanIp = p.wan_ip || data.system.wanIp;
            data.system.gatewayIp = p.gateway_ip || data.system.gatewayIp;
            data.system.ispName = p.isp_name || data.system.ispName;
            data.system.downloadMbps = p.download_mbps || data.system.downloadMbps;
            data.system.uploadMbps = p.upload_mbps || data.system.uploadMbps;
            data.system.pingMs = p.ping_ms || data.system.pingMs;
            data.system.unassignedDeviceAlert = p.unassigned_device_alert;
        }

        if (people.status === 'fulfilled' && Array.isArray(people.value) && people.value.length) {
            data.people = people.value.map(p => ({
                id: p.id,
                name: p.name,
                role: p.role,
                color: p.color || '#3b82f6',
                avatar: p.avatar || '👤',
                screentimeLimit: p.screentime_limit_minutes,
                screentimeUsed: p.screentime_used_minutes,
                bedtimeStart: p.bedtime?.start_time || '20:30',
                bedtimeEnd: p.bedtime?.end_time || '06:30',
                bedtimeActive: p.bedtime?.active_now || false,
                filterLevel: p.filter_level || 'Standard',
                deviceCount: p.device_count || (p.devices || []).length,
            }));
        }

        if (devData.status === 'fulfilled' && devData.value?.devices) {
            const liveDevs = devData.value.devices;
            const activeArp = devData.value.active_arp || [];
            const onlineMacs = new Set(activeArp.map(a => a.mac.toLowerCase()));

            data.devices = liveDevs.map(d => {
                const normMac = d.mac.toLowerCase();
                const isOnline = onlineMacs.has(normMac);
                const matchingArp = activeArp.find(a => a.mac.toLowerCase() === normMac);
                const ip = d.static_ip || (matchingArp ? matchingArp.ip : '192.168.1.100');
                return {
                    mac: d.mac,
                    name: d.name,
                    owner: d.owner || '',
                    location: d.location || 'Living Room',
                    ip: ip,
                    staticIp: d.static_ip || '',
                    tags: d.tags || ['personal'],
                    zone: (d.tags || []).includes('iot') ? 'iot' : ((d.tags || []).includes('guest') ? 'guest' : 'lan'),
                    status: isOnline ? 'online' : 'offline',
                    signal: -50,
                    rxMbps: 1.2,
                    txMbps: 0.2,
                    icon: (d.tags || []).includes('laptop') ? '💻' : ((d.tags || []).includes('iot') ? '💡' : '📱'),
                    vendor: 'Hardware Client',
                };
            });
        }

        if (guestWifi.status === 'fulfilled' && guestWifi.value) {
            const gw = guestWifi.value;
            const guestNet = data.wifiNetworks.find(w => w.ssid.includes('Guest') || w.isolate);
            if (guestNet) {
                guestNet.ssid = gw.ssid;
                guestNet.status = gw.enabled ? 'Active' : 'Disabled';
                guestNet.clients = gw.clients_count;
                guestNet.qr = gw.qr_payload;
            }
        }

        if (shields.status === 'fulfilled' && shields.value) {
            const s = shields.value;
            data.protection.adBlocking.enabled = s.ad_blocking_enabled;
            data.protection.adBlocking.blockedToday = s.ad_blocking_blocked_today;
            data.protection.adBlocking.queriesToday = s.ad_blocking_queries_today;
            data.protection.safeSearch.enabled = s.safe_search_enabled;
            data.protection.malwareProtection.enabled = s.threat_defense_enabled;
            data.protection.vpnTunnel.enabled = s.privacy_vpn_enabled;
        }

        if (scopes.status === 'fulfilled' && Array.isArray(scopes.value) && scopes.value.length) {
            data.admin.dhcpScopes = scopes.value.map(sc => ({
                id: sc.id,
                name: sc.name,
                nodeId: sc.node_id,
                haStandby: sc.ha_standby_node || 'none',
                interface: sc.interface,
                subnet: sc.subnet,
                gateway: sc.gateway,
                enabled: sc.enabled,
                poolStart: sc.pool_start,
                poolEnd: sc.pool_end,
                leaseTime: String(sc.lease_time_seconds),
                leaseTimeHuman: `${Math.round(sc.lease_time_seconds / 3600)} Hours`,
                dnsServers: (sc.dns_servers || []).join(', '),
                domainName: sc.domain_name,
                authoritative: sc.authoritative,
                activeLeasesCount: sc.active_leases_count,
                poolSize: sc.pool_size,
            }));
        }

        if (leases.status === 'fulfilled' && Array.isArray(leases.value) && leases.value.length) {
            data.admin.activeLeases = leases.value.map(l => ({
                ip: l.ip,
                mac: l.mac,
                hostname: l.hostname,
                network: l.network_interface,
                expires: `${Math.round(l.expires_in_seconds / 3600)}h ${Math.round((l.expires_in_seconds % 3600) / 60)}m`,
                vendor: l.vendor || 'Network Device',
            }));
        }

        notify('sync');
    } catch (err) {
        console.warn('Backend sync failed, using cached state:', err);
    }
}
