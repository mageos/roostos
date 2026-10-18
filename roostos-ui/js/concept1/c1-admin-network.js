// Concept 1: SysAdmin Console - Network Interfaces & Cluster Fleet (AGENTS.md compliant)
import { store } from '../state.js';
import { renderDhcpReservations } from './c1-admin-dhcp-reservations.js';
import { renderEdgeGatewayCard } from './c1-admin-edge-gateway.js';

let activeNodeFilter = 'all';

export function renderAdminNetwork(container) {
    const data = store.data;
    const admin = data.admin;
    const nodes = data.cluster.nodes;

    let displayedInterfaces = [];
    if (activeNodeFilter === 'all') {
        (nodes || []).forEach(n => {
            (n.interfaces || []).forEach(i => displayedInterfaces.push({ ...i, nodeName: n.hostname, nodeRole: n.role }));
        });
        if (displayedInterfaces.length === 0 && admin.network.interfaces.length > 0) {
            displayedInterfaces = admin.network.interfaces.map(i => ({
                ...i, nodeName: data.system.hostname, nodeRole: 'Edge Gateway Router'
            }));
        }
    } else {
        const found = (nodes || []).find(n => n.id === activeNodeFilter);
        if (found) {
            displayedInterfaces = (found.interfaces || []).map(i => ({ ...i, nodeName: found.hostname, nodeRole: found.role }));
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

        <!-- Cloud VPS Edge Gateway Container -->
        <div id="edge-gateway-container"></div>

        <!-- Cluster Fleet Node Interfaces -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🔌 Cluster Fleet Network Interfaces</h3>
                    <p class="card-subtitle">Inspect and control physical and virtual adapters across all cluster nodes</p>
                </div>
            </div>

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
                        ${displayedInterfaces.length === 0 ? `
                            <tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--text-muted);">No network interfaces detected.</td></tr>
                        ` : displayedInterfaces.map(i => `
                            <tr>
                                <td><strong>${i.nodeName}</strong><div style="font-size:11px;color:var(--text-muted);">${i.nodeRole}</div></td>
                                <td><code>${i.name}</code></td>
                                <td><span class="badge ${String(i.role).toLowerCase().includes('wan') ? 'badge-info' : String(i.role).toLowerCase().includes('tunnel') ? 'badge-warning' : 'badge-neutral'}">${i.role}</span></td>
                                <td>${i.speed}</td>
                                <td><code>${i.ip}</code></td>
                                <td>${i.mtu}</td>
                                <td>${i.rxBytes || '0 B'} / ${i.txBytes || '0 B'}</td>
                                <td><span class="badge ${i.status === 'UP' ? 'badge-success' : 'badge-neutral'}">${i.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    const edgeContainer = container.querySelector('#edge-gateway-container');
    if (edgeContainer) {
        renderEdgeGatewayCard(edgeContainer, () => renderAdminNetwork(container));
    }
    renderDhcpReservations(container, () => renderAdminNetwork(container));

    container.querySelector('#btn-goto-dhcp')?.addEventListener('click', () => window.c1SwitchTab('dhcp'));
    container.querySelectorAll('.node-filter').forEach(btn => {
        btn.onclick = () => {
            activeNodeFilter = btn.dataset.node;
            renderAdminNetwork(container);
        };
    });
}
