// Network Zones & VPN Tunnel Interactive SVG Diagram
import { store } from '../state.js';

let selectedDiagramItem = 'zone-lan';

export function renderZoneDiagramSvg(container) {
    const data = store.data;
    const edge = data.edgeGateway;

    const inspectorData = {
        'wg-edge': {
            title: 'Inbound WireGuard Tunnel (wg-edge)',
            badge: 'CGNAT Bypass Ingress',
            badgeClass: 'badge-info',
            ip: '10.42.0.2 ↔ 10.42.0.1 (VPS)',
            flow: 'Internet Users ➔ Cloud VPS (198.51.100.89:443) ➔ wg-edge ➔ Home LAN',
            cipher: 'ChaCha20-Poly1305 (Dark UDP 51820)',
            transfer: `Rx: ${edge.rxBytes} / Tx: ${edge.txBytes}`,
            firewall: 'Target NAT Forward to Home Assistant (192.168.1.50) & Nextcloud'
        },
        'wg-privacy': {
            title: 'Outbound Privacy VPN Tunnel (wg-privacy)',
            badge: 'Whole-Network Egress',
            badgeClass: 'badge-success',
            ip: '10.8.0.45 ↔ ch45.nordvpn.com:51820',
            flow: 'Household Devices ➔ br-lan ➔ wg-privacy ➔ Swiss VPN Exit Gateway',
            cipher: 'ChaCha20-Poly1305 (Kill Switch Active)',
            transfer: 'Rx: 14.8 GB / Tx: 2.1 GB',
            firewall: 'Default Route masquerade via WireGuard endpoint'
        },
        'eth0': {
            title: 'Physical WAN Interface (eth0)',
            badge: 'Residential ISP Uplink',
            badgeClass: 'badge-warning',
            ip: `100.64.14.82/24 (Carrier-Grade NAT)`,
            flow: 'Direct fiber connection to ISP Carrier Network (RFC6598)',
            cipher: 'Unencrypted ISP Transport (Protected by WireGuard)',
            transfer: 'Rx: 14.2 GB / Tx: 3.8 GB (1 Gbps Full Duplex)',
            firewall: 'nftables: DROP all unsolicited inbound; ALLOW established'
        },
        'br-lan': {
            title: 'Linux Bridge Interface (br-lan)',
            badge: 'Core LAN Switch',
            badgeClass: 'badge-success',
            ip: '192.168.1.1/24 (Gateway)',
            flow: 'Bridges physical ports eth1, eth2, and local AP wlan0 into single broadcast domain',
            cipher: 'Local Ethernet / WPA3-Personal',
            transfer: 'Internal Switching: 8.5 GB Rx / 12.1 GB Tx',
            firewall: 'Kea DHCP pool: 192.168.1.100 - 192.168.1.250',
            dhcpScopeId: 'scope-lan',
            dhcpSummary: '192.168.1.100 - 250 (24h lease • 5 active)'
        },
        'zone-lan': {
            title: 'Security Zone: Household LAN (lan)',
            badge: 'Trusted Family Zone',
            badgeClass: 'badge-success',
            ip: '192.168.1.0/24 (br-lan)',
            flow: 'Personal laptops, family phones, entertainment consoles, and local servers',
            cipher: 'WPA3-SAE / Gigabit Ethernet',
            transfer: '8 Registered Devices • Screentime & bedtimes enforced via timeguardd',
            firewall: 'Policy: ACCEPT to WAN, ACCEPT to IoT, ACCEPT to Guest. Free inter-device talk.',
            dhcpScopeId: 'scope-lan',
            dhcpSummary: '192.168.1.100 - 250 (24h lease • 5 active)'
        },
        'zone-iot': {
            title: 'Security Zone: Smart Home IoT (iot)',
            badge: 'Isolated VLAN 20',
            badgeClass: 'badge-warning',
            ip: '192.168.20.0/24 (vlan-iot: ID 20)',
            flow: 'Smart thermostats, Philips Hue, smart fridge, cameras, and IoT sensors',
            cipher: 'WPA2-PSK (2.4GHz Dedicated SSID: RoostHome-IoT)',
            transfer: '3 Active Devices • High security quarantine',
            firewall: 'nftables Policy: DROP to Household LAN; DROP inter-IoT client traffic; Restricted WAN.',
            dhcpScopeId: 'scope-iot',
            dhcpSummary: '192.168.20.100 - 240 (7d lease • 3 active)'
        },
        'zone-guest': {
            title: 'Security Zone: Guest Wi-Fi (guest)',
            badge: 'Isolated VLAN 10',
            badgeClass: 'badge-info',
            ip: '192.168.10.0/24 (vlan-guest: ID 10)',
            flow: 'Visitor phones and guest laptops with QR code onboarding',
            cipher: 'WPA2-PSK (SSID: RoostHome-Guest)',
            transfer: '1 Active Guest Client • Temporary DHCP leases',
            firewall: 'nftables Policy: Client Isolation ON; DROP access to LAN and IoT; WAN NAT Only.',
            dhcpScopeId: 'scope-guest',
            dhcpSummary: '192.168.10.50 - 200 (2h lease • 1 active)'
        }
    };

    const cur = inspectorData[selectedDiagramItem] || inspectorData['zone-lan'];

    container.innerHTML = `
        <div class="zone-diagram-container">
            <svg class="zone-diagram-svg" viewBox="0 0 920 490" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="cloudGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#1e293b"/>
                        <stop offset="100%" stop-color="#0f172a"/>
                    </linearGradient>
                    <linearGradient id="routerGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#1e3a8a"/>
                        <stop offset="100%" stop-color="#1e293b"/>
                    </linearGradient>
                    <linearGradient id="lanGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#064e3b"/>
                        <stop offset="100%" stop-color="#022c22"/>
                    </linearGradient>
                    <linearGradient id="iotGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#78350f"/>
                        <stop offset="100%" stop-color="#451a03"/>
                    </linearGradient>
                    <linearGradient id="guestGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#1e1b4b"/>
                        <stop offset="100%" stop-color="#0f172a"/>
                    </linearGradient>
                </defs>

                <!-- 1. Cloud & Public Internet Area -->
                <rect x="20" y="10" width="880" height="95" rx="16" fill="url(#cloudGrad)" stroke="#334155" stroke-width="1.5"/>
                <text x="40" y="34" fill="#94a3b8" font-size="12" font-weight="700" letter-spacing="0.5">🌐 THE PUBLIC INTERNET & REMOTE CLOUD NODES</text>

                <!-- Cloud VPS Edge Box -->
                <g class="diagram-clickable ${selectedDiagramItem === 'wg-edge' ? 'selected' : ''}" data-item="wg-edge">
                    <rect x="50" y="44" width="280" height="48" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
                    <text x="65" y="64" fill="#ffffff" font-size="13" font-weight="700">☁️ Cloud VPS (vps-edge-01)</text>
                    <text x="65" y="80" fill="#38bdf8" font-size="11" font-family="monospace">Static Public IPv4: 198.51.100.89</text>
                </g>

                <!-- Remote Privacy VPN Exit Box -->
                <g class="diagram-clickable ${selectedDiagramItem === 'wg-privacy' ? 'selected' : ''}" data-item="wg-privacy">
                    <rect x="590" y="44" width="280" height="48" rx="8" fill="#1e293b" stroke="#10b981" stroke-width="1.5"/>
                    <text x="605" y="64" fill="#ffffff" font-size="13" font-weight="700">🔒 NordVPN Swiss Gateway</text>
                    <text x="605" y="80" fill="#10b981" font-size="11" font-family="monospace">Endpoint: ch45.nordvpn.com</text>
                </g>

                <!-- 2. Animated VPN Tunnels Through Internet -->
                <!-- Tunnel 1: Inbound wg-edge (Cyan flow) -->
                <line x1="190" y1="92" x2="190" y2="155" stroke="#38bdf8" stroke-width="4" class="tunnel-flow-in"/>
                <!-- Tunnel label badge -->
                <rect x="90" y="112" width="200" height="22" rx="6" fill="#0284c7" class="diagram-clickable ${selectedDiagramItem === 'wg-edge' ? 'selected' : ''}" data-item="wg-edge"/>
                <text x="190" y="127" fill="#ffffff" font-size="10" font-weight="700" text-anchor="middle">🔒 wg-edge (CGNAT Tunnel)</text>

                <!-- Tunnel 2: Outbound wg-privacy (Green flow) -->
                <line x1="730" y1="92" x2="730" y2="155" stroke="#10b981" stroke-width="4" class="tunnel-flow-out"/>
                <rect x="630" y="112" width="200" height="22" rx="6" fill="#059669" class="diagram-clickable ${selectedDiagramItem === 'wg-privacy' ? 'selected' : ''}" data-item="wg-privacy"/>
                <text x="730" y="127" fill="#ffffff" font-size="10" font-weight="700" text-anchor="middle">🔒 wg-privacy (Egress Tunnel)</text>

                <!-- 3. Gateway Router Box -->
                <rect x="20" y="155" width="880" height="135" rx="16" fill="url(#routerGrad)" stroke="#3b82f6" stroke-width="2"/>
                <text x="40" y="180" fill="#93c5fd" font-size="14" font-weight="800">🛡️ ROOSTOS GATEWAY ROUTER (roost-gateway-01)</text>
                <text x="480" y="180" fill="#94a3b8" font-size="11">Behind CGNAT: 100.64.14.82 • Linux 6.8.0 • nftables • Kea</text>

                <!-- Ports on Gateway -->
                <!-- eth0 WAN Port -->
                <g class="diagram-clickable ${selectedDiagramItem === 'eth0' ? 'selected' : ''}" data-item="eth0">
                    <rect x="40" y="195" width="210" height="42" rx="6" fill="#0f172a" stroke="#f59e0b" stroke-width="1.5"/>
                    <text x="52" y="213" fill="#ffffff" font-size="12" font-weight="700">Port: eth0 (WAN)</text>
                    <text x="52" y="228" fill="#f59e0b" font-size="10" font-family="monospace">100.64.14.82 (CGNAT)</text>
                </g>

                <!-- eth1 and eth2 Internal LAN Ports -->
                <rect x="270" y="195" width="130" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="282" y="213" fill="#ffffff" font-size="11" font-weight="700">Port: eth1 (LAN)</text>
                <text x="282" y="228" fill="#94a3b8" font-size="10">1 Gbps Trunk</text>

                <rect x="415" y="195" width="130" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="427" y="213" fill="#ffffff" font-size="11" font-weight="700">Port: eth2 (LAN)</text>
                <text x="427" y="228" fill="#94a3b8" font-size="10">1 Gbps Trunk</text>

                <!-- wlan0 and wlan1 Radios -->
                <rect x="560" y="195" width="150" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="572" y="213" fill="#ffffff" font-size="11" font-weight="700">Radio: wlan0 (AP)</text>
                <text x="572" y="228" fill="#94a3b8" font-size="10">Wi-Fi 6 AX (5GHz)</text>

                <rect x="725" y="195" width="155" height="42" rx="6" fill="#0f172a" stroke="#64748b" stroke-width="1"/>
                <text x="737" y="213" fill="#ffffff" font-size="11" font-weight="700">Radio: wlan1 (Mesh)</text>
                <text x="737" y="228" fill="#94a3b8" font-size="10">802.11s Backhaul</text>

                <!-- br-lan Bridge Box -->
                <g class="diagram-clickable ${selectedDiagramItem === 'br-lan' ? 'selected' : ''}" data-item="br-lan">
                    <rect x="270" y="248" width="580" height="32" rx="6" fill="#1e293b" stroke="#3b82f6" stroke-width="1.5"/>
                    <text x="285" y="268" fill="#ffffff" font-size="11" font-weight="700">Bridge Interface: br-lan</text>
                    <text x="470" y="268" fill="#93c5fd" font-size="11" font-family="monospace">192.168.1.1/24 (Kea DHCP & DNS)</text>
                </g>

                <!-- Lines from eth1/eth2 to br-lan -->
                <line x1="335" y1="237" x2="335" y2="248" stroke="#3b82f6" stroke-width="2"/>
                <line x1="480" y1="237" x2="480" y2="248" stroke="#3b82f6" stroke-width="2"/>

                <!-- 4. Downlink Network Zones -->
                <!-- Lines feeding into Zones -->
                <line x1="160" y1="280" x2="160" y2="320" stroke="#10b981" stroke-width="2.5"/>
                <line x1="460" y1="280" x2="460" y2="320" stroke="#f59e0b" stroke-width="2.5"/>
                <line x1="760" y1="280" x2="760" y2="320" stroke="#818cf8" stroke-width="2.5"/>

                <!-- ZONE 1: Household LAN -->
                <g class="diagram-clickable ${selectedDiagramItem === 'zone-lan' ? 'selected' : ''}" data-item="zone-lan">
                    <rect x="20" y="320" width="280" height="150" rx="12" fill="url(#lanGrad)" stroke="#10b981" stroke-width="2"/>
                    <text x="35" y="344" fill="#6ee7b7" font-size="14" font-weight="800">🟢 ZONE: HOUSEHOLD LAN</text>
                    <text x="35" y="364" fill="#ffffff" font-size="11" font-family="monospace">Subnet: 192.168.1.0/24 (br-lan)</text>
                    <text x="35" y="382" fill="#94a3b8" font-size="11">Firewall: ALLOW WAN, IoT & Guest</text>
                    <text x="35" y="400" fill="#34d399" font-size="11" font-weight="600">📱 8 Devices Online (Laptops/Phones/TV)</text>
                    <rect x="35" y="415" width="250" height="26" rx="4" fill="#065f46"/>
                    <text x="45" y="432" fill="#a7f3d0" font-size="10">Dad iPhone, Mom Mac, Alice iPad, NAS</text>
                </g>

                <!-- ZONE 2: Smart Home IoT (VLAN 20) -->
                <g class="diagram-clickable ${selectedDiagramItem === 'zone-iot' ? 'selected' : ''}" data-item="zone-iot">
                    <rect x="320" y="320" width="280" height="150" rx="12" fill="url(#iotGrad)" stroke="#f59e0b" stroke-width="2"/>
                    <text x="335" y="344" fill="#fcd34d" font-size="14" font-weight="800">🟡 ZONE: SMART HOME IOT</text>
                    <text x="335" y="364" fill="#ffffff" font-size="11" font-family="monospace">VLAN 20: 192.168.20.0/24 (vlan-iot)</text>
                    <text x="335" y="382" fill="#f87171" font-size="11" font-weight="700">🚫 Firewall: DROP Access to LAN</text>
                    <text x="335" y="400" fill="#fbbf24" font-size="11" font-weight="600">💡 3 Isolated Smart Devices</text>
                    <rect x="335" y="415" width="250" height="26" rx="4" fill="#92400e"/>
                    <text x="345" y="432" fill="#fef3c7" font-size="10">Ecobee, Smart Fridge, Hue Bridge</text>
                </g>

                <!-- ZONE 3: Guest Wi-Fi (VLAN 10) -->
                <g class="diagram-clickable ${selectedDiagramItem === 'zone-guest' ? 'selected' : ''}" data-item="zone-guest">
                    <rect x="620" y="320" width="280" height="150" rx="12" fill="url(#guestGrad)" stroke="#818cf8" stroke-width="2"/>
                    <text x="635" y="344" fill="#a5b4fc" font-size="14" font-weight="800">🔵 ZONE: GUEST WI-FI</text>
                    <text x="635" y="364" fill="#ffffff" font-size="11" font-family="monospace">VLAN 10: 192.168.10.0/24 (vlan-guest)</text>
                    <text x="635" y="382" fill="#c7d2fe" font-size="11">Firewall: Client Isolation (WAN Only)</text>
                    <text x="635" y="400" fill="#a5b4fc" font-size="11" font-weight="600">👥 1 Guest Client Connected</text>
                    <rect x="635" y="415" width="250" height="26" rx="4" fill="#312e81"/>
                    <text x="645" y="432" fill="#e0e7ff" font-size="10">Guest iPhone 13 (QR Onboarded)</text>
                </g>
            </svg>
        </div>

        <!-- Interactive Diagram Inspector Card -->
        <div class="card" style="border-left: 4px solid var(--brand-primary); margin-top: 16px;">
            <div class="card-header">
                <div>
                    <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);">
                        SELECTED DIAGRAM ELEMENT
                    </div>
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
                    <span style="color: var(--text-muted); font-size: 11px;">Encryption / Cipher:</span><br>
                    <strong>${cur.cipher}</strong>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <span style="color: var(--text-muted); font-size: 11px;">Traffic Throughput:</span><br>
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
        if (store.currentConcept === 'concept1') {
            store.concept1Persona = 'admin';
            window.c1SwitchTab('dhcp');
        } else {
            const btn = document.querySelector('[data-c2="connectivity"]');
            if (btn) btn.click();
        }
    });

    container.querySelectorAll('.diagram-clickable').forEach(el => {
        el.onclick = () => {
            selectedDiagramItem = el.dataset.item;
            renderZoneDiagramSvg(container);
        };
    });
}
