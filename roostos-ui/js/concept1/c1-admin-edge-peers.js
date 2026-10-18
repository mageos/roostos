// Concept 1: SysAdmin Console - Edge Gateway WireGuard Client Peers (AGENTS.md compliant)
import { store } from '../state.js';
import { api } from '../api.js';

let addingPeerPos = null; // 'top' | 'bottom' | null
let activeQrPeer = null;
let qrSvgContent = null;
let peerConfigContent = null;
let cachedServers = [];
let allPeers = [];

function buildPeerAddRow(servers) {
    const activeServers = (servers || []).filter(s => s.is_active);
    const serverOptions = activeServers.length > 0
        ? activeServers.map(s => `<option value="${s.server_id}">${s.role === 'edge_gateway' ? '☁️' : '🛡️'} ${s.name} (${s.hostname || 'No Hostname'})</option>`).join('')
        : '<option value="">No Active Servers (Enable in table above)</option>';

    return `
        <tr class="inline-edit-row" style="background: var(--bg-subtle);">
            <td><input type="text" class="form-input" id="peer-name" placeholder="e.g. Matt's iPhone" style="padding:5px 8px;font-size:12px;width:100%;"></td>
            <td><select class="form-input" id="peer-server-node" style="padding:5px 8px;font-size:12px;width:100%;">${serverOptions}</select></td>
            <td>
                <select class="form-input" id="peer-type" style="padding:5px 8px;font-size:12px;">
                    <option value="client">📱 Mobile / Laptop</option>
                    <option value="site">🌐 Remote Site / Router</option>
                </select>
            </td>
            <td><code style="color:var(--text-muted); font-size:11px;">Auto (10.42.0.X)</code></td>
            <td><label style="font-size:12px;display:flex;align-items:center;gap:6px;"><input type="checkbox" id="peer-route-internet" checked> Full Tunnel</label></td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="btn-save-peer">Save</button>
                    <button class="btn btn-secondary btn-sm" id="btn-cancel-peer">Cancel</button>
                </div>
            </td>
        </tr>
    `;
}

