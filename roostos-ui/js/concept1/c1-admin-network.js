// Concept 1: SysAdmin Console - Network Interfaces & Cluster Fleet (AGENTS.md compliant)
import { store } from '../state.js';
import { renderDhcpReservations } from './c1-admin-dhcp-reservations.js';

let activeNodeFilter = 'all';

export function renderAdminNetwork(container) {
    const data = store.data;
    const admin = data.admin;
    const nodes = data.cluster.nodes;
    const edge = data.edgeGateway;

    // Filter interfaces by selected cluster node
    let displayedInterfaces = [];
    if (activeNodeFilter === 'all') {
        nodes.forEach(n => {
            n.interfaces.forEach(i => displayedInterfaces.push({ ...i, nodeName: n.hostname, nodeRole: n.role }));
        });
    } else {
        const found = nodes.find(n => n.id === activeNodeFilter);
        if (found) {
            displayedInterfaces = found.interfaces.map(i => ({ ...i, nodeName: found.hostname, nodeRole: found.role }));
        }
    }

    container.innerHTML = `
        <!-- DHCP Scopes Quick Link & Status Card -->
        <div class="card" style="border-left: 4px solid var(--accent-emerald);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h3 class="card-title">📡 Kea DHCP Scopes & Dynamic Pools (${admin.dhcpScopes.length} Networks)</h3>
                    <p class="card-subtitle">Dynamic IP pools, gateways, lease timers, and DNS delivered for Household LAN, Guest, and IoT</p>
                </div>
                <button class="btn btn-primary btn-sm" id="btn-goto-dhcp">Configure DHCP Scopes →</button>
            </div>
        </div>

        <!-- Cloud VPS Edge Gateway (CGNAT Bypass) -->
        <div class="card" style="border-left: 4px solid var(--brand-primary);">
            <div class="card-header">
                <div>
                    <h3 class="card-title">☁️ Cloud VPS Edge Gateway (CGNAT Bypass Ingress)</h3>
                    <p class="card-subtitle">Stealth WireGuard tunnel providing a static public IPv4 for home services behind CGNAT</p>
                </div>
                <span class="badge badge-success">● ${edge.tunnelStatus}</span>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Home WAN (Behind CGNAT)</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${edge.cgnatIspIp}</code></div>
                    <span class="badge badge-warning" style="margin-top: 4px;">RFC6598 Carrier NAT</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Edge VPS Static Public IP</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${edge.vpsPublicIp}</code></div>
                    <span class="badge badge-success" style="margin-top: 4px;">Static Public Ingress</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">WireGuard Stealth Tunnel</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>10.42.0.1 ↔ 10.42.0.2</code></div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Dark UDP Port: 51820</div>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Ingress Proxy Data Transfer</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;">Rx: ${edge.rxBytes} / Tx: ${edge.txBytes}</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Handshake: ${edge.handshake}</div>
                </div>
            </div>

            <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 8px;">Active Public Ingress Domain Mappings</h4>
            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Public Hostname</th>
                            <th>Internal Target (Home LAN)</th>
                            <th>Target Service</th>
                            <th>SSL / TLS Certificate</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${edge.ingressRules.map(r => `
                            <tr>
                                <td><strong><a href="https://${r.domain}" target="_blank" style="color:var(--brand-primary); text-decoration:none;">${r.domain} ↗</a></strong></td>
                                <td><code>${r.target}</code></td>
                                <td>${r.service}</td>
                                <td><span class="badge badge-success">🔒 ${r.ssl} (${r.expires})</span></td>
                                <td><span class="badge badge-success">Live Proxy</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Cluster Fleet Node Interfaces -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🔌 Cluster Fleet Network Interfaces</h3>
                    <p class="card-subtitle">Inspect and control physical and virtual adapters across all cluster nodes</p>
                </div>
            </div>

            <!-- Cluster Node Filter Pills -->
            <div class="c1-nav-tabs" style="margin-bottom: 14px;">
                <button class="c1-nav-link node-filter ${activeNodeFilter === 'all' ? 'active' : ''}" data-node="all">
                    🌐 All Fleet Nodes (${nodes.length})
                </button>
                ${nodes.map(n => `
                    <button class="c1-nav-link node-filter ${activeNodeFilter === n.id ? 'active' : ''}" data-node="${n.id}">
                        ${n.role.includes('Gateway') ? '🛡️' : n.role.includes('Cloud') ? '☁️' : n.role.includes('Mesh') ? '📶' : '🖥️'} ${n.hostname}
                    </button>
                `).join('')}
            </div>

            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Node Hostname</th>
                            <th>Interface</th>
                            <th>Role</th>
                            <th>Speed / Duplex</th>
                            <th>IP Address</th>
                            <th>MTU</th>
                            <th>Traffic (Rx / Tx)</th>
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
                                <td>${i.mtu}</td>
                                <td>${i.rxBytes} / ${i.txBytes}</td>
                                <td><span class="badge badge-success">${i.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    // Append Static DHCP Reservations Table (modular AGENTS.md component)
    renderDhcpReservations(container, () => renderAdminNetwork(container));

    // Event handlers
    container.querySelector('#btn-goto-dhcp')?.addEventListener('click', () => {
        window.c1SwitchTab('dhcp');
    });

    container.querySelectorAll('.node-filter').forEach(btn => {
        btn.onclick = () => {
            activeNodeFilter = btn.dataset.node;
            renderAdminNetwork(container);
        };
    });
}
