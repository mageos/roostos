// Concept 1: SysAdmin Console - Cluster Fleet Management & Node Decommissioning (AGENTS.md compliant)
import { store } from '../state.js';
import { api } from '../api.js';

let clusterVerifyResults = null;
let joinTokenModal = null;

export function renderClusterFleet(container, onUpdate) {
    const data = store.data;
    const nodes = data.cluster?.nodes || [];
    const localHostname = data.system.hostname;
    const localNodeId = data.system.nodeId || 'node-01';

    const card = document.createElement('div');
    card.className = 'card';

    card.innerHTML = `
        <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
            <div>
                <h3 class="card-title">🖥️ RoostOS Cluster Fleet & Node Telemetry</h3>
                <p class="card-subtitle">Real-time status, hardware specs, network/auth verification, and node lifecycle management</p>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <button class="btn btn-secondary btn-sm" id="btn-cluster-token">➕ Generate Join Token</button>
                <button class="btn btn-secondary btn-sm" id="btn-verify-cluster">🩺 Verify Connectivity & Auth</button>
                <span class="badge badge-success">Node Telemetry Active</span>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 16px;">
            ${nodes.length === 0 ? `
                <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted);">
                    No cluster nodes detected. Local router: <strong>${data.system.hostname}</strong> (<code>${data.system.gatewayIp}</code>)
                </div>
            ` : nodes.map(n => {
                const v = (clusterVerifyResults || []).find(r => r.node_id === n.id || r.ip === n.ip);
                const isLocal = n.id === localNodeId || n.hostname === localHostname;
                return `
                <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 18px; background: var(--bg-subtle); display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <h4 style="font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                                    <span>${(n.role || '').includes('Cloud') ? '☁️' : (n.role || '').includes('Gateway') ? '🛡️' : (n.role || '').includes('Mesh') ? '📶' : '🖥️'}</span>
                                    ${n.hostname}
                                </h4>
                                <div style="font-size: 12px; color: var(--brand-primary); font-weight: 600; margin-top: 2px;">${n.role}</div>
                            </div>
                            <span class="badge ${n.status === 'Master' ? 'badge-success' : n.status === 'Cloud Ingress' ? 'badge-info' : 'badge-neutral'}">${n.status}</span>
                        </div>

                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                            <div>IP: <code>${n.ip}</code></div>
                            <div>CPU: <strong>${n.cpu}%</strong></div>
                            <div>Model: <strong>${n.model}</strong></div>
                            <div>Uptime: <strong>${n.uptime}</strong></div>
                        </div>

                        ${v ? `
                            <div style="margin-top: 10px; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-surface); font-size: 11px;">
                                <div>Ping: <strong>${v.ping_reachable ? `OK (${v.latency_ms || '<1'} ms)` : 'Unreachable'}</strong> | API: <strong>${v.api_reachable ? 'OK' : 'Offline'}</strong></div>
                                <div style="margin-top: 2px;">Auth: <strong style="color: ${v.auth_valid ? 'var(--accent-emerald)' : 'var(--accent-amber)'};">${v.auth_valid ? 'Verified' : 'Unverified'} (${v.auth_method})</strong></div>
                            </div>
                        ` : ''}

                        <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-subtle);">
                            <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px;">BOUND NETWORK INTERFACES:</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                ${(n.interfaces || []).map(i => `
                                    <span class="badge badge-neutral" style="font-family:var(--font-mono); font-size:10px;">
                                        ${i.name} (${(i.role || 'LAN').split(' ')[0]})
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    </div>

                    <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <div style="font-size: 11px; color: var(--text-muted);">
                            Services: <strong>${(n.services || []).join(', ')}</strong>
                        </div>
                        ${isLocal ? `
                            ${nodes.length > 1 ? `
                                <button class="btn btn-danger btn-sm btn-leave-cluster" style="font-size: 11px; padding: 3px 8px;" title="Leave the cluster and reset to standalone mode">🚪 Leave Cluster</button>
                            ` : ''}
                        ` : `
                            <button class="btn btn-danger btn-sm btn-evict-node" data-id="${n.id}" data-name="${n.hostname}" style="font-size: 11px; padding: 3px 8px;" title="Evict failed or decommissioned node and invalidate credentials">🗑️ Remove Node</button>
                        `}
                    </div>
                </div>
            `}).join('')}
        </div>

        ${joinTokenModal ? `
            <div id="token-modal-backdrop" style="position:fixed;inset:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:9999;padding:20px;">
                <div class="card" style="max-width:480px;width:100%;margin:0;background:var(--bg-surface);border:1px solid var(--border-subtle);box-shadow:var(--shadow-xl);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <h3 style="font-size:16px;font-weight:700;margin:0;">➕ Cluster Node Join Token</h3>
                        <button class="btn btn-secondary btn-sm" id="btn-close-token" style="padding:2px 8px;">✕</button>
                    </div>
                    <p style="font-size:12px;color:var(--text-muted);margin:0 0 10px 0;">To enroll a worker node or mesh access point into this cluster, run on the new node:</p>
                    <div style="background:var(--bg-subtle);padding:10px 14px;border-radius:var(--radius-sm);font-family:var(--font-mono);font-size:12px;word-break:break-all;margin-bottom:14px;color:var(--accent-emerald);">
                        sudo roostos cluster join --token ${joinTokenModal}
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;">
                        <button class="btn btn-primary btn-sm" id="btn-copy-token">📋 Copy Command</button>
                    </div>
                </div>
            </div>
        ` : ''}
    `;

    container.appendChild(card);

    // Event handlers
    card.querySelector('#btn-cluster-token')?.addEventListener('click', async () => {
        try {
            const res = await api.request('/api/v1/cluster/token', { method: 'POST' });
            joinTokenModal = res.token || 'roost-token';
        } catch {
            joinTokenModal = 'roost-token-err';
        }
        onUpdate();
    });

    card.querySelector('#btn-close-token')?.addEventListener('click', () => {
        joinTokenModal = null;
        onUpdate();
    });

    card.querySelector('#btn-copy-token')?.addEventListener('click', (e) => {
        navigator.clipboard?.writeText(`sudo roostos cluster join --token ${joinTokenModal}`);
        e.target.textContent = 'Copied!';
        setTimeout(() => e.target.textContent = '📋 Copy Command', 1500);
    });

    card.querySelector('#btn-verify-cluster')?.addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = '⏳ Probing Nodes...';
        try {
            const res = await api.verifyClusterConnectivity();
            clusterVerifyResults = res.nodes || [];
        } catch (err) {
            console.warn('Cluster verification failed:', err);
        }
        onUpdate();
    });

    card.querySelectorAll('.btn-evict-node').forEach(btn => {
        btn.onclick = async () => {
            const nodeId = btn.dataset.id;
            const nodeName = btn.dataset.name;
            if (!confirm(`Are you sure you want to remove node '${nodeName}' (${nodeId}) from the cluster?\n\nThis will invalidate its mTLS credentials, revoke certificates, cleanup routes/tunnels, and purge it from the cluster roster.`)) return;
            try {
                const res = await api.removeClusterNode(nodeId);
                alert(`✓ ${res.message || `Node '${nodeName}' evicted successfully.`}`);
                await store.syncWithBackend();
                onUpdate();
            } catch (err) {
                alert(`Failed to remove node: ${err.message || err}`);
            }
        };
    });

    card.querySelector('.btn-leave-cluster')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want this local router to leave the cluster?\n\nThis will invalidate cluster credentials, disconnect from the controller, and reset this node to standalone operation.')) return;
        try {
            const res = await api.leaveCluster();
            alert(`✓ ${res.message || 'Node left cluster successfully.'}`);
            await store.syncWithBackend();
            onUpdate();
        } catch (err) {
            alert(`Failed to leave cluster: ${err.message || err}`);
        }
    });
}
