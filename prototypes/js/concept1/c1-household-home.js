// Concept 1: Household Hub - Home Dashboard & Pulse
import { store } from '../state.js';

export function renderHouseholdHome(container) {
    const data = store.data;
    const kids = data.people.filter(p => p.role === "kid");
    const allKidsPaused = kids.every(k => k.bedtimeActive);

    const alertHtml = data.system.unassignedDeviceAlert ? `
        <div class="card" style="border-left: 4px solid var(--accent-amber); background: var(--accent-amber-subtle);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: gap: 12px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 24px;">⚠️</span>
                    <div>
                        <strong style="color: var(--text-main);">New Device Detected: Unknown Samsung Galaxy S23</strong>
                        <p style="font-size: 12px; color: var(--text-muted); margin: 0;">Connected via Wi-Fi (IP: 192.168.1.188). Currently quarantined from home LAN.</p>
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-primary btn-sm" id="btn-allow-quarantine">Assign to Person</button>
                    <button class="btn btn-secondary btn-sm" id="btn-dismiss-quarantine">Keep Quarantined</button>
                </div>
            </div>
        </div>
    ` : '';

    container.innerHTML = `
        <!-- Hero Internet Pulse Banner -->
        <div class="c1-hero-banner">
            <div class="c1-hero-top">
                <div>
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <span class="brand-dot"></span>
                        <span style="font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Network Online</span>
                    </div>
                    <h2 class="c1-hero-title">${data.system.ispName}</h2>
                    <p class="c1-hero-subtitle">Gateway IP: <code>${data.system.gatewayIp}</code> • External WAN: <code>${data.system.wanIp}</code></p>
                </div>
                <div class="c1-hero-stats">
                    <div class="c1-hero-stat-box">
                        <div class="c1-hero-stat-label">Download Speed</div>
                        <div class="c1-hero-stat-value">⚡ ${data.system.downloadMbps} <span style="font-size: 12px; font-weight: normal;">Mbps</span></div>
                    </div>
                    <div class="c1-hero-stat-box">
                        <div class="c1-hero-stat-label">Upload Speed</div>
                        <div class="c1-hero-stat-value">⬆️ ${data.system.uploadMbps} <span style="font-size: 12px; font-weight: normal;">Mbps</span></div>
                    </div>
                    <div class="c1-hero-stat-box">
                        <div class="c1-hero-stat-label">Latency / Ping</div>
                        <div class="c1-hero-stat-value">⏱️ ${data.system.pingMs} <span style="font-size: 12px; font-weight: normal;">ms</span></div>
                    </div>
                </div>
            </div>
        </div>

        ${alertHtml}

        <!-- One-Touch Quick Actions -->
        <div class="c1-quick-actions">
            <div class="c1-action-card" id="qa-pause-kids">
                <div class="c1-action-icon">${allKidsPaused ? '▶️' : '⏸️'}</div>
                <div class="c1-action-text">
                    <h4>${allKidsPaused ? 'Resume Kids Wi-Fi' : 'Pause Kids Wi-Fi'}</h4>
                    <p>${allKidsPaused ? 'All kids paused' : 'Pause Alice & Bob now'}</p>
                </div>
            </div>

            <div class="c1-action-card" id="qa-dinner-time">
                <div class="c1-action-icon">🍕</div>
                <div class="c1-action-text">
                    <h4>Dinner Time</h4>
                    <p>Pause household screens 1 hr</p>
                </div>
            </div>

            <div class="c1-action-card" id="qa-bonus-time">
                <div class="c1-action-icon">⏱️</div>
                <div class="c1-action-text">
                    <h4>+30 Min Bonus</h4>
                    <p>Grant kids extra screentime</p>
                </div>
            </div>

            <div class="c1-action-card" id="qa-guest-qr">
                <div class="c1-action-icon">📶</div>
                <div class="c1-action-text">
                    <h4>Guest Wi-Fi QR</h4>
                    <p>Show instant connect QR</p>
                </div>
            </div>
        </div>

        <!-- Family Snapshot Section -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">👨‍👩‍👧‍👦 Family Screen Time & Bedtimes</h3>
                    <p class="card-subtitle">Real-time status of household profiles and parental controls</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-view-all-family">Manage Family →</button>
            </div>

            <div class="c1-family-grid">
                ${data.people.map(p => {
                    const pct = p.screentimeLimit > 0 ? Math.min(100, Math.round((p.screentimeUsed / p.screentimeLimit) * 100)) : 0;
                    const barColor = p.bedtimeActive ? 'var(--accent-rose)' : pct > 85 ? 'var(--accent-amber)' : 'var(--accent-emerald)';
                    return `
                        <div class="c1-family-card" style="border-top: 4px solid ${p.color};">
                            <div class="c1-family-header">
                                <div class="c1-family-identity">
                                    <div class="c1-family-avatar" style="background: ${p.color}20;">${p.avatar}</div>
                                    <div>
                                        <h4 style="font-size: 15px; font-weight: 600;">${p.name}</h4>
                                        <span class="badge ${p.bedtimeActive ? 'badge-danger' : 'badge-success'}">
                                            ${p.bedtimeActive ? '🌙 Bedtime Blocked' : '🟢 Internet Active'}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div style="font-size: 12px; color: var(--text-muted); display: flex; justify-content: space-between;">
                                <span>Screen time used:</span>
                                <strong>${p.screentimeLimit > 0 ? `${p.screentimeUsed} / ${p.screentimeLimit}m` : 'Unlimited'}</strong>
                            </div>
                            ${p.screentimeLimit > 0 ? `
                                <div class="c1-family-progress-bar">
                                    <div class="c1-family-progress-fill" style="width: ${pct}%; background: ${barColor};"></div>
                                </div>
                            ` : ''}

                            <div style="display: flex; gap: 8px; margin-top: 6px;">
                                <button class="btn btn-secondary btn-sm toggle-bedtime-btn" data-id="${p.id}" style="flex: 1;">
                                    ${p.bedtimeActive ? 'Unpause' : 'Pause'}
                                </button>
                                ${p.role === 'kid' ? `
                                    <button class="btn btn-secondary btn-sm bonus-time-btn" data-id="${p.id}">+30m</button>
                                ` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>

        <!-- Network Devices Summary Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📱 Connected Devices Snapshot</h3>
                    <p class="card-subtitle">${data.devices.length} devices online across household zones</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-view-all-devices">View All Devices →</button>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                <div style="background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                    <div style="font-size: 12px; color: var(--text-muted);">Family Devices</div>
                    <div style="font-size: 22px; font-weight: 700; color: var(--brand-primary); margin-top: 4px;">
                        ${data.devices.filter(d => ['dad', 'mom', 'alice', 'bob'].includes(d.owner)).length} Online
                    </div>
                </div>
                <div style="background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                    <div style="font-size: 12px; color: var(--text-muted);">Smart Home (IoT)</div>
                    <div style="font-size: 22px; font-weight: 700; color: var(--accent-emerald); margin-top: 4px;">
                        ${data.devices.filter(d => d.zone === 'iot').length} Isolated
                    </div>
                </div>
                <div style="background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                    <div style="font-size: 12px; color: var(--text-muted);">Guest Network</div>
                    <div style="font-size: 22px; font-weight: 700; color: var(--accent-amber); margin-top: 4px;">
                        ${data.devices.filter(d => d.zone === 'guest').length} Active
                    </div>
                </div>
            </div>
        </div>

        <!-- Visual Network & Zone Map Teaser -->
        <div class="card" style="border-left: 4px solid var(--brand-primary);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h3 class="card-title">🗺️ Interactive Network Map & Security Zones</h3>
                    <p class="card-subtitle">Visualize how ports, Wi-Fi radios, and encrypted tunnels flow into your home</p>
                </div>
                <button class="btn btn-primary btn-sm" id="btn-view-topo-map">Open Network Map →</button>
            </div>
        </div>

        <!-- Recently Blocked Threats & Protection Summary -->
        <div class="card" style="border-left: 4px solid var(--accent-rose);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h3 class="card-title">🛡️ Protection Shield: ${data.protection.blockedRequests.length} Recent Blocks</h3>
                    <p class="card-subtitle">Latest block: <code>${data.protection.blockedRequests[0].target}</code> on ${data.protection.blockedRequests[0].clientName} (${data.protection.blockedRequests[0].timeAgo})</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-view-blocked-feed">View Blocked Requests →</button>
            </div>
        </div>
    `;

    // Event handlers
    container.querySelector('#qa-pause-kids')?.addEventListener('click', () => {
        kids.forEach(k => store.toggleBedtime(k.id));
    });

    container.querySelector('#qa-dinner-time')?.addEventListener('click', () => {
        data.people.forEach(p => store.toggleBedtime(p.id));
    });

    container.querySelector('#qa-bonus-time')?.addEventListener('click', () => {
        kids.forEach(k => store.addBonusScreentime(k.id, 30));
    });

    container.querySelector('#qa-guest-qr')?.addEventListener('click', () => {
        window.c1SwitchTab('wifi');
    });

    container.querySelector('#btn-view-all-family')?.addEventListener('click', () => {
        window.c1SwitchTab('family');
    });

    container.querySelector('#btn-view-all-devices')?.addEventListener('click', () => {
        window.c1SwitchTab('devices');
    });

    container.querySelector('#btn-view-topo-map')?.addEventListener('click', () => {
        window.c1SwitchTab('topology');
    });

    container.querySelector('#btn-view-blocked-feed')?.addEventListener('click', () => {
        window.c1SwitchTab('safety');
    });

    container.querySelectorAll('.toggle-bedtime-btn').forEach(btn => {
        btn.addEventListener('click', () => store.toggleBedtime(btn.dataset.id));
    });

    container.querySelectorAll('.bonus-time-btn').forEach(btn => {
        btn.addEventListener('click', () => store.addBonusScreentime(btn.dataset.id, 30));
    });

    container.querySelector('#btn-allow-quarantine')?.addEventListener('click', () => {
        store.allowQuarantinedDevice("cc:dd:ee:ff:00:99", "dad", "Dad's Work Galaxy S23");
    });

    container.querySelector('#btn-dismiss-quarantine')?.addEventListener('click', () => {
        store.data.system.unassignedDeviceAlert = false;
        store.notify("system");
    });
}
