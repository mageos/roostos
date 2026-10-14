// Concept 2: Unified Topology - Multi-Node Connectivity, Wi-Fi & Edge Tunnels
import { store } from '../state.js';
import { renderC2DhcpScopes } from './c2-dhcp-scopes.js';

let activeConnNode = 'all';

export function renderConnectivityView(container) {
    const data = store.data;
    const isExpert = store.concept2Density === 'expert';
    const edge = data.edgeGateway;
    const nodes = data.cluster.nodes;

    let displayedInterfaces = [];
    if (activeConnNode === 'all') {
        nodes.forEach(n => {
            n.interfaces.forEach(i => displayedInterfaces.push({ ...i, nodeName: n.hostname, nodeRole: n.role }));
        });
    } else {
        const found = nodes.find(n => n.id === activeConnNode);
        if (found) {
            displayedInterfaces = found.interfaces.map(i => ({ ...i, nodeName: found.hostname, nodeRole: found.role }));
        }
    }

    container.innerHTML = `
        <!-- Cloud VPS Edge Gateway (CGNAT Bypass) -->
        <div class="card" style="border-left: 4px solid var(--brand-primary);">
            <div class="card-header">
                <div>
                    <h3 class="card-title">☁️ Cloud VPS Edge Gateway (CGNAT Bypass)</h3>
                    <p class="card-subtitle">Zero-exposure WireGuard tunnel mapping public static IP to internal home LAN</p>
                </div>
                <span class="badge badge-success">● ${edge.tunnelStatus}</span>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Residential ISP IP</div>
                    <div style="font-size: 14px; font-weight: 700;"><code>${edge.cgnatIspIp}</code></div>
                    <span class="badge badge-warning" style="margin-top: 4px;">CGNAT (No Inbound Ports)</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">VPS Public Static IPv4</div>
                    <div style="font-size: 14px; font-weight: 700;"><code>${edge.vpsPublicIp}</code></div>
                    <span class="badge badge-success" style="margin-top: 4px;">Static Edge Ingress</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">WireGuard Stealth Tunnel</div>
                    <div style="font-size: 14px; font-weight: 700;"><code>10.42.0.1 ↔ 10.42.0.2</code></div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Handshake: ${edge.handshake}</div>
                </div>
            </div>

            <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 8px;">Active Ingress Reverse Proxy Domains</h4>
            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Public Hostname</th>
                            <th>Internal Target</th>
                            <th>Target Service</th>
                            <th>SSL Certificate</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${edge.ingressRules.map(r => `
                            <tr>
                                <td><strong><a href="https://${r.domain}" target="_blank" style="color:var(--brand-primary); text-decoration:none;">${r.domain} ↗</a></strong></td>
                                <td><code>${r.target}</code></td>
                                <td>${r.service}</td>
                                <td><span class="badge badge-success">🔒 ${r.ssl}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Multi-Node Cluster Network Adapters -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🔌 Cluster Fleet Network Adapters</h3>
                    <p class="card-subtitle">Inspect physical and virtual interfaces across all nodes in the home cluster</p>
                </div>
            </div>

            <!-- Cluster Node Switcher Pills -->
            <div class="c1-nav-tabs" style="margin-bottom: 14px;">
                <button class="c1-nav-link c2-node-btn ${activeConnNode === 'all' ? 'active' : ''}" data-node="all">
                    🌐 All Fleet Nodes (${nodes.length})
                </button>
                ${nodes.map(n => `
                    <button class="c1-nav-link c2-node-btn ${activeConnNode === n.id ? 'active' : ''}" data-node="${n.id}">
                        ${n.role.includes('Cloud') ? '☁️' : n.role.includes('Gateway') ? '🛡️' : n.role.includes('Mesh') ? '📶' : '🖥️'} ${n.hostname}
                    </button>
                `).join('')}
            </div>

            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Host Node</th>
                            <th>Interface</th>
                            <th>Role / Type</th>
                            <th>Speed / Duplex</th>
                            <th>Assigned IP</th>
                            ${isExpert ? '<th>MTU</th><th>QoS / Scheduler</th>' : ''}
                            <th>State</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${displayedInterfaces.map(i => `
                            <tr>
                                <td><strong>${i.nodeName}</strong><div style="font-size:11px;color:var(--text-muted);">${i.nodeRole}</div></td>
                                <td><code>${i.name}</code></td>
                                <td><span class="badge ${i.role.includes('WAN') ? 'badge-info' : i.role.includes('Tunnel') ? 'badge-warning' : 'badge-neutral'}">${i.role}</span></td>
                                <td>${i.speed}</td>
                                <td><code>${i.ip}</code></td>
                                ${isExpert ? `
                                    <td>${i.mtu}</td>
                                    <td><span class="badge badge-info">${i.role.includes('WAN') ? 'CAKE (diffserv4)' : 'Default'}</span></td>
                                ` : ''}
                                <td><span class="badge badge-success">${i.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Wireless APs & Mesh Radios -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📶 Wi-Fi Radios & 802.11s Mesh</h3>
                    <p class="card-subtitle">Access point configuration and wireless mesh backhaul</p>
                </div>
            </div>

            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Network SSID</th>
                            <th>Frequency Band</th>
                            <th>Security</th>
                            <th>Clients</th>
                            <th>Channel</th>
                            <th>Isolation</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.wifiNetworks.map(w => `
                            <tr>
                                <td><strong>${w.ssid}</strong></td>
                                <td>${w.band}</td>
                                <td><span class="badge badge-info">${w.security}</span></td>
                                <td><strong>${w.clients}</strong></td>
                                <td><code>${w.channel}</code></td>
                                <td><span class="badge ${w.isolate ? 'badge-warning' : 'badge-success'}">${w.isolate ? 'Isolated' : 'Bridged'}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    // Append modular DHCP Scopes Component
    renderC2DhcpScopes(container, () => renderConnectivityView(container));

    container.querySelectorAll('.c2-node-btn').forEach(btn => {
        btn.onclick = () => {
            activeConnNode = btn.dataset.node;
            renderConnectivityView(container);
        };
    });
}
