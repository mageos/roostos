// Concept 1: SysAdmin Console - Cloud VPS Edge Gateway Card (AGENTS.md compliant)
import { store } from '../state.js';
import { api } from '../api.js';
import { renderEdgePeers } from './c1-admin-edge-peers.js';
import { renderVpnServers } from './c1-admin-vpn-servers.js';

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

export function renderEdgeGatewayCard(container, onRefresh) {
    const data = store.data;
    const edge = data.edgeGateway || {};
    const card = document.createElement('div');
    card.className = 'card';
    card.style.borderLeft = '4px solid var(--brand-primary)';

    const vpsDisplay = (edge.vpsHostname && edge.vpsHostname !== '-' && edge.vpsHostname !== edge.vpsPublicIp)
        ? `${edge.vpsHostname} (${edge.vpsPublicIp})`
        : (edge.vpsPublicIp || '-');
    const lanSubnetsStr = (edge.lanSubnets && edge.lanSubnets.length > 0) ? edge.lanSubnets.join(', ') : (data.system.lanSubnet || '192.168.1.0/24');

    card.innerHTML = `
        <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
            <div>
                <h3 class="card-title">☁️ Cloud VPS Edge Gateway (${edge.name || 'CGNAT Bypass Ingress'})</h3>
                <p class="card-subtitle">Stealth WireGuard tunnel & bidirectional Main LAN ↔ Edge Gateway routing</p>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                ${edge.enabled ? `
                    <button class="btn btn-secondary btn-sm" id="btn-sync-lan-routes" title="Push bidirectional Main LAN ↔ Edge Gateway routes & firewall rules">🔄 Push LAN Routes</button>
                    <button class="btn btn-secondary btn-sm" id="btn-verify-edge" title="Probe live WireGuard handshake, ICMP ping, and peer authentication">🩺 Verify Tunnel & Auth</button>
                    <button class="btn btn-danger btn-sm" id="btn-disconnect-edge" title="Teardown tunnel, flush routes, and remove SSL certs">🔌 Disconnect Gateway</button>
                ` : ''}
                <span class="badge ${edge.enabled ? 'badge-success' : 'badge-neutral'}">● ${edge.tunnelStatus || (edge.enabled ? 'Connected' : 'Not Enrolled')}</span>
            </div>
        </div>

        ${edgeDiagStatus ? `
            <div style="margin-bottom: 14px; padding: 10px 14px; border-radius: var(--radius-md); background: var(--bg-subtle); border-left: 4px solid ${edgeDiagStatus.ok ? 'var(--accent-emerald)' : 'var(--accent-amber)'}; font-size: 12px;">
                <div style="font-weight: 700; margin-bottom: 4px;">${edgeDiagStatus.title}</div>
                <div style="color: var(--text-muted);">${edgeDiagStatus.detail}</div>
            </div>
        ` : ''}

        ${!edge.enabled ? `
            <div style="background: var(--bg-subtle); padding: 16px; border-radius: var(--radius-md); margin-bottom: 16px; border: 1px dashed var(--border-subtle);">
                <h4 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 700;">🔗 Connect Cloud VPS Edge Gateway</h4>
                <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 14px 0;">Paste your bootstrap invitation token (e.g. <code>roost-edge-wg://...</code> or JWT) from your Cloud VPS to establish the WireGuard tunnel and bypass CGNAT.</p>
                <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px; margin-bottom: 12px;">
                    <div>
                        <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 4px;">Invite Token / URL</label>
                        <input type="text" class="form-input" id="edge-connect-token" placeholder="roost-edge-wg://ey... or eyJhbGci..." style="width: 100%;">
                    </div>
                    <div>
                        <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 4px;">Gateway Name</label>
                        <input type="text" class="form-input" id="edge-connect-name" value="Cloud VPS Edge Gateway" style="width: 100%;">
                    </div>
                    <div>
                        <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 4px;">Domain / Hostname (Optional)</label>
                        <input type="text" class="form-input" id="edge-connect-domain" placeholder="e.g. vps.example.com" style="width: 100%;">
                    </div>
                </div>
                <button class="btn btn-primary btn-sm" id="btn-connect-edge">Establish WireGuard Tunnel</button>
            </div>
        ` : `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Home WAN (Behind CGNAT)</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${edge.cgnatIspIp || data.system.wanIp || '-'}</code></div>
                    <span class="badge badge-warning" style="margin-top: 4px;">RFC6598 Carrier NAT</span>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Edge VPS Endpoint</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;"><code>${vpsDisplay}</code></div>
                    <span class="badge badge-success" style="margin-top: 4px;">Static Public Ingress</span>
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
        `}
        <div id="vpn-servers-container"></div>
        <div id="edge-peers-container"></div>
    `;

    container.appendChild(card);

    const vpnContainer = card.querySelector('#vpn-servers-container');
    if (vpnContainer) {
        renderVpnServers(vpnContainer, onRefresh);
    }

    const peersContainer = card.querySelector('#edge-peers-container');
    if (peersContainer) {
        renderEdgePeers(peersContainer, onRefresh);
    }

    // Attach listeners
    card.querySelector('#btn-connect-edge')?.addEventListener('click', async (e) => {
        const token = card.querySelector('#edge-connect-token')?.value.trim();
        const name = card.querySelector('#edge-connect-name')?.value.trim() || 'Cloud VPS Edge Gateway';
        const domain = card.querySelector('#edge-connect-domain')?.value.trim() || null;
        if (!token) {
            alert('Please enter an invitation token or JWT to connect the Edge Gateway.');
            return;
        }
        e.target.disabled = true;
        e.target.textContent = '⏳ Connecting...';
        try {
            const res = await api.connectEdgeGateway(token, name, domain);
            edgeDiagStatus = { ok: true, title: '✓ Edge Gateway Connected Successfully', detail: `Tunnel established to ${res.vps_ip || 'VPS'}` };
            await store.syncWithBackend();
        } catch (err) {
            edgeDiagStatus = { ok: false, title: '⚠ Connection Failed', detail: String(err.message || err) };
        }
        onRefresh();
    });

    card.querySelector('#btn-disconnect-edge')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to disconnect and teardown this Cloud VPS Edge Gateway?\n\nThis will remove the WireGuard tunnel, unbind LAN routes, and delete associated domain SSL certificates.')) return;
        try {
            const res = await api.disconnectEdgeGateway();
            edgeDiagStatus = { ok: true, title: '✓ Edge Gateway Disconnected & Cleaned Up', detail: res.message || 'Tunnel and certificates purged.' };
            await store.syncWithBackend();
        } catch (err) {
            edgeDiagStatus = { ok: false, title: '⚠ Disconnect Failed', detail: String(err.message || err) };
        }
        onRefresh();
    });

    card.querySelector('#btn-sync-lan-routes')?.addEventListener('click', async (e) => {
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
        onRefresh();
    });

    card.querySelector('#btn-verify-edge')?.addEventListener('click', async (e) => {
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
        onRefresh();
    });

    card.querySelector('#btn-add-ingress-top')?.addEventListener('click', () => {
        addingIngressPos = 'top';
        onRefresh();
    });
    card.querySelector('#btn-add-ingress-bottom')?.addEventListener('click', () => {
        addingIngressPos = 'bottom';
        onRefresh();
    });
    card.querySelector('#btn-cancel-ing')?.addEventListener('click', () => {
        addingIngressPos = null;
        onRefresh();
    });
    card.querySelector('#btn-save-ing')?.addEventListener('click', async () => {
        const domain = card.querySelector('#ing-domain')?.value.trim();
        const targetIp = card.querySelector('#ing-target-ip')?.value.trim();
        const targetPort = parseInt(card.querySelector('#ing-target-port')?.value || '443', 10);
        const sslEnabled = card.querySelector('#ing-ssl')?.checked ?? true;
        if (!domain || !targetIp) return;
        try {
            await api.createEdgeRoute({ domain, target_ip: targetIp, target_port: targetPort, ssl_enabled: sslEnabled });
            addingIngressPos = null;
            await store.syncWithBackend();
            onRefresh();
        } catch (err) {
            console.warn('Failed to create edge route:', err);
        }
    });
    card.querySelectorAll('.btn-del-ing').forEach(btn => {
        btn.onclick = async () => {
            try {
                await api.deleteEdgeRoute(btn.dataset.id);
                await store.syncWithBackend();
                onRefresh();
            } catch (err) {
                console.warn('Failed to delete edge route:', err);
            }
        };
    });
}
