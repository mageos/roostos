// Concept 1: SysAdmin Console - Network Interfaces & Cluster Fleet (AGENTS.md compliant)
import { store } from '../state.js';
import { api } from '../api.js';
import { renderDhcpReservations } from './c1-admin-dhcp-reservations.js';
import { renderEdgePeers } from './c1-admin-edge-peers.js';

let activeNodeFilter = 'all';
let addingIngressPos = null; // 'top' | 'bottom' | null
let edgeDiagStatus = null;

function buildIngressAddRow() {
    return `
        <tr class="inline-edit-row" style="background: var(--bg-subtle);">
            <td><input type="text" class="form-input" id="ing-domain" placeholder="plex.example.com" style="padding:5px 8px;font-size:12px;"></td>
            <td><input type="text" class="form-input" id="ing-target-ip" placeholder="192.168.1.50" style="padding:5px 8px;font-size:12px;"></td>
            <td><input type="number" class="form-input" id="ing-target-port" placeholder="32400" value="443" style="padding:5px 8px;font-size:12px;width:90px;"></td>
            <td><label style="font-size:12px;display:flex;align-items:center;gap:6px;"><input type="checkbox" id="ing-ssl" checked> Auto-TLS</label></td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="btn-save-ing">Save</button>
                    <button class="btn btn-secondary btn-sm" id="btn-cancel-ing">Cancel</button>
                </div>
            </td>
        </tr>
    `;
}

