// Concept 2: Unified Topology - Fleet, Containers & System
import { store } from '../state.js';

let selectedYaml = 'network.yaml';

export function renderFleetView(container) {
    const data = store.data;
    const admin = data.admin;

    container.innerHTML = `
        <!-- Cluster Fleet Table -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🖥️ RoostOS Fleet & Multi-Node Cluster</h3>
                    <p class="card-subtitle">Nodes synchronized across the home mesh network</p>
                </div>
            </div>

            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Node Hostname</th>
                            <th>Role</th>
                            <th>IP Address</th>
                            <th>Status</th>
                            <th>CPU Load</th>
                            <th>Memory</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${admin.clusterNodes.map(n => `
                            <tr>
                                <td><strong>${n.hostname}</strong></td>
                                <td><span class="badge badge-neutral">${n.role}</span></td>
                                <td><code>${n.ip}</code></td>
                                <td><span class="badge ${n.status === 'Master' ? 'badge-success' : 'badge-info'}">${n.status}</span></td>
                                <td>${n.load}</td>
                                <td>${n.ram}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Declarative Split YAML Layout -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📄 Declarative Configuration Files (/etc/roostos/)</h3>
                    <p class="card-subtitle">Inspect the underlying YAML specifications</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-copy-yaml-c2">📋 Copy YAML</button>
            </div>

            <div class="c1-nav-tabs" style="margin-bottom: 12px;">
                <button class="c1-nav-link y-tab ${selectedYaml === 'network.yaml' ? 'active' : ''}" data-file="network.yaml">network.yaml</button>
                <button class="c1-nav-link y-tab ${selectedYaml === 'devices.yaml' ? 'active' : ''}" data-file="devices.yaml">devices.yaml</button>
            </div>

            <div class="c2-yaml-viewer">${admin.yamlFiles[selectedYaml] || ''}</div>
        </div>
    `;

    container.querySelectorAll('.y-tab').forEach(b => {
        b.onclick = () => {
            selectedYaml = b.dataset.file;
            renderFleetView(container);
        };
    });

    container.querySelector('#btn-copy-yaml-c2')?.addEventListener('click', (e) => {
        navigator.clipboard?.writeText(admin.yamlFiles[selectedYaml]);
        e.target.textContent = 'Copied!';
        setTimeout(() => e.target.textContent = '📋 Copy YAML', 1500);
    });
}