export function renderEdgePeers(container, onUpdate) {
    const section = document.createElement('div');
    section.style.marginTop = '24px';
    section.style.paddingTop = '18px';
    section.style.borderTop = '1px solid var(--border-subtle)';

    section.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px; flex-wrap:wrap; gap:8px;">
            <div>
                <h4 style="font-size: 14px; font-weight: 700; margin: 0;">📱 Mobile WireGuard Clients & Site-to-Site Peers</h4>
                <p style="font-size: 12px; color: var(--text-muted); margin: 2px 0 0 0;">Secure remote access profiles for iPhones, Androids, laptops, and remote home sites</p>
            </div>
            <button class="btn btn-primary btn-sm" id="btn-add-peer-top">+ Add Client Peer</button>
        </div>

        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Device Name</th>
                        <th>Target VPN Server</th>
                        <th>Peer Type</th>
                        <th>Assigned Tunnel IP</th>
                        <th>Routing Mode</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="peers-table-body">
                    <tr><td colspan="6" style="text-align:center; padding: 16px; color: var(--text-muted);">Loading remote peers...</td></tr>
                </tbody>
            </table>
        </div>
        <div style="margin-top: 10px; display: flex; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" id="btn-add-peer-bottom">+ Add Client Peer</button>
        </div>
        <div id="qr-modal-mount"></div>
    `;

    container.appendChild(section);

    async function refreshPeerData() {
        try {
            const [servers, peers] = await Promise.all([
                api.getVpnServers().catch(() => []),
                api.getEdgePeers().catch(() => store.data.edgeGateway.peers || [])
            ]);
            cachedServers = servers;
            allPeers = peers;
            renderPeerRows();
        } catch (e) {
            allPeers = store.data.edgeGateway.peers || [];
            renderPeerRows();
        }
    }

    function renderPeerRows() {
        const tbody = section.querySelector('#peers-table-body');
        if (!tbody) return;

        tbody.innerHTML = `
            ${addingPeerPos === 'top' ? buildPeerAddRow(cachedServers) : ''}
            ${allPeers.length === 0 && !addingPeerPos ? `
                <tr><td colspan="6" style="text-align:center; padding: 20px; color: var(--text-muted);">No mobile devices or remote peers registered yet. Click "+ Add Client Peer" to create one.</td></tr>
            ` : allPeers.map(p => `
                <tr>
                    <td>
                        <strong>${p.peer_type === 'site' ? '🌐' : '📱'} ${p.name}</strong>
                        <div style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono);">${p.id}</div>
                    </td>
                    <td>
                        <span class="badge badge-info">
                            ${p.server_node_id === 'edge' || (p.server_node_name && p.server_node_name.includes('Edge')) ? '☁️' : '🛡️'}
                            ${p.server_node_name || 'Edge Gateway'}
                        </span>
                    </td>
                    <td><span class="badge ${p.peer_type === 'site' ? 'badge-warning' : 'badge-info'}">${p.peer_type === 'site' ? 'Remote Site' : 'Mobile Client'}</span></td>
                    <td><code>${p.assigned_ip}</code></td>
                    <td><span class="badge badge-neutral">${p.route_internet ? 'Full Tunnel (0.0.0.0/0)' : 'Split Tunnel'}</span></td>
                    <td>
                        <div style="display:flex; gap:6px; flex-wrap:wrap;">
                            <button class="btn btn-secondary btn-sm btn-qr-peer" data-id="${p.id}" data-name="${p.name}" title="Scan QR Code with WireGuard App">📱 QR Code</button>
                            <button class="btn btn-danger btn-sm btn-del-peer" data-id="${p.id}" data-name="${p.name}">Revoke</button>
                        </div>
                    </td>
                </tr>
            `).join('')}
            ${addingPeerPos === 'bottom' ? buildPeerAddRow(cachedServers) : ''}
        `;

        renderQrModal();
        wireTableEvents();
    }

    function renderQrModal() {
        const modalMount = section.querySelector('#qr-modal-mount');
        if (!modalMount) return;
        if (!activeQrPeer) {
            modalMount.innerHTML = '';
            return;
        }
        modalMount.innerHTML = `
            <div id="qr-modal-backdrop" style="position:fixed;inset:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:9999;padding:20px;">
                <div class="card" style="max-width:440px;width:100%;margin:0;background:var(--bg-surface);border:1px solid var(--border-subtle);box-shadow:var(--shadow-xl);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <h3 style="font-size:16px;font-weight:700;margin:0;">📱 WireGuard QR Code: ${activeQrPeer.name}</h3>
                        <button class="btn btn-secondary btn-sm" id="btn-close-qr" style="padding:2px 8px;">✕</button>
                    </div>
                    <p style="font-size:12px;color:var(--text-muted);margin:0 0 14px 0;">Scan this with the official WireGuard app (iOS / Android) for instant tunnel activation:</p>
                    <div id="qr-svg-container" style="display:flex;justify-content:center;background:#fff;padding:16px;border-radius:var(--radius-md);margin-bottom:14px;">
                        ${qrSvgContent || '<div style="color:#000;">Generating QR Code...</div>'}
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;">
                        <button class="btn btn-secondary btn-sm" id="btn-copy-peer-conf">📋 Copy .conf</button>
                        <button class="btn btn-primary btn-sm" id="btn-download-peer-conf">⬇️ Download .conf</button>
                    </div>
                </div>
            </div>
        `;

        modalMount.querySelector('#btn-close-qr')?.addEventListener('click', () => {
            activeQrPeer = null; qrSvgContent = null; peerConfigContent = null;
            renderQrModal();
        });
        modalMount.querySelector('#btn-copy-peer-conf')?.addEventListener('click', (e) => {
            if (peerConfigContent) {
                navigator.clipboard?.writeText(peerConfigContent);
                e.target.textContent = 'Copied!';
                setTimeout(() => e.target.textContent = '📋 Copy .conf', 1500);
            }
        });
        modalMount.querySelector('#btn-download-peer-conf')?.addEventListener('click', () => {
            if (peerConfigContent && activeQrPeer) {
                const blob = new Blob([peerConfigContent], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${activeQrPeer.name.replace(/\s+/g, '_')}.conf`;
                a.click();
                URL.revokeObjectURL(url);
            }
        });
    }

    function wireTableEvents() {
        section.querySelector('#btn-cancel-peer')?.addEventListener('click', () => {
            addingPeerPos = null;
            renderPeerRows();
        });
        section.querySelector('#btn-save-peer')?.addEventListener('click', async () => {
            const name = section.querySelector('#peer-name')?.value.trim();
            const serverNodeId = section.querySelector('#peer-server-node')?.value || null;
            const peerType = section.querySelector('#peer-type')?.value || 'client';
            const routeInternet = section.querySelector('#peer-route-internet')?.checked ?? true;
            if (!name) return;
            try {
                const peer = await api.createEdgePeer({ name, peer_type: peerType, route_internet: routeInternet, server_node_id: serverNodeId });
                addingPeerPos = null;
                await refreshPeerData();
                activeQrPeer = { id: peer.id, name: peer.name };
                qrSvgContent = peer.qr_svg || (await api.getEdgePeerQr(peer.id));
                peerConfigContent = peer.client_config || (await api.getEdgePeerConfig(peer.id));
                renderQrModal();
                onUpdate();
            } catch (err) {
                alert(`Failed to create peer: ${err.message || err}`);
            }
        });
        section.querySelectorAll('.btn-del-peer').forEach(btn => {
            btn.onclick = async () => {
                if (!confirm(`Are you sure you want to revoke '${btn.dataset.name}'?`)) return;
                try {
                    await api.deleteEdgePeer(btn.dataset.id);
                    await refreshPeerData();
                    onUpdate();
                } catch (err) {
                    alert(`Failed to delete peer: ${err.message || err}`);
                }
            };
        });
        section.querySelectorAll('.btn-qr-peer').forEach(btn => {
            btn.onclick = async () => {
                activeQrPeer = { id: btn.dataset.id, name: btn.dataset.name };
                qrSvgContent = await api.getEdgePeerQr(btn.dataset.id);
                peerConfigContent = await api.getEdgePeerConfig(btn.dataset.id);
                renderQrModal();
            };
        });
    }

    section.querySelector('#btn-add-peer-top')?.addEventListener('click', () => {
        addingPeerPos = 'top';
        renderPeerRows();
    });
    section.querySelector('#btn-add-peer-bottom')?.addEventListener('click', () => {
        addingPeerPos = 'bottom';
        renderPeerRows();
    });

    refreshPeerData();
}
