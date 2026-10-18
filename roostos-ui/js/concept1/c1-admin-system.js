// Concept 1: SysAdmin Console - Cluster Fleet & Multi-Node Network Breakdown
import { store } from '../state.js';
import { api } from '../api.js';

let activeYaml = 'network.yaml';
let clusterVerifyResults = null;
let updateState = null; // { checking, installing, result, error }
let joinTokenModal = null; // token string or null

export function renderAdminSystem(container) {
    const data = store.data;
    const admin = data.admin;
    const nodes = data.cluster?.nodes || [];

    const updateInfo = updateState?.result || null;
    const updatesAvailable = updateInfo?.updates_available ?? false;
    const secCount = updateInfo?.security_updates_count ?? 0;
    const allCount = updateInfo?.total_updates_count ?? (updateInfo?.packages?.length || 0);

    container.innerHTML = `
        <!-- Multi-Node Cluster Fleet Cards -->
        <div class="card">
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">🖥️ RoostOS Cluster Fleet & Node Telemetry</h3>
                    <p class="card-subtitle">Real-time status, hardware specs, and network/auth verification across all cluster nodes</p>
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

        <!-- OS & Security Updates and Router Maintenance -->
        <div class="card" style="border-left: 4px solid var(--accent-amber);">
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">🛡️ OS Updates & Router Maintenance</h3>
                    <p class="card-subtitle">Keep Debian base system, kernel, security patches, and router services up to date</p>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="badge ${updatesAvailable ? (secCount > 0 ? 'badge-danger' : 'badge-warning') : 'badge-success'}">
                        ${updatesAvailable ? `● ${allCount} Update(s) Pending` : '● Up to Date'}
                    </span>
                </div>
            </div>

            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center;">
                <button class="btn btn-primary btn-sm" id="btn-check-updates" ${updateState?.checking ? 'disabled' : ''}>
                    ${updateState?.checking ? '⏳ Checking Repositories...' : '🔍 Check for Updates'}
                </button>
                <button class="btn btn-success btn-sm" id="btn-install-all-updates" ${(!updatesAvailable || updateState?.installing) ? 'disabled' : ''}>
                    ${updateState?.installing ? '⏳ Installing...' : '⬇️ Install All Updates'}
                </button>
                <button class="btn btn-secondary btn-sm" id="btn-install-sec-updates" ${(!updatesAvailable || secCount === 0 || updateState?.installing) ? 'disabled' : ''}>
                    🛡️ Install Security Only (${secCount})
                </button>
                <button class="btn btn-danger btn-sm" id="btn-reboot-router" style="margin-left:auto;">
                    🔄 Reboot Router
                </button>
            </div>

            ${updateState?.installMessage ? `
                <div style="padding: 10px 14px; border-radius: var(--radius-md); background: var(--bg-subtle); border-left: 4px solid var(--accent-emerald); font-size: 12px; margin-bottom: 14px;">
                    <strong>Update Completed:</strong> ${updateState.installMessage}
                </div>
            ` : ''}

            ${updateInfo?.packages && updateInfo.packages.length > 0 ? `
                <div style="margin-top: 8px;">
                    <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">PENDING SYSTEM PACKAGES (${updateInfo.packages.length}):</div>
                    <div style="max-height: 120px; overflow-y: auto; background: var(--bg-subtle); padding: 8px 12px; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 11px;">
                        ${updateInfo.packages.map(p => `<div>• <strong>${p.name || p}</strong> ${p.version ? `(${p.version})` : ''}</div>`).join('')}
                    </div>
                </div>
            ` : ''}
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

    container.querySelector('#btn-cluster-token')?.addEventListener('click', async () => {
        try {
            const res = await api.request('/api/v1/cluster/token', { method: 'POST' });
            joinTokenModal = res.token || 'roost-token';
        } catch {
            joinTokenModal = 'roost-token-err';
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-close-token')?.addEventListener('click', () => {
        joinTokenModal = null;
        renderAdminSystem(container);
    });

    container.querySelector('#btn-copy-token')?.addEventListener('click', (e) => {
        navigator.clipboard?.writeText(`sudo roostos cluster join --token ${joinTokenModal}`);
        e.target.textContent = 'Copied!';
        setTimeout(() => e.target.textContent = '📋 Copy Command', 1500);
    });

    container.querySelector('#btn-check-updates')?.addEventListener('click', async () => {
        updateState = { checking: true };
        renderAdminSystem(container);
        try {
            const res = await api.checkUpdates();
            updateState = { result: res };
        } catch (err) {
            updateState = { error: String(err) };
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-install-all-updates')?.addEventListener('click', async () => {
        if (!confirm('Install all pending OS packages and updates now?')) return;
        updateState = { ...updateState, installing: true };
        renderAdminSystem(container);
        try {
            const res = await api.installUpdates(false);
            updateState = { installMessage: res.message || 'Packages installed successfully.' };
        } catch (err) {
            alert(`Installation failed: ${err.message || err}`);
            updateState = { ...updateState, installing: false };
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-install-sec-updates')?.addEventListener('click', async () => {
        updateState = { ...updateState, installing: true };
        renderAdminSystem(container);
        try {
            const res = await api.installUpdates(true);
            updateState = { installMessage: res.message || 'Security updates installed.' };
        } catch (err) {
            alert(`Security install failed: ${err.message || err}`);
            updateState = { ...updateState, installing: false };
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-reboot-router')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to reboot the RoostOS router? Network connectivity will be temporarily interrupted.')) return;
        try {
            await api.rebootRouter();
            alert('Reboot command sent to router. System will restart shortly.');
        } catch (err) {
            alert(`Failed to reboot: ${err.message || err}`);
        }
    });

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

