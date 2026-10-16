// Concept 1: SysAdmin Console - Cockpit, Telemetry & Network Zone Visualizer
import { store } from '../state.js';
import { renderZoneDiagramSvg } from '../concept2/c2-zone-svg.js';

let cockpitViewMode = 'charts'; // 'charts' | 'diagram'

export function renderAdminCockpit(container) {
    const data = store.data;
    const admin = data.admin;

    container.innerHTML = `
        <!-- High Density Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">CPU Utilization</div>
                <div class="metric-value">${data.system.cpuPercent}% <span style="font-size: 14px; font-weight: normal; color: var(--text-muted);">(4 Cores)</span></div>
                <div class="metric-sub">Load Avg: 0.18, 0.24, 0.19</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Memory (RAM)</div>
                <div class="metric-value">${data.system.ramPercent}% <span style="font-size: 14px; font-weight: normal; color: var(--text-muted);">(1.7 / 4.0 GB)</span></div>
                <div class="metric-sub">Buffers/Cached: 840 MB</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Thermal Sensor</div>
                <div class="metric-value">${data.system.tempC} °C <span style="font-size: 14px; font-weight: normal; color: var(--accent-emerald);">• Normal</span></div>
                <div class="metric-sub">Fan RPM: Passive Cooling</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">System Uptime</div>
                <div class="metric-value" style="font-size: 18px;">${data.system.uptime}</div>
                <div class="metric-sub">Kernel: Linux 6.8.0-45-generic</div>
            </div>
        </div>

        <!-- Cockpit Sub-view Selector -->
        <div class="card" style="padding: 12px 18px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div class="c1-nav-tabs">
                    <button class="c1-nav-link cp-tab ${cockpitViewMode === 'charts' ? 'active' : ''}" data-cp="charts">
                        📈 Telemetry & Throughput Charts
                    </button>
                    <button class="c1-nav-link cp-tab ${cockpitViewMode === 'diagram' ? 'active' : ''}" data-cp="diagram">
                        🗺️ Network Zones & VPN Tunnel Architecture
                    </button>
                </div>
                <span class="badge badge-success">● Telemetry Live</span>
            </div>
        </div>

        <div id="cockpit-sub-mount"></div>
    `;

    const mount = container.querySelector('#cockpit-sub-mount');

    if (cockpitViewMode === 'diagram') {
        renderZoneDiagramSvg(mount);
    } else {
        renderCockpitCharts(mount, data, admin);
    }

    container.querySelectorAll('.cp-tab').forEach(b => {
        b.onclick = () => {
            cockpitViewMode = b.dataset.cp;
            renderAdminCockpit(container);
        };
    });
}

function renderCockpitCharts(container, data, admin) {
    container.innerHTML = `
        <div class="c1-cockpit-grid">
            <!-- Bandwidth Sparkline & Throughput -->
            <div class="card">
                <div class="card-header">
                    <div>
                        <h3 class="card-title">📈 WAN Network Real-Time Throughput</h3>
                        <p class="card-subtitle">Interface: <code>eth0</code> (Symmetric Gigabit Link)</p>
                    </div>
                    <span class="badge badge-success">Live: 1s Interval</span>
                </div>

                <div style="background: var(--bg-subtle); border-radius: var(--radius-md); padding: 16px; border: 1px solid var(--border-subtle);">
                    <svg viewBox="0 0 500 120" style="width: 100%; height: 120px; overflow: visible;">
                        <defs>
                            <linearGradient id="wanGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stop-color="#2563eb" stop-opacity="0.3"/>
                                <stop offset="100%" stop-color="#2563eb" stop-opacity="0.0"/>
                            </linearGradient>
                        </defs>
                        <line x1="0" y1="30" x2="500" y2="30" stroke="var(--border-subtle)" stroke-dasharray="3,3"/>
                        <line x1="0" y1="70" x2="500" y2="70" stroke="var(--border-subtle)" stroke-dasharray="3,3"/>
                        <line x1="0" y1="110" x2="500" y2="110" stroke="var(--border-subtle)" stroke-dasharray="3,3"/>
                        <path d="M 0 110 Q 60 40, 120 75 T 240 30 T 360 85 T 440 20 L 500 45 L 500 110 Z" fill="url(#wanGrad)"/>
                        <path d="M 0 110 Q 60 40, 120 75 T 240 30 T 360 85 T 440 20 L 500 45" fill="none" stroke="#2563eb" stroke-width="2.5"/>
                    </svg>
                    <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); margin-top: 8px; font-family: var(--font-mono);">
                        <span>Rx: 42.1 MB/s (Peak: 112 MB/s)</span>
                        <span>Tx: 6.8 MB/s (Peak: 45 MB/s)</span>
                    </div>
                </div>
            </div>

            <!-- Dynamic NFT Sets Status -->
            <div class="card">
                <div class="card-header">
                    <div>
                        <h3 class="card-title">🛡️ nftables Dynamic Sets</h3>
                        <p class="card-subtitle">Active packet filtering kernel sets</p>
                    </div>
                </div>

                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                        <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600;">
                            <span>@quarantined</span>
                            <span class="badge badge-warning">${admin.nftSets.quarantined.length} IP</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px; font-family: var(--font-mono);">
                            ${admin.nftSets.quarantined.join(', ') || 'None'}
                        </div>
                    </div>
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                        <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600;">
                            <span>@schedule_blocked</span>
                            <span class="badge badge-danger">${admin.nftSets.schedule_blocked.length} IP</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px; font-family: var(--font-mono);">
                            ${admin.nftSets.schedule_blocked.join(', ') || 'None'}
                        </div>
                    </div>
                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                        <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600;">
                            <span>@admin_blocked</span>
                            <span class="badge badge-neutral">${admin.nftSets.admin_blocked.length} IP</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px; font-family: var(--font-mono);">
                            ${admin.nftSets.admin_blocked.join(', ') || 'None'}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Core System Daemons Matrix -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">⚙️ Core Systemd Services & Subsystems</h3>
                    <p class="card-subtitle">Live health status of networking and domain engine daemons</p>
                </div>
            </div>
            <div class="c1-services-matrix">
                ${data.cluster.nodes[0].services.map(s => `
                    <div class="c1-service-item">
                        <h5><span>${s}</span><span class="badge badge-success">Active</span></h5>
                        <p>Core Networking Unit</p>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}
