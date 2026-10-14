// Concept 2: Unified Topology - Network Zones, VPN Tunnels & Cluster Fleet Map
import { store } from '../state.js';
import { renderZoneDiagramSvg } from './c2-zone-svg.js';

let activeTopoMode = 'zones'; // 'zones' | 'fleet'
let selectedClusterNode = 'all';

export function renderTopologyView(container) {
    const data = store.data;
    const isExpert = store.concept2Density === 'expert';
    const edge = data.edgeGateway;
    const nodes = data.cluster.nodes;
    const activeNodeData = nodes.find(n => n.id === selectedClusterNode);

    container.innerHTML = `
        <!-- View Selector Bar -->
        <div class="card" style="padding: 14px 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div class="c1-nav-tabs">
                    <button class="c1-nav-link topo-tab-btn ${activeTopoMode === 'zones' ? 'active' : ''}" data-topo-tab="zones">
                        🗺️ Network Zones & VPN Tunnel Flow
                    </button>
                    <button class="c1-nav-link topo-tab-btn ${activeTopoMode === 'fleet' ? 'active' : ''}" data-topo-tab="fleet">
                        🖥️ Multi-Node Cluster Fleet Mesh
                    </button>
                </div>
                <div style="display: flex; gap: 8px;">
                    <span class="badge badge-success">● Zones Active</span>
                    <span class="badge badge-info">WireGuard CGNAT Bypass</span>
                </div>
            </div>
        </div>

        <div id="topo-mount-body"></div>
    `;

    const bodyMount = container.querySelector('#topo-mount-body');

    if (activeTopoMode === 'zones') {
        renderZoneDiagramSvg(bodyMount);
    } else {
        renderFleetTopologyView(bodyMount, data, isExpert, edge, nodes, activeNodeData);
    }

    container.querySelectorAll('.topo-tab-btn').forEach(btn => {
        btn.onclick = () => {
            activeTopoMode = btn.dataset.topoTab;
            renderTopologyView(container);
        };
    });
}

