// Network Zones & VPN Tunnel Interactive SVG Diagram
import { store } from '../state.js';

let selectedDiagramItem = 'zone-lan';

export function renderZoneDiagramSvg(container) {
    const data = store.data;
    const sys = data.system;
    const edge = data.edgeGateway;
    const vpn = data.protection.vpnTunnel;
    const ifaces = data.admin.network.interfaces || [];
    const bridges = data.admin.bridgesVlans || [];
    const scopes = data.admin.dhcpScopes || [];
    const devices = data.devices || [];

    const wanIface = ifaces.find(i => i.role === 'wan') || ifaces[0] || { name: 'eth0', ip: sys.wanIp || '-', speed: 'Unknown' };
    const lanIfaces = ifaces.filter(i => i.name !== wanIface.name);
    const port1 = lanIfaces[0] || { name: 'eth1', role: 'lan', speed: 'Not Present' };
    const port2 = lanIfaces[1] || { name: 'eth2', role: 'lan', speed: 'Not Present' };
    const mainBridge = bridges[0] || { name: 'br-lan', ip: sys.gatewayIp !== '-' ? `${sys.gatewayIp}/24` : 'Not Configured' };
    const lanScope = scopes.find(s => s.interface === mainBridge.name || s.id === 'scope-lan') || scopes[0];
    const iotScope = scopes.find(s => s.id.includes('iot') || s.interface.includes('iot'));
    const guestScope = scopes.find(s => s.id.includes('guest') || s.interface.includes('guest'));

    const lanDevices = devices.filter(d => d.zone === 'lan' || !d.zone);
    const iotDevices = devices.filter(d => d.zone === 'iot');
    const guestDevices = devices.filter(d => d.zone === 'guest');

    const formatDeviceNames = (list) => list.length > 0
        ? list.slice(0, 4).map(d => d.name).join(', ')
        : 'No active devices in this zone';

    const inspectorData = {
        'wg-edge': {
            title: `Inbound WireGuard Tunnel (wg-edge)`,
            badge: edge.enabled ? (edge.tunnelStatus || 'Tunnel Active') : 'Not Configured',
            badgeClass: edge.enabled ? 'badge-info' : 'badge-neutral',
            ip: `${edge.localTunnelIp || '-'} ↔ ${edge.vpsTunnelIp || '-'} (${edge.vpsHostname || edge.vpsPublicIp || '-'})`,
            flow: edge.enabled ? `Internet ➔ Edge VPS (${edge.vpsHostname || edge.vpsPublicIp}:${edge.tunnelPort || 51820}) ➔ wg-edge ➔ Home LAN` : 'Edge Gateway tunnel is not currently enabled',
            cipher: 'WireGuard ChaCha20-Poly1305',
            transfer: `Rx: ${edge.rxBytes} / Tx: ${edge.txBytes}`,
            firewall: `Inbound DNAT forwarding (${(edge.ingressRules || []).length} active ingress routes)`
        },
        'wg-privacy': {
            title: 'Outbound Privacy VPN Tunnel (wg-privacy)',
            badge: vpn.enabled ? 'Whole-Network Egress' : 'Disabled',
            badgeClass: vpn.enabled ? 'badge-success' : 'badge-neutral',
            ip: vpn.endpoint || 'Not configured',
            flow: vpn.enabled ? `Household Devices ➔ ${mainBridge.name} ➔ wg-privacy ➔ ${vpn.endpoint}` : 'Direct ISP routing (Privacy VPN disabled)',
            cipher: vpn.enabled ? 'WireGuard ChaCha20-Poly1305' : 'None',
            transfer: vpn.enabled ? 'Active Tunnel' : '0 B',
            firewall: 'Outbound NAT masquerade'
        },
        'eth0': {
            title: `Physical WAN Interface (${wanIface.name})`,
            badge: wanIface.status === 'UP' ? 'Active Uplink' : 'Interface',
            badgeClass: wanIface.status === 'UP' ? 'badge-success' : 'badge-warning',
            ip: wanIface.ip !== '-' ? wanIface.ip : (sys.wanIp || 'Unassigned'),
            flow: `Primary upstream network interface (${wanIface.name})`,
            cipher: 'Standard IP Transport',
            transfer: `Link Speed: ${wanIface.speed || 'Unknown'} (MTU ${wanIface.mtu || 1500})`,
            firewall: 'nftables: DROP unsolicited inbound; ALLOW established/related'
        },
        'br-lan': {
            title: `Linux Bridge Interface (${mainBridge.name})`,
            badge: 'Core LAN Switch',
            badgeClass: 'badge-success',
            ip: mainBridge.ip,
            flow: `Bridges local ports (${mainBridge.ports || 'none'}) into broadcast domain`,
            cipher: 'Local Ethernet / Wi-Fi',
            transfer: `${lanDevices.length} Connected Devices`,
            firewall: lanScope ? `Kea DHCP pool: ${lanScope.poolStart} - ${lanScope.poolEnd}` : 'DHCP scope not configured',
            dhcpScopeId: lanScope?.id || '',
            dhcpSummary: lanScope ? `${lanScope.poolStart} - ${lanScope.poolEnd} (${lanScope.activeLeasesCount} active)` : 'No active DHCP scope'
        },
        'zone-lan': {
            title: 'Security Zone: Household LAN (lan)',
            badge: 'Trusted Family Zone',
            badgeClass: 'badge-success',
            ip: lanScope ? `${lanScope.subnet} (${mainBridge.name})` : mainBridge.ip,
            flow: 'Personal laptops, family phones, workstations, and local servers',
            cipher: 'Local LAN',
            transfer: `${lanDevices.length} Discovered / Registered Devices`,
            firewall: 'Policy: ACCEPT to WAN, IoT, and Guest zones.',
            dhcpScopeId: lanScope?.id || '',
            dhcpSummary: lanScope ? `${lanScope.poolStart} - ${lanScope.poolEnd} (${lanScope.activeLeasesCount} active)` : ''
        },
        'zone-iot': {
            title: 'Security Zone: Smart Home IoT (iot)',
            badge: iotScope ? 'Isolated VLAN' : 'Not Configured',
            badgeClass: iotScope ? 'badge-warning' : 'badge-neutral',
            ip: iotScope ? `${iotScope.subnet} (${iotScope.interface})` : 'No IoT VLAN configured',
            flow: 'Smart thermostats, sensors, appliances, and cameras',
            cipher: 'WPA2/WPA3 / VLAN Tagged',
            transfer: `${iotDevices.length} Active IoT Devices`,
            firewall: 'nftables Policy: DROP to Household LAN; Restricted WAN.',
            dhcpScopeId: iotScope?.id || '',
            dhcpSummary: iotScope ? `${iotScope.poolStart} - ${iotScope.poolEnd} (${iotScope.activeLeasesCount} active)` : ''
        },
        'zone-guest': {
            title: 'Security Zone: Guest Wi-Fi (guest)',
            badge: guestScope ? 'Isolated VLAN' : 'Not Configured',
            badgeClass: guestScope ? 'badge-info' : 'badge-neutral',
            ip: guestScope ? `${guestScope.subnet} (${guestScope.interface})` : 'No Guest VLAN configured',
            flow: 'Visitor phones and guest laptops with client isolation',
            cipher: 'WPA2-Personal',
            transfer: `${guestDevices.length} Active Guest Clients`,
            firewall: 'nftables Policy: Client Isolation ON; DROP access to LAN and IoT.',
            dhcpScopeId: guestScope?.id || '',
            dhcpSummary: guestScope ? `${guestScope.poolStart} - ${guestScope.poolEnd} (${guestScope.activeLeasesCount} active)` : ''
        }
    };

    const cur = inspectorData[selectedDiagramItem] || inspectorData['zone-lan'];

    container.innerHTML = `
        <div class="zone-diagram-container">
            <svg class="zone-diagram-svg" viewBox="0 0 920 490" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="cloudGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1e293b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
                    <linearGradient id="routerGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1e3a8a"/><stop offset="100%" stop-color="#1e293b"/></linearGradient>
                    <linearGradient id="lanGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#064e3b"/><stop offset="100%" stop-color="#022c22"/></linearGradient>
                    <linearGradient id="iotGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#78350f"/><stop offset="100%" stop-color="#451a03"/></linearGradient>
                    <linearGradient id="guestGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1e1b4b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
                </defs>

                <!-- 1. Cloud & Public Internet Area -->
                <rect x="20" y="10" width="880" height="95" rx="16" fill="url(#cloudGrad)" stroke="#334155" stroke-width="1.5"/>
                <text x="40" y="34" fill="#94a3b8" font-size="12" font-weight="700" letter-spacing="0.5">🌐 UPSTREAM NETWORK & OPTIONAL VPN TUNNELS</text>

                <g class="diagram-clickable ${selectedDiagramItem === 'wg-edge' ? 'selected' : ''}" data-item="wg-edge">
                    <rect x="50" y="44" width="280" height="48" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
                    <text x="65" y="64" fill="#ffffff" font-size="13" font-weight="700">☁️ ${edge.name || 'Edge Gateway'} (${edge.enabled ? 'Active' : 'Disabled'})</text>
                    <text x="65" y="80" fill="#38bdf8" font-size="11" font-family="monospace">Endpoint: ${edge.enabled ? (edge.vpsHostname !== '-' ? edge.vpsHostname : edge.vpsPublicIp) : 'Not Configured'}</text>
                </g>

                <g class="diagram-clickable ${selectedDiagramItem === 'wg-privacy' ? 'selected' : ''}" data-item="wg-privacy">
                    <rect x="590" y="44" width="280" height="48" rx="8" fill="#1e293b" stroke="#10b981" stroke-width="1.5"/>
                    <text x="605" y="64" fill="#ffffff" font-size="13" font-weight="700">🔒 Privacy VPN (${vpn.enabled ? 'Active' : 'Disabled'})</text>
                    <text x="605" y="80" fill="#10b981" font-size="11" font-family="monospace">Endpoint: ${vpn.endpoint || 'Not configured'}</text>
                </g>

                <line x1="190" y1="92" x2="190" y2="155" stroke="#38bdf8" stroke-width="4" class="tunnel-flow-in"/>
                <rect x="90" y="112" width="200" height="22" rx="6" fill="#0284c7" class="diagram-clickable ${selectedDiagramItem === 'wg-edge' ? 'selected' : ''}" data-item="wg-edge"/>
                <text x="190" y="127" fill="#ffffff" font-size="10" font-weight="700" text-anchor="middle">🔒 wg-edge (${edge.enabled ? `${edge.localTunnelIp} ↔ ${edge.vpsTunnelIp}` : 'Off'})</text>

                <line x1="730" y1="92" x2="730" y2="155" stroke="#10b981" stroke-width="4" class="tunnel-flow-out"/>
                <rect x="630" y="112" width="200" height="22" rx="6" fill="#059669" class="diagram-clickable ${selectedDiagramItem === 'wg-privacy' ? 'selected' : ''}" data-item="wg-privacy"/>
                <text x="730" y="127" fill="#ffffff" font-size="10" font-weight="700" text-anchor="middle">🔒 wg-privacy (${vpn.enabled ? 'Active' : 'Off'})</text>

                <!-- 3. Gateway Router Box -->
                <rect x="20" y="155" width="880" height="135" rx="16" fill="url(#routerGrad)" stroke="#3b82f6" stroke-width="2"/>
                <text x="40" y="180" fill="#93c5fd" font-size="14" font-weight="800">🛡️ ROOSTOS GATEWAY ROUTER (${sys.hostname})</text>
                <text x="480" y="180" fill="#94a3b8" font-size="11">IP: ${sys.wanIp} • ${sys.kernelVersion || 'Linux'} • nftables • Kea</text>

                <g class="diagram-clickable ${selectedDiagramItem === 'eth0' ? 'selected' : ''}" data-item="eth0">
                    <rect x="40" y="195" width="210" height="42" rx="6" fill="#0f172a" stroke="#f59e0b" stroke-width="1.5"/>
                    <text x="52" y="213" fill="#ffffff" font-size="12" font-weight="700">Port: ${wanIface.name} (${(wanIface.role || 'WAN').toUpperCase()})</text>
                    <text x="52" y="228" fill="#f59e0b" font-size="10" font-family="monospace">${wanIface.ip !== '-' ? wanIface.ip : sys.wanIp}</text>
                </g>

                <rect x="270" y="195" width="130" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="282" y="213" fill="#ffffff" font-size="11" font-weight="700">Port: ${port1.name}</text>
                <text x="282" y="228" fill="#94a3b8" font-size="10">${port1.speed || 'Interface'}</text>

                <rect x="415" y="195" width="130" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="427" y="213" fill="#ffffff" font-size="11" font-weight="700">Port: ${port2.name}</text>
                <text x="427" y="228" fill="#94a3b8" font-size="10">${port2.speed || 'Interface'}</text>

                <rect x="560" y="195" width="320" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="572" y="213" fill="#ffffff" font-size="11" font-weight="700">Wireless Access Points (${data.wifiNetworks.length} Configured)</text>
                <text x="572" y="228" fill="#94a3b8" font-size="10">${data.wifiNetworks.map(w => w.ssid).join(', ') || 'No Wi-Fi Radios Configured'}</text>

                <g class="diagram-clickable ${selectedDiagramItem === 'br-lan' ? 'selected' : ''}" data-item="br-lan">
                    <rect x="270" y="248" width="610" height="32" rx="6" fill="#1e293b" stroke="#3b82f6" stroke-width="1.5"/>
                    <text x="285" y="268" fill="#ffffff" font-size="11" font-weight="700">Bridge / LAN: ${mainBridge.name}</text>
                    <text x="470" y="268" fill="#93c5fd" font-size="11" font-family="monospace">${mainBridge.ip} (Gateway: ${sys.gatewayIp})</text>
                </g>

                <line x1="335" y1="237" x2="335" y2="248" stroke="#3b82f6" stroke-width="2"/>
                <line x1="480" y1="237" x2="480" y2="248" stroke="#3b82f6" stroke-width="2"/>

                <!-- 4. Downlink Network Zones -->
                <line x1="160" y1="280" x2="160" y2="320" stroke="#10b981" stroke-width="2.5"/>
                <line x1="460" y1="280" x2="460" y2="320" stroke="#f59e0b" stroke-width="2.5"/>
                <line x1="760" y1="280" x2="760" y2="320" stroke="#818cf8" stroke-width="2.5"/>

                <g class="diagram-clickable ${selectedDiagramItem === 'zone-lan' ? 'selected' : ''}" data-item="zone-lan">
                    <rect x="20" y="320" width="280" height="150" rx="12" fill="url(#lanGrad)" stroke="#10b981" stroke-width="2"/>
                    <text x="35" y="344" fill="#6ee7b7" font-size="14" font-weight="800">🟢 ZONE: HOUSEHOLD LAN</text>
                    <text x="35" y="364" fill="#ffffff" font-size="11" font-family="monospace">Subnet: ${lanScope ? lanScope.subnet : mainBridge.ip}</text>
                    <text x="35" y="382" fill="#94a3b8" font-size="11">Firewall: ALLOW WAN, IoT & Guest</text>
                    <text x="35" y="400" fill="#34d399" font-size="11" font-weight="600">📱 ${lanDevices.length} Devices Connected</text>
                    <rect x="35" y="415" width="250" height="26" rx="4" fill="#065f46"/>
                    <text x="45" y="432" fill="#a7f3d0" font-size="10">${formatDeviceNames(lanDevices)}</text>
                </g>

                <g class="diagram-clickable ${selectedDiagramItem === 'zone-iot' ? 'selected' : ''}" data-item="zone-iot">
                    <rect x="320" y="320" width="280" height="150" rx="12" fill="url(#iotGrad)" stroke="#f59e0b" stroke-width="2"/>
                    <text x="335" y="344" fill="#fcd34d" font-size="14" font-weight="800">🟡 ZONE: SMART HOME IOT</text>
                    <text x="335" y="364" fill="#ffffff" font-size="11" font-family="monospace">${iotScope ? `${iotScope.subnet} (${iotScope.interface})` : 'Not Configured'}</text>
                    <text x="335" y="382" fill="#f87171" font-size="11" font-weight="700">🚫 Firewall: DROP Access to LAN</text>
                    <text x="335" y="400" fill="#fbbf24" font-size="11" font-weight="600">💡 ${iotDevices.length} Isolated Smart Devices</text>
                    <rect x="335" y="415" width="250" height="26" rx="4" fill="#92400e"/>
                    <text x="345" y="432" fill="#fef3c7" font-size="10">${formatDeviceNames(iotDevices)}</text>
                </g>

                <g class="diagram-clickable ${selectedDiagramItem === 'zone-guest' ? 'selected' : ''}" data-item="zone-guest">
                    <rect x="620" y="320" width="280" height="150" rx="12" fill="url(#guestGrad)" stroke="#818cf8" stroke-width="2"/>
                    <text x="635" y="344" fill="#a5b4fc" font-size="14" font-weight="800">🔵 ZONE: GUEST WI-FI</text>
                    <text x="635" y="364" fill="#ffffff" font-size="11" font-family="monospace">${guestScope ? `${guestScope.subnet} (${guestScope.interface})` : 'Not Configured'}</text>
                    <text x="635" y="382" fill="#c7d2fe" font-size="11">Firewall: Client Isolation (WAN Only)</text>
                    <text x="635" y="400" fill="#a5b4fc" font-size="11" font-weight="600">👥 ${guestDevices.length} Guest Clients Connected</text>
                    <rect x="635" y="415" width="250" height="26" rx="4" fill="#312e81"/>
                    <text x="645" y="432" fill="#e0e7ff" font-size="10">${formatDeviceNames(guestDevices)}</text>
                </g>
            </svg>
        </div>

        <div class="card" style="border-left: 4px solid var(--brand-primary); margin-top: 16px;">
            <div class="card-header">
                <div>
                    <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);">SELECTED DIAGRAM ELEMENT</div>
                    <h3 class="card-title" style="margin-top: 4px;">${cur.title}</h3>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    ${cur.dhcpScopeId ? `<button class="btn btn-primary btn-sm" id="btn-inspect-dhcp">Configure DHCP →</button>` : ''}
                    <span class="badge ${cur.badgeClass}">${cur.badge}</span>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; font-size: 13px;">
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <span style="color: var(--text-muted); font-size: 11px;">IP / Subnet Allocation:</span><br>
                    <strong><code>${cur.ip}</code></strong>
                </div>
                ${cur.dhcpSummary ? `
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                        <span style="color: var(--text-muted); font-size: 11px;">Kea DHCP Dynamic Pool:</span><br>
                        <strong><code>${cur.dhcpSummary}</code></strong>
                    </div>
                ` : ''}
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <span style="color: var(--text-muted); font-size: 11px;">Encryption / Transport:</span><br>
                    <strong>${cur.cipher}</strong>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <span style="color: var(--text-muted); font-size: 11px;">Status / Devices:</span><br>
                    <strong>${cur.transfer}</strong>
                </div>
            </div>

            <div style="margin-top: 12px; padding: 12px; background: var(--bg-subtle); border-radius: var(--radius-md); font-size: 12px;">
                <span style="color: var(--text-muted);">Packet Flow & Routing:</span> <strong>${cur.flow}</strong><br>
                <span style="color: var(--text-muted);">Firewall Policy:</span> <strong>${cur.firewall}</strong>
            </div>
        </div>
    `;

    container.querySelector('#btn-inspect-dhcp')?.addEventListener('click', () => {
        store.concept1Persona = 'admin';
        window.c1SwitchTab('dhcp');
    });

    container.querySelectorAll('.diagram-clickable').forEach(el => {
        el.onclick = () => {
            selectedDiagramItem = el.dataset.item;
            renderZoneDiagramSvg(container);
        };
    });
}
