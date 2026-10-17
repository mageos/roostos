// Backend Synchronization Helper for RoostOS StateStore
import { api } from './api.js';

export async function syncStateWithBackend(data, notify) {
    try {
        const [
            pulse, sysConfig, healthReport, people, devData,
            netConfig, clusterStatus, guestWifi, shields,
            scopes, leases, reservations, portForwards, dnsRecords
        ] = await Promise.allSettled([
            api.getHouseholdPulse(),
            api.getSystem(),
            api.getSystemHealth(),
            api.getFamilyPeople(),
            api.getDevices(),
            api.getNetwork(),
            api.getClusterStatus(),
            api.getGuestWifi(),
            api.getSecurityShields(),
            api.getDhcpScopes(),
            api.getDhcpLeases(),
            api.getDhcpReservations(),
            api.getPortForwards(),
            api.getDnsRecords(),
        ]);

        // 1. System & Live Hardware Telemetry
        if (pulse.status === 'fulfilled' && pulse.value) {
            const p = pulse.value;
            data.system.hostname = p.hostname || data.system.hostname;
            data.system.version = p.version || data.system.version;
            data.system.uptime = p.uptime || data.system.uptime;
            data.system.wanIp = p.wan_ip || data.system.wanIp;
            data.system.gatewayIp = p.gateway_ip || data.system.gatewayIp;
            data.system.ispName = p.isp_name || data.system.ispName;
            data.system.downloadMbps = p.download_mbps ?? data.system.downloadMbps;
            data.system.uploadMbps = p.upload_mbps ?? data.system.uploadMbps;
            data.system.pingMs = p.ping_ms ?? data.system.pingMs;
            data.system.unassignedDeviceAlert = p.unassigned_device_alert ?? false;
            data.system.unassignedDevice = p.unassigned_device || null;
            if (p.cpu_percent !== undefined) data.system.cpuPercent = p.cpu_percent;
            if (p.ram_percent !== undefined) data.system.ramPercent = p.ram_percent;
            if (p.cpu_cores !== undefined) data.system.cpuCores = p.cpu_cores;
            if (p.kernel_version) data.system.kernelVersion = p.kernel_version;
            if (p.ram_total_gb !== undefined) data.system.ramTotalGb = p.ram_total_gb;
            if (p.ram_used_gb !== undefined) data.system.ramUsedGb = p.ram_used_gb;
            if (p.temp_c !== undefined) data.system.tempC = p.temp_c;
        }

        if (sysConfig.status === 'fulfilled' && sysConfig.value) {
            const sc = sysConfig.value;
            data.system.hostname = sc.hostname || data.system.hostname;
            data.system.domain = sc.domain || data.system.domain;
            if (sc.stats?.uptime) data.system.uptime = sc.stats.uptime;
            if (sc.stats?.wan_ip && sc.stats.wan_ip !== '-') data.system.wanIp = sc.stats.wan_ip;
            if (sc.stats?.lan_ip && sc.stats.lan_ip !== '-') data.system.gatewayIp = sc.stats.lan_ip;
            if (sc.stats?.cpu_load !== undefined) data.system.cpuPercent = sc.stats.cpu_load;
            if (sc.stats?.ram_usage !== undefined) data.system.ramPercent = sc.stats.ram_usage;
            data.system.warnings = sc.stats?.warnings || [];
        }

        if (healthReport.status === 'fulfilled' && healthReport.value?.telemetry) {
            const t = healthReport.value.telemetry;
            if (t.cpu_load) data.system.cpuPercent = t.cpu_load;
            if (t.ram_usage) data.system.ramPercent = t.ram_usage;
            if (t.uptime_str && t.uptime_str !== 'Unknown') data.system.uptime = t.uptime_str;
        }

        // 2. Family & Household Members
        if (people.status === 'fulfilled' && Array.isArray(people.value)) {
            data.people = people.value.map(p => ({
                id: p.id,
                name: p.name,
                role: p.role,
                color: p.color || '#3b82f6',
                avatar: p.avatar || (p.role === 'kid' ? '🧒' : '👤'),
                screentimeLimit: p.screentime_limit_minutes || 0,
                screentimeUsed: p.screentime_used_minutes || 0,
                bedtimeStart: p.bedtime?.start_time || '20:30',
                bedtimeEnd: p.bedtime?.end_time || '06:30',
                bedtimeActive: p.bedtime?.active_now || false,
                filterLevel: p.filter_level || 'Standard',
                deviceCount: p.device_count || (p.devices || []).length,
            }));
        }

        // 3. Network Devices (Configured Profiles + Live Discovered Clients)
        if (devData.status === 'fulfilled' && devData.value) {
            const registered = devData.value.devices || [];
            const activeArp = devData.value.active_arp || [];
            const activeLeases = devData.value.active_leases || (leases.status === 'fulfilled' ? leases.value : []) || [];
            const onlineMacs = new Set(activeArp.map(a => (a.mac || '').toLowerCase()));
            const seenMacs = new Set();
            const deviceList = [];

            for (const d of registered) {
                const normMac = (d.mac || '').toLowerCase();
                seenMacs.add(normMac);
                const matchingArp = activeArp.find(a => (a.mac || '').toLowerCase() === normMac);
                const matchingLease = activeLeases.find(l => (l.mac || '').toLowerCase() === normMac);
                deviceList.push({
                    mac: d.mac,
                    name: d.name,
                    owner: d.owner || '',
                    location: d.location || '',
                    ip: d.static_ip || matchingArp?.ip || matchingLease?.ip || '-',
                    staticIp: d.static_ip || '',
                    tags: d.tags || ['personal'],
                    zone: (d.tags || []).includes('iot') ? 'iot' : ((d.tags || []).includes('guest') ? 'guest' : 'lan'),
                    status: onlineMacs.has(normMac) ? 'online' : 'offline',
                    signal: -50, rxMbps: 0, txMbps: 0,
                    icon: (d.tags || []).includes('laptop') ? '💻' : ((d.tags || []).includes('iot') ? '💡' : '📱'),
                    vendor: matchingLease?.vendor || 'Hardware Client',
                    isRegistered: true,
                });
            }

            for (const client of [...activeArp, ...activeLeases]) {
                const mac = (client.mac || '').toLowerCase();
                if (!mac || mac === '00:00:00:00:00:00' || seenMacs.has(mac)) continue;
                seenMacs.add(mac);
                const matchingLease = activeLeases.find(l => (l.mac || '').toLowerCase() === mac);
                const matchingArp = activeArp.find(a => (a.mac || '').toLowerCase() === mac);
                const vendor = matchingLease?.vendor || 'Network Device';
                const name = matchingLease?.hostname || matchingArp?.hostname || (vendor !== 'Network Device' ? `${vendor} Client` : `Device ${mac.slice(-5)}`);
                const lower = `${name} ${vendor}`.toLowerCase();
                const icon = lower.includes('laptop') || lower.includes('macbook') || lower.includes('pc') ? '💻'
                    : lower.includes('tv') || lower.includes('roku') ? '📺'
                    : lower.includes('pad') || lower.includes('tablet') ? '📲'
                    : lower.includes('switch') || lower.includes('playstation') || lower.includes('xbox') ? '🎮'
                    : lower.includes('thermostat') || lower.includes('plug') || lower.includes('cam') ? '💡' : '📱';

                deviceList.push({
                    mac: client.mac, name, owner: '', location: '',
                    ip: client.ip || matchingLease?.ip || matchingArp?.ip || '-',
                    staticIp: '', tags: ['discovered', 'unregistered'],
                    zone: 'lan', status: 'online', signal: -50, rxMbps: 0, txMbps: 0,
                    icon, vendor, isRegistered: false,
                });
            }
            data.devices = deviceList;
        }

        // 4. Network Interfaces & Wi-Fi
        if (netConfig.status === 'fulfilled' && netConfig.value?.network) {
            const net = netConfig.value.network;
            data.admin.network.interfaces = (net.interfaces || []).map(i => ({
                name: i.name, role: i.role || 'unassigned', ip: i.ip || '-',
                gateway: i.gateway || '-', mac: i.mac || '-', mtu: i.mtu || 1500,
                status: i.status || 'unknown', speed: i.speed || 'Unknown'
            }));
            data.admin.bridgesVlans = (net.bridges || []).map(b => ({
                name: b.name, type: 'Bridge', ip: b.ip || '-',
                ports: (b.interfaces || []).join(', ') || '-', dhcp: 'Active (Kea)', isolate: b.isolate || false
            }));
            const wifiAps = netConfig.value.wifi?.access_points || [];
            if (wifiAps.length > 0) {
                data.wifiNetworks = wifiAps.map(ap => ({
                    ssid: ap.ssid, band: ap.band || 'Dual-Band (2.4/5GHz)',
                    security: ap.security || 'WPA2/WPA3-Personal', clients: 0,
                    channel: ap.channel || 'Auto', status: ap.enabled !== false ? 'Active' : 'Disabled',
                    isolate: ap.isolate || false, qr: ap.passphrase ? `WIFI:S:${ap.ssid};T:WPA;P:${ap.passphrase};;` : ''
                }));
            }
        }

        // 5. Cluster & Fleet Nodes
        if (clusterStatus.status === 'fulfilled' && clusterStatus.value) {
            const cs = clusterStatus.value;
            const rawNodes = cs.nodes || [];
            if (rawNodes.length > 0) {
                data.cluster.nodes = rawNodes.map(n => ({
                    id: n.id || n.name, hostname: n.name || n.id || data.system.hostname,
                    role: (n.roles || ['gateway_router']).map(r => r === 'gateway_router' ? 'Edge Gateway Router' : r).join(', '),
                    ip: n.management_ip || data.system.gatewayIp,
                    status: cs.is_controller ? 'Master' : 'Online', model: 'RoostOS Node',
                    cpu: data.system.cpuPercent, ram: `${data.system.ramPercent}%`,
                    temp: `${data.system.tempC || 38}°C`, uptime: data.system.uptime,
                    interfaces: (n.interfaces || []).map(i => ({ name: i.name, role: i.mode || i.type || 'LAN', status: 'UP' })),
                    services: ['roostos-web', 'roostos-engine', 'kea-dhcp4', 'nftables']
                }));
            } else {
                data.cluster.nodes = [{
                    id: cs.node_id || "node-01", hostname: cs.node_name || data.system.hostname,
                    role: "Edge Gateway Router", ip: data.system.gatewayIp,
                    status: "Master", model: "RoostOS Router", cpu: data.system.cpuPercent,
                    ram: `${data.system.ramPercent}%`, temp: `${data.system.tempC || 38}°C`, uptime: data.system.uptime,
                    interfaces: (data.admin.network.interfaces || []).slice(0, 5).map(i => ({ name: i.name, role: i.role || 'LAN', status: i.status || 'UP' })),
                    services: ['roostos-web', 'roostos-engine', 'systemd-networkd', 'kea-dhcp4', 'nftables']
                }];
            }
        }

        // 6. Guest Wi-Fi
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

        // 7. Security Shields
        if (shields.status === 'fulfilled' && shields.value) {
            const s = shields.value;
            data.protection.adBlocking.enabled = s.ad_blocking_enabled;
            data.protection.adBlocking.blockedToday = s.ad_blocking_blocked_today;
            data.protection.adBlocking.queriesToday = s.ad_blocking_queries_today;
            data.protection.safeSearch.enabled = s.safe_search_enabled;
            data.protection.malwareProtection.enabled = s.threat_defense_enabled;
            data.protection.vpnTunnel.enabled = s.privacy_vpn_enabled;
        }

        // 8. DHCP Scopes, Leases, and Reservations
        if (scopes.status === 'fulfilled' && Array.isArray(scopes.value)) {
            data.admin.dhcpScopes = scopes.value.map(sc => ({
                id: sc.id, name: sc.name, nodeId: sc.node_id,
                haStandby: sc.ha_standby_node || 'none', interface: sc.interface,
                subnet: sc.subnet, gateway: sc.gateway, enabled: sc.enabled,
                poolStart: sc.pool_start, poolEnd: sc.pool_end, leaseTime: String(sc.lease_time_seconds),
                leaseTimeHuman: `${Math.round(sc.lease_time_seconds / 3600)} Hours`,
                dnsServers: (sc.dns_servers || []).join(', '), domainName: sc.domain_name,
                authoritative: sc.authoritative, activeLeasesCount: sc.active_leases_count, poolSize: sc.pool_size,
            }));
        }

        if (leases.status === 'fulfilled' && Array.isArray(leases.value)) {
            data.admin.activeLeases = leases.value.map(l => ({
                ip: l.ip, mac: l.mac, hostname: l.hostname || 'Unknown',
                network: l.network_interface || 'lan',
                expires: `${Math.round(l.expires_in_seconds / 3600)}h ${Math.round((l.expires_in_seconds % 3600) / 60)}m`,
                vendor: l.vendor || 'Network Device',
            }));
        }

        if (reservations.status === 'fulfilled' && Array.isArray(reservations.value)) {
            data.admin.dhcpReservations = reservations.value.map(r => ({
                id: r.id || r.mac, mac: r.mac, ip: r.ip, hostname: r.hostname || '', description: r.description || ''
            }));
        }

        // 9. Firewall Port Forwards & DNS Records
        if (portForwards.status === 'fulfilled' && Array.isArray(portForwards.value)) {
            data.admin.portForwards = portForwards.value.map(pf => ({
                id: pf.name.toLowerCase().replace(/\s+/g, '-'), name: pf.name,
                proto: (pf.protocol || 'TCP').toUpperCase(), wanPort: pf.external_port || pf.wan_port || 0,
                lanIp: pf.internal_ip || pf.lan_ip || '', lanPort: pf.internal_port || pf.lan_port || 0,
                hits: 0, enabled: pf.enabled ?? true,
            }));
        }

        if (dnsRecords.status === 'fulfilled' && Array.isArray(dnsRecords.value)) {
            data.admin.dnsRecords = dnsRecords.value.map(r => ({
                id: r.id || r.domain.toLowerCase().replace(/\s+/g, '-'),
                domain: r.domain, type: r.type || 'A', ip: r.ip,
            }));
        }

        notify('sync');
    } catch (err) {
        console.warn('Backend sync failed, using cached state:', err);
    }
}