function renderFleetTopologyView(container, data, isExpert, edge, nodes, activeNodeData) {
    container.innerHTML = `
        <div class="c2-topology-canvas-container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div>
                    <h3 style="font-size: 16px; font-weight: 700;">🌐 Distributed Cluster & Edge Gateway Topology</h3>
                    <p style="font-size: 12px; color: var(--text-muted);">Click any node in the cluster fleet to inspect its physical adapters, routing & telemetry</p>
                </div>
                <span class="badge badge-success">● 4 Nodes Synchronized</span>
            </div>

            <div class="c2-topo-graph">
                <div class="c2-topo-node ${selectedClusterNode === 'vps-edge-01' ? 'active' : ''}" data-cluster-node="vps-edge-01">
                    <div class="c2-node-icon">☁️</div>
                    <div class="c2-node-title">vps-edge-01</div>
                    <div class="c2-node-meta">Public Static: <code>${edge.vpsPublicIp}</code></div>
                    <span class="badge badge-info" style="font-size: 10px; margin-top: 4px;">Cloud Ingress</span>
                </div>
                <div class="c2-topo-link" title="WireGuard Stealth Tunnel (10.42.0.0/24)"></div>
                <div class="c2-topo-node ${selectedClusterNode === 'roost-gateway-01' ? 'active' : ''}" data-cluster-node="roost-gateway-01">
                    <div class="c2-node-icon">🛡️</div>
                    <div class="c2-node-title">roost-gateway-01</div>
                    <div class="c2-node-meta">Gateway: <code>192.168.1.1</code></div>
                    <span class="badge badge-warning" style="font-size: 10px; margin-top: 4px;">CGNAT (${edge.cgnatIspIp})</span>
                </div>
                <div class="c2-topo-link"></div>
                <div class="c2-topo-node ${selectedClusterNode === 'roost-controller-01' ? 'active' : ''}" data-cluster-node="roost-controller-01">
                    <div class="c2-node-icon">🖥️</div>
                    <div class="c2-node-title">roost-controller-01</div>
                    <div class="c2-node-meta">Apps & DNS: <code>192.168.1.10</code></div>
                    <span class="badge badge-neutral" style="font-size: 10px; margin-top: 4px;">Docker Host</span>
                </div>
                <div class="c2-topo-link"></div>
                <div class="c2-topo-node ${selectedClusterNode === 'living-room-ap' ? 'active' : ''}" data-cluster-node="living-room-ap">
                    <div class="c2-node-icon">📶</div>
                    <div class="c2-node-title">living-room-ap</div>
                    <div class="c2-node-meta">PoE Backhaul: <code>192.168.1.4</code></div>
                    <span class="badge badge-success" style="font-size: 10px; margin-top: 4px;">Mesh Satellite</span>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🔍 Node Network Inspector: <span style="color:var(--brand-primary);">${activeNodeData ? activeNodeData.hostname : 'All Cluster Nodes'}</span></h3>
                    <p class="card-subtitle">${activeNodeData ? `${activeNodeData.role} • Hardware: ${activeNodeData.model}` : 'Click any node above to inspect its specific adapters and routing'}</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-reset-cluster-filter">Fleet Overview</button>
            </div>

            ${activeNodeData ? `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px;">
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                        <div style="font-size: 11px; color: var(--text-muted);">CPU Utilization</div>
                        <div style="font-size: 18px; font-weight: 700; color: var(--brand-primary);">${activeNodeData.cpu}%</div>
                    </div>
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                        <div style="font-size: 11px; color: var(--text-muted);">RAM Memory</div>
                        <div style="font-size: 18px; font-weight: 700;">${activeNodeData.ram}</div>
                    </div>
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                        <div style="font-size: 11px; color: var(--text-muted);">Thermal Temp</div>
                        <div style="font-size: 18px; font-weight: 700; color: var(--accent-emerald);">${activeNodeData.temp}</div>
                    </div>
                </div>

                <div class="table-responsive">
                    <table class="data-table">
                        <thead>
                            <tr><th>Interface</th><th>Role</th><th>Link Speed</th><th>Assigned IP</th><th>MTU</th><th>Traffic (Rx / Tx)</th><th>Status</th></tr>
                        </thead>
                        <tbody>
                            ${activeNodeData.interfaces.map(i => `
                                <tr>
                                    <td><code>${i.name}</code></td>
                                    <td><span class="badge ${i.role.includes('WAN') ? 'badge-info' : 'badge-neutral'}">${i.role}</span></td>
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
            ` : `
                <div class="table-responsive">
                    <table class="data-table">
                        <thead>
                            <tr><th>Cluster Node</th><th>Role</th><th>Hardware Model</th><th>Primary IP</th><th>Active Adapters</th><th>CPU Load</th><th>Cluster State</th></tr>
                        </thead>
                        <tbody>
                            ${nodes.map(n => `
                                <tr class="node-row" data-node-select="${n.id}" style="cursor: pointer;">
                                    <td><strong>${n.role.includes('Cloud') ? '☁️' : n.role.includes('Gateway') ? '🛡️' : '🖥️'} ${n.hostname}</strong></td>
                                    <td><span class="badge badge-neutral">${n.role}</span></td>
                                    <td>${n.model}</td>
                                    <td><code>${n.ip}</code></td>
                                    <td>${n.interfaces.map(i => i.name).join(', ')}</td>
                                    <td>${n.cpu}%</td>
                                    <td><span class="badge badge-success">${n.status}</span></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `}
        </div>
    `;

    container.querySelectorAll('[data-cluster-node]').forEach(el => {
        el.onclick = () => { selectedClusterNode = el.dataset.clusterNode; renderFleetTopologyView(container, data, isExpert, edge, nodes, nodes.find(n => n.id === selectedClusterNode)); };
    });
    container.querySelectorAll('[data-node-select]').forEach(el => {
        el.onclick = () => { selectedClusterNode = el.dataset.nodeSelect; renderFleetTopologyView(container, data, isExpert, edge, nodes, nodes.find(n => n.id === selectedClusterNode)); };
    });
    container.querySelector('#btn-reset-cluster-filter').onclick = () => {
        selectedClusterNode = 'all';
        renderFleetTopologyView(container, data, isExpert, edge, nodes, null);
    };
}
