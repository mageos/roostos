// Concept 1: SysAdmin Console - Cluster Fleet & Multi-Node Network Breakdown
import { store } from '../state.js';

let activeYaml = 'network.yaml';

export function renderAdminSystem(container) {
    const data = store.data;
    const admin = data.admin;
    const nodes = data.cluster?.nodes || [];

    container.innerHTML = `
        <!-- Multi-Node Cluster Fleet Cards -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🖥️ RoostOS Cluster Fleet & Node Telemetry</h3>
                    <p class="card-subtitle">Real-time status, hardware specs, and network bindings across all cluster nodes</p>
                </div>
                <span class="badge badge-success">Node Telemetry Active</span>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 16px;">
                ${nodes.length === 0 ? `
                    <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted);">
                        No cluster nodes detected. Local router: <strong>${data.system.hostname}</strong> (<code>${data.system.gatewayIp}</code>)
                    </div>
                ` : nodes.map(n => `
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
                `).join('')}
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