export function renderAdminNetwork(container) {
    const data = store.data;
    const admin = data.admin;
    const nodes = data.cluster.nodes;
    const edge = data.edgeGateway;

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

    const vpsDisplay = (edge.vpsHostname && edge.vpsHostname !== '-' && edge.vpsHostname !== edge.vpsPublicIp)
        ? `${edge.vpsHostname} (${edge.vpsPublicIp})`
        : (edge.vpsPublicIp || '-');
    const lanSubnetsStr = (edge.lanSubnets && edge.lanSubnets.length > 0) ? edge.lanSubnets.join(', ') : (data.system.lanSubnet || '192.168.1.0/24');

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
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">☁️ Cloud VPS Edge Gateway (${edge.name || 'CGNAT Bypass Ingress'})</h3>
                    <p class="card-subtitle">Stealth WireGuard tunnel & bidirectional Main LAN ↔ Edge Gateway routing</p>
                </div>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-secondary btn-sm" id="btn-sync-lan-routes" title="Push bidirectional Main LAN ↔ Edge Gateway routes & firewall rules">🔄 Push LAN Routes</button>
                    <button class="btn btn-secondary btn-sm" id="btn-verify-edge" title="Probe live WireGuard handshake, ICMP ping, and peer authentication">🩺 Verify Tunnel & Auth</button>
                    <span class="badge ${edge.enabled ? 'badge-success' : 'badge-neutral'}">● ${edge.tunnelStatus || 'Not Enrolled'}</span>
                </div>
            </div>

            ${edgeDiagStatus ? `
                <div style="margin-bottom: 14px; padding: 10px 14px; border-radius: var(--radius-md); background: var(--bg-subtle); border-left: 4px solid ${edgeDiagStatus.ok ? 'var(--accent-emerald)' : 'var(--accent-amber)'}; font-size: 12px;">
                    <div style="font-weight: 700; margin-bottom: 4px;">${edgeDiagStatus.title}</div>
                    <div style="color: var(--text-muted);">${edgeDiagStatus.detail}</div>
                </div>
            ` : ''}

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Home WAN (Behind CGNAT)</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${edge.cgnatIspIp || data.system.wanIp || '-'}</code></div>
                    <span class="badge badge-warning" style="margin-top: 4px;">RFC6598 Carrier NAT</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Edge VPS Endpoint</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${vpsDisplay}</code></div>
                    <span class="badge ${edge.enabled ? 'badge-success' : 'badge-neutral'}" style="margin-top: 4px;">Static Public Ingress</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">WireGuard Tunnel & LAN Routes</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${edge.localTunnelIp || '-'} ↔ ${edge.vpsTunnelIp || '-'}</code></div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">LAN ↔ Edge: <code>${lanSubnetsStr}</code></div>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Ingress Proxy Data Transfer</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;">Rx: ${edge.rxBytes || '0 B'} / Tx: ${edge.txBytes || '0 B'}</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Handshake: ${edge.handshake || '-'}</div>
                </div>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                <h4 style="font-size: 13px; font-weight: 700; margin: 0;">Active Public Ingress Domain Mappings</h4>
                <button class="btn btn-primary btn-sm" id="btn-add-ingress-top">+ Add Ingress Route</button>
            </div>
            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Public Hostname</th>
                            <th>Internal Target (Home LAN)</th>
                            <th>Target Service</th>
                            <th>SSL / TLS Certificate</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${addingIngressPos === 'top' ? buildIngressAddRow() : ''}
                        ${(edge.ingressRules || []).length === 0 && !addingIngressPos ? `
                            <tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">No Cloud VPS ingress domain mappings configured yet.</td></tr>
                        ` : (edge.ingressRules || []).map(r => `
                            <tr>
                                <td><strong><a href="https://${r.domain}" target="_blank" style="color:var(--brand-primary); text-decoration:none;">${r.domain} ↗</a></strong></td>
                                <td><code>${r.target}</code></td>
                                <td>${r.service}</td>
                                <td><span class="badge badge-success">🔒 ${r.ssl} (${r.expires})</span></td>
                                <td>
                                    <button class="btn btn-danger btn-sm btn-del-ing" data-id="${r.id}">Delete</button>
                                </td>
                            </tr>
                        `).join('')}
                        ${addingIngressPos === 'bottom' ? buildIngressAddRow() : ''}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 10px; display: flex; justify-content: flex-end;">
                <button class="btn btn-secondary btn-sm" id="btn-add-ingress-bottom">+ Add Ingress Route</button>
            </div>
            <div id="edge-peers-container"></div>
        </div>

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

    renderDhcpReservations(container, () => renderAdminNetwork(container));
    const peersContainer = container.querySelector('#edge-peers-container');
    if (peersContainer) {
        renderEdgePeers(peersContainer, () => renderAdminNetwork(container));
    }

    container.querySelector('#btn-goto-dhcp')?.addEventListener('click', () => window.c1SwitchTab('dhcp'));
    container.querySelector('#btn-sync-lan-routes')?.addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = '⏳ Syncing Routes...';
        try {
            const res = await api.syncEdgeLanRoutes();
            edgeDiagStatus = {
                ok: true,
                title: '✓ Bidirectional Main LAN ↔ Edge Gateway Routes Synced',
                detail: `${res.message || 'Routes applied.'} | Subnets: ${(res.lan_subnets || []).join(', ')}`
            };
            await store.syncWithBackend();
        } catch (err) {
            edgeDiagStatus = { ok: false, title: '⚠ Route Sync Failed', detail: String(err.message || err) };
        }
        renderAdminNetwork(container);
    });
    container.querySelector('#btn-verify-edge')?.addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = '⏳ Verifying...';
        try {
            const v = await api.verifyEdgeConnectivity();
            edgeDiagStatus = {
                ok: v.status === 'healthy',
                title: `${v.status === 'healthy' ? '✓' : '⚠'} Connectivity & Auth: ${String(v.status).toUpperCase()} — ${v.message}`,
                detail: `Interface: ${v.interface} (${v.interface_up ? 'UP' : 'DOWN'}) | Handshake: ${v.wg_handshake_ok ? 'OK' : 'Pending'} | Ping: ${v.ping_reachable ? `OK (${v.latency_ms || '<1'} ms)` : 'Unreachable'} | Peer Auth: ${v.auth_valid ? 'VALID' : 'Unverified'} (${v.auth_method}: ${v.auth_detail}) | LAN Routes: ${(v.lan_routes_configured || []).join(', ') || 'none'}`
            };
        } catch (err) {
            edgeDiagStatus = { ok: false, title: '⚠ Verification Probe Failed', detail: String(err.message || err) };
        }
        renderAdminNetwork(container);
    });
    container.querySelector('#btn-add-ingress-top')?.addEventListener('click', () => {
        addingIngressPos = 'top';
        renderAdminNetwork(container);
    });
    container.querySelector('#btn-add-ingress-bottom')?.addEventListener('click', () => {
        addingIngressPos = 'bottom';
        renderAdminNetwork(container);
    });
    container.querySelector('#btn-cancel-ing')?.addEventListener('click', () => {
        addingIngressPos = null;
        renderAdminNetwork(container);
    });
    container.querySelector('#btn-save-ing')?.addEventListener('click', async () => {
        const domain = container.querySelector('#ing-domain')?.value.trim();
        const targetIp = container.querySelector('#ing-target-ip')?.value.trim();
        const targetPort = parseInt(container.querySelector('#ing-target-port')?.value || '443', 10);
        const sslEnabled = container.querySelector('#ing-ssl')?.checked ?? true;
        if (!domain || !targetIp) return;
        try {
            await api.createEdgeRoute({ domain, target_ip: targetIp, target_port: targetPort, ssl_enabled: sslEnabled });
            addingIngressPos = null;
            await store.syncWithBackend();
        } catch (err) {
            console.warn('Failed to create edge route:', err);
        }
    });
    container.querySelectorAll('.btn-del-ing').forEach(btn => {
        btn.onclick = async () => {
            try {
                await api.deleteEdgeRoute(btn.dataset.id);
                await store.syncWithBackend();
            } catch (err) {
                console.warn('Failed to delete edge route:', err);
            }
        };
    });
    container.querySelectorAll('.node-filter').forEach(btn => {
        btn.onclick = () => {
            activeNodeFilter = btn.dataset.node;
            renderAdminNetwork(container);
        };
    });
}
