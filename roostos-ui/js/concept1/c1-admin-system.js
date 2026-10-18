// Concept 1: SysAdmin Console - Cluster Fleet & Multi-Node Network Breakdown
import { store } from '../state.js';
import { api } from '../api.js';

let activeYaml = 'network.yaml';
let clusterVerifyResults = null;

export function renderAdminSystem(container) {
    const data = store.data;
    const admin = data.admin;
    const nodes = data.cluster?.nodes || [];

    container.innerHTML = `
        <!-- Multi-Node Cluster Fleet Cards -->
        <div class="card">
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">🖥️ RoostOS Cluster Fleet & Node Telemetry</h3>
                    <p class="card-subtitle">Real-time status, hardware specs, and network/auth verification across all cluster nodes</p>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
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

                        <div style="margin-top: 14px; font-size: 11px; color: var(--text-muted);">
                            Services: <strong>${(n.services || []).join(', ')}</strong>
                        </div>
                    </div>
                `}).join('')}
            </div>
        </div>

        <!-- Split YAML Configuration Inspector -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📄 Split Configuration Layout (/etc/roostos/)</h3>
                    <p class="card-subtitle">Inspect the declarative version-controlled YAML state files</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-copy-yaml">📋 Copy YAML</button>
            </div>

            <div class="c1-nav-tabs" style="margin-bottom: 12px;">
                <button class="c1-nav-link yaml-tab ${activeYaml === 'network.yaml' ? 'active' : ''}" data-file="network.yaml">network.yaml</button>
                <button class="c1-nav-link yaml-tab ${activeYaml === 'devices.yaml' ? 'active' : ''}" data-file="devices.yaml">devices.yaml</button>
            </div>

            <div class="c2-yaml-viewer" id="yaml-code-display">${(admin.yamlFiles && admin.yamlFiles[activeYaml]) || '# Declarative configuration files\n# Location: /etc/roostos/'}</div>
        </div>
    `;

    container.querySelector('#btn-verify-cluster')?.addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = '⏳ Probing Nodes...';
        try {
            const res = await api.verifyClusterConnectivity();
            clusterVerifyResults = res.nodes || [];
        } catch (err) {
            console.warn('Cluster verification failed:', err);
        }
        renderAdminSystem(container);
    });

    container.querySelectorAll('.yaml-tab').forEach(b => {
        b.onclick = () => {
            activeYaml = b.dataset.file;
            renderAdminSystem(container);
        };
    });

    container.querySelector('#btn-copy-yaml').onclick = (e) => {
        const text = (admin.yamlFiles && admin.yamlFiles[activeYaml]) || '';
        navigator.clipboard?.writeText(text);
        e.target.textContent = 'Copied!';
        setTimeout(() => e.target.textContent = '📋 Copy YAML', 1500);
    };
}
