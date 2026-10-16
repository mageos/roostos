// Concept 2: Unified Topology - Protection & Traffic Rules (Compliant with AGENTS.md)
import { store } from '../state.js';
import { renderBlockedFeed } from '../concept1/c1-blocked-feed.js';

let activeProtectionTab = 'rules';

export function renderProtectionView(container) {
    const data = store.data;
    const isExpert = store.concept2Density === 'expert';

    container.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🛡️ Unified Protection & Traffic Filter</h3>
                    <p class="card-subtitle">Manage parental schedules, ad filtering, and kernel packet policies</p>
                </div>
            </div>

            <div class="c1-nav-tabs" style="margin-bottom: 16px;">
                <button class="c1-nav-link sub-tab ${activeProtectionTab === 'rules' ? 'active' : ''}" data-tab="rules">Household Schedules & Filters</button>
                <button class="c1-nav-link sub-tab ${activeProtectionTab === 'nftables' ? 'active' : ''}" data-tab="nftables">
                    nftables Kernel Rules & Sets ${isExpert ? '⚡' : ''}
                </button>
            </div>

            ${activeProtectionTab === 'rules' ? `
                <div style="display: flex; flex-direction: column; gap: 14px;">
                    <div style="background: var(--bg-subtle); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="font-size: 15px; font-weight: 700;">Global Ad & Tracker Shield</h4>
                            <p style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">DNS-based network blocking active across all zones</p>
                        </div>
                        <label class="switch-toggle">
                            <input type="checkbox" id="c2-ad-toggle" ${data.protection.adBlocking.enabled ? 'checked' : ''}>
                            <span class="switch-slider"></span>
                        </label>
                    </div>

                    <div style="background: var(--bg-subtle); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="font-size: 15px; font-weight: 700;">WireGuard VPN Privacy Egress</h4>
                            <p style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">Tunnel outbound traffic through encrypted gateway</p>
                        </div>
                        <label class="switch-toggle">
                            <input type="checkbox" id="c2-vpn-toggle" ${data.protection.vpnTunnel.enabled ? 'checked' : ''}>
                            <span class="switch-slider"></span>
                        </label>
                    </div>

                    <h4 style="font-size: 14px; font-weight: 700; margin-top: 10px;">Active Bedtime Schedules</h4>
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Profile</th>
                                    <th>Bedtime Window</th>
                                    <th>Days</th>
                                    <th>Current State</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.people.filter(p => p.role === 'kid').map(k => `
                                    <tr>
                                        <td><strong>${k.avatar} ${k.name}</strong></td>
                                        <td>${k.bedtimeStart} - ${k.bedtimeEnd}</td>
                                        <td>School Nights (Sun-Thu)</td>
                                        <td><span class="badge ${k.bedtimeActive ? 'badge-danger' : 'badge-success'}">${k.bedtimeActive ? 'Enforced' : 'Normal'}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            ` : `
                <!-- nftables and Packet Filters -->
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">Set: @quarantined</div>
                            <div class="metric-value">${data.admin.nftSets.quarantined.length} IP</div>
                            <div class="metric-sub">${data.admin.nftSets.quarantined.join(', ') || 'Empty'}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Set: @schedule_blocked</div>
                            <div class="metric-value">${data.admin.nftSets.schedule_blocked.length} IP</div>
                            <div class="metric-sub">${data.admin.nftSets.schedule_blocked.join(', ') || 'Empty'}</div>
                        </div>
                    </div>

                    <h4 style="font-size: 14px; font-weight: 700;">Active Port Forwards</h4>
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Rule</th>
                                    <th>Protocol</th>
                                    <th>WAN Port</th>
                                    <th>Internal Target</th>
                                    <th>Hits</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.admin.portForwards.map(pf => `
                                    <tr>
                                        <td><strong>${pf.name}</strong></td>
                                        <td><span class="badge badge-info">${pf.proto}</span></td>
                                        <td><code>${pf.wanPort}</code></td>
                                        <td><code>${pf.lanIp}:${pf.lanPort}</code></td>
                                        <td>${pf.hits}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `}
        </div>
    `;

    renderBlockedFeed(container, { onReload: () => renderProtectionView(container) });

    container.querySelectorAll('.sub-tab').forEach(b => {
        b.onclick = () => {
            activeProtectionTab = b.dataset.tab;
            renderProtectionView(container);
        };
    });

    container.querySelector('#c2-ad-toggle')?.addEventListener('change', () => store.toggleAdBlock());
    container.querySelector('#c2-vpn-toggle')?.addEventListener('change', () => store.toggleVpn());
}
