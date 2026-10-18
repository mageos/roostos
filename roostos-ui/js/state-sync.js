// Backend Synchronization Helper for RoostOS StateStore
import { api } from './api.js';

export async function syncStateWithBackend(data, notify) {
    try {
        const [
            pulse, sysConfig, healthReport, people, devData, netConfig, clusterStatus, guestWifi, shields,
            blockedFeed, scopes, leases, reservations, portForwards, dnsRecords, dnsConfig, sysServices, stateBundle, edgeStatus
        ] = await Promise.allSettled([
            api.getHouseholdPulse(), api.getSystem(), api.getSystemHealth(), api.getFamilyPeople(), api.getDevices(),
            api.getNetwork(), api.getClusterStatus(), api.getGuestWifi(), api.getSecurityShields(), api.getBlockedThreatFeed(),
            api.getDhcpScopes(), api.getDhcpLeases(), api.getDhcpReservations(), api.getPortForwards(), api.getDnsRecords(),
            api.getDnsConfig(), api.getSystemServices(), api.getStateBundle(), api.getEdgeStatus()
        ]);

        if (pulse.status === 'fulfilled' && pulse.value) {
            const p = pulse.value;
            Object.assign(data.system, {
                hostname: p.hostname || data.system.hostname, version: p.version || data.system.version,
                uptime: p.uptime || data.system.uptime, wanIp: p.wan_ip || data.system.wanIp,
                gatewayIp: p.gateway_ip || data.system.gatewayIp, ispName: p.isp_name || data.system.ispName,
                downloadMbps: p.download_mbps ?? data.system.downloadMbps, uploadMbps: p.upload_mbps ?? data.system.uploadMbps,
                pingMs: p.ping_ms ?? data.system.pingMs, unassignedDeviceAlert: p.unassigned_device_alert ?? false,
                unassignedDevice: p.unassigned_device || null,
            });
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
            if (t.cpu_load !== undefined) data.system.cpuPercent = t.cpu_load;
            if (t.ram_usage !== undefined) data.system.ramPercent = t.ram_usage;
            if (t.uptime_str && t.uptime_str !== 'Unknown') data.system.uptime = t.uptime_str;
        }

        if (people.status === 'fulfilled' && Array.isArray(people.value)) {
            data.people = people.value.map(p => ({
                id: p.id, name: p.name, role: p.role, color: p.color || '#3b82f6',
                avatar: p.avatar || (p.role === 'kid' ? '🧒' : '👤'),
                screentimeLimit: p.screentime_limit_minutes || 0, screentimeUsed: p.screentime_used_minutes || 0,
                bedtimeStart: p.bedtime?.start_time || '20:30', bedtimeEnd: p.bedtime?.end_time || '06:30',
                bedtimeActive: p.bedtime?.active_now || false, filterLevel: p.filter_level || 'Standard',
                deviceCount: p.device_count || (p.devices || []).length,
            }));
        }

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
                    mac: d.mac, name: d.name, owner: d.owner || '', location: d.location || '',
                    ip: d.static_ip || matchingArp?.ip || matchingLease?.ip || '-',
                    staticIp: d.static_ip || '', tags: d.tags || ['personal'],
                    zone: (d.tags || []).includes('iot') ? 'iot' : ((d.tags || []).includes('guest') ? 'guest' : 'lan'),
                    status: onlineMacs.has(normMac) ? 'online' : 'offline',
                    signal: -50, rxMbps: 0, txMbps: 0,
                    icon: (d.tags || []).includes('laptop') ? '💻' : ((d.tags || []).includes('iot') ? '💡' : '📱'),
                    vendor: matchingLease?.vendor || 'Hardware Client', isRegistered: true,
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

        if (netConfig.status === 'fulfilled' && netConfig.value?.network) {
            const net = netConfig.value.network;
            data.admin.network.interfaces = (net.interfaces || []).map(i => ({
                name: i.name, role: i.role || 'unassigned', ip: i.ip || '-',
                gateway: i.gateway || '-', mac: i.mac || '-', mtu: i.mtu || 1500,
                status: i.status || 'unknown', speed: i.speed || 'Unknown',
                rxBytes: i.rx_bytes || '0 B', txBytes: i.tx_bytes || '0 B'
            }));
            data.admin.bridgesVlans = (net.bridges || []).map(b => ({
                name: b.name, type: 'Bridge', ip: b.ip || '-',
                ports: (b.interfaces || []).join(', ') || '-', dhcp: 'Active (Kea)', isolate: b.isolate || false
            }));
            data.wifiNetworks = (netConfig.value.wifi?.access_points || []).map(ap => ({
                ssid: ap.ssid, band: ap.band || 'Dual-Band (2.4/5GHz)',
                security: ap.security || 'WPA2/WPA3-Personal', clients: 0,
                channel: ap.channel || 'Auto', status: ap.enabled !== false ? 'Active' : 'Disabled',
                isolate: ap.isolate || false, qr: ap.passphrase ? `WIFI:S:${ap.ssid};T:WPA;P:${ap.passphrase};;` : ''
            }));
        }

        const activeServiceNames = (sysServices.status === 'fulfilled' && Array.isArray(sysServices.value))
            ? sysServices.value.filter(s => s.status === 'active').map(s => s.id || s.service)
            : ['roostos-web', 'roostos-engine', 'systemd-networkd', 'kea-dhcp4', 'nftables'];
        if (sysServices.status === 'fulfilled' && Array.isArray(sysServices.value)) {
            data.admin.systemServices = sysServices.value;
        }

        if (clusterStatus.status === 'fulfilled' && clusterStatus.value) {
            const cs = clusterStatus.value;
            const rawNodes = cs.nodes || [];
            const fallbackIfaces = data.admin.network.interfaces || [];
            if (rawNodes.length > 0) {
                data.cluster.nodes = rawNodes.map(n => ({
                    id: n.id || n.name, hostname: n.name || n.id || data.system.hostname,
                    role: (n.roles || ['gateway_router']).map(r => r === 'gateway_router' ? 'Edge Gateway Router' : r).join(', '),
                    ip: n.management_ip || data.system.gatewayIp,
                    status: cs.is_controller ? 'Master' : 'Online', model: data.system.kernelVersion || 'RoostOS Node',
                    cpu: data.system.cpuPercent, ram: `${data.system.ramPercent}%`,
                    temp: `${data.system.tempC || 0}°C`, uptime: data.system.uptime,
                    interfaces: (n.interfaces && n.interfaces.length > 0)
                        ? n.interfaces.map(i => {
                            const live = fallbackIfaces.find(f => f.name === i.name) || {};
                            return {
                                name: i.name, role: i.mode || i.type || live.role || 'LAN',
                                ip: i.ip || live.ip || '-', speed: i.speed || live.speed || 'Unknown',
                                mtu: i.mtu || live.mtu || 1500, status: live.status || 'UP',
                                mac: i.mac || live.mac || '-', rxBytes: live.rxBytes || '0 B', txBytes: live.txBytes || '0 B'
                            };
                        }) : fallbackIfaces,
                    services: activeServiceNames
                }));
            } else {
                data.cluster.nodes = [{
                    id: cs.node_id || data.system.hostname || "node-01",
                    hostname: cs.node_name || data.system.hostname,
                    role: "Edge Gateway Router", ip: data.system.gatewayIp,
                    status: "Master", model: data.system.kernelVersion || "RoostOS Router",
                    cpu: data.system.cpuPercent, ram: `${data.system.ramPercent}%`,
                    temp: `${data.system.tempC || 0}°C`, uptime: data.system.uptime,
                    interfaces: fallbackIfaces, services: activeServiceNames
                }];
            }
        }

        if (guestWifi.status === 'fulfilled' && guestWifi.value) {
            const gw = guestWifi.value;
            const guestNet = data.wifiNetworks.find(w => w.ssid.includes('Guest') || w.isolate);
            if (guestNet) {
                guestNet.ssid = gw.ssid; guestNet.status = gw.enabled ? 'Active' : 'Disabled';
                guestNet.clients = gw.clients_count; guestNet.qr = gw.qr_payload;
            }
        }

        if (shields.status === 'fulfilled' && shields.value) {
            const s = shields.value;
            data.protection.adBlocking.enabled = s.ad_blocking_enabled;
            data.protection.adBlocking.blockedToday = s.ad_blocking_blocked_today;
            data.protection.adBlocking.queriesToday = s.ad_blocking_queries_today;
            data.protection.safeSearch.enabled = s.safe_search_enabled;
            data.protection.malwareProtection.enabled = s.threat_defense_enabled;
            data.protection.malwareProtection.blockedToday = s.threat_defense_drops_today;
            data.protection.vpnTunnel.enabled = s.privacy_vpn_enabled;
            data.protection.vpnTunnel.endpoint = s.privacy_vpn_endpoint || 'Not configured';
        }

        if (blockedFeed.status === 'fulfilled' && Array.isArray(blockedFeed.value)) {
            data.blockedRequests = blockedFeed.value.map(b => ({
                id: b.id, time: b.timestamp || 'Recent', client: b.client_name || b.client_ip,
                clientIp: b.client_ip, target: b.target, subsystem: b.subsystem,
                category: b.category, rule: b.rule, actionTaken: b.action_taken,
                zone: b.zone || 'wan', canAllow: b.can_allow ?? false,
                canBonus: b.can_bonus ?? false, allowed: b.allowed ?? false
            }));
        }

        if (scopes.status === 'fulfilled' && Array.isArray(scopes.value)) {
            data.admin.dhcpScopes = scopes.value.map(sc => ({
                id: sc.id, name: sc.name, nodeId: sc.node_id, haStandby: sc.ha_standby_node || 'none',
                interface: sc.interface, subnet: sc.subnet, gateway: sc.gateway, enabled: sc.enabled,
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
                id: r.id || r.mac, mac: r.mac, ip: r.ip || r.reserved_ip,
                hostname: r.hostname || '', description: r.description || ''
            }));
        }

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

        if (dnsConfig.status === 'fulfilled' && dnsConfig.value) {
            data.admin.dnsForwarders = dnsConfig.value.forwarders || ['1.1.1.1', '8.8.8.8'];
        }

        if (stateBundle.status === 'fulfilled' && stateBundle.value?.files) {
            data.admin.yamlFiles = stateBundle.value.files;
        }

        if (edgeStatus.status === 'fulfilled' && edgeStatus.value) {
            const es = edgeStatus.value;
            const gw = (es.gateways && es.gateways[0]) || null;
            if (es.linked && gw) {
                Object.assign(data.edgeGateway, {
                    enabled: true, name: gw.name || 'VPS Edge Gateway',
                    cgnatIspIp: data.system.wanIp || '-', vpsPublicIp: gw.public_ip || '-',
                    vpsHostname: gw.domain || gw.public_ip || '-',
                    localTunnelIp: (gw.tunnel_ip_home || '10.42.0.2/24').split('/')[0],
                    vpsTunnelIp: (gw.tunnel_ip_gateway || '10.42.0.1/24').split('/')[0],
                    tunnelSubnet: gw.tunnel_ip_home || '10.42.0.0/24',
                    tunnelPort: gw.listen_port || 51820,
                    tunnelStatus: gw.status === 'connected' ? 'Connected & Active' : (gw.status || 'Configured'),
                    handshake: gw.last_handshake || 'Active',
                    rxBytes: es.rx_bytes || data.edgeGateway.rxBytes || '0 B',
                    txBytes: es.tx_bytes || data.edgeGateway.txBytes || '0 B',
                    lanSubnets: gw.lan_subnets || es.lan_subnets || [],
                    ingressRules: (gw.ingress_routes || []).map(r => ({
                        id: r.id, domain: r.domain, target: `${r.target_ip}:${r.target_port}`,
                        targetIp: r.target_ip, targetPort: r.target_port,
                        service: `Target ${r.target_ip}:${r.target_port}`,
                        ssl: r.ssl_enabled ? `TLS (${r.ssl_status || 'valid'})` : 'HTTP Only',
                        expires: 'Auto-Renew', enabled: true,
                    })),
                    peers: gw.peers || []
                });
            } else {
                data.edgeGateway.enabled = false;
                data.edgeGateway.cgnatIspIp = data.system.wanIp || '-';
                data.edgeGateway.lanSubnets = es.lan_subnets || [];
            }
        }

        notify('sync');
    } catch (err) {
        console.warn('Backend sync failed, using cached state:', err);
    }
}
