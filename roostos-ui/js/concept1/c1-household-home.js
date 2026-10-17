// Concept 1: Household Hub - Home Dashboard & Pulse
import { store } from '../state.js';

export function renderHouseholdHome(container) {
    const data = store.data;
    const kids = data.people.filter(p => p.role === "kid");
    const allKidsPaused = kids.length > 0 && kids.every(k => k.bedtimeActive);

    const unassigned = data.system.unassignedDevice;
    const alertHtml = (data.system.unassignedDeviceAlert && unassigned) ? `
        <div class="card" style="border-left: 4px solid var(--accent-amber); background: var(--accent-amber-subtle);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 24px;">⚠️</span>
                    <div>
                        <strong style="color: var(--text-main);">New Device Detected: ${unassigned.vendor && unassigned.vendor !== 'Unknown Device' ? unassigned.vendor : `Device ${unassigned.mac.slice(-5)}`}</strong>
                        <p style="font-size: 12px; color: var(--text-muted); margin: 0;">MAC: <code>${unassigned.mac}</code> (IP: ${unassigned.ip}). Quarantined until approved.</p>
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-primary btn-sm" id="btn-allow-quarantine">View in Devices</button>
                    <button class="btn btn-secondary btn-sm" id="btn-dismiss-quarantine">Dismiss</button>
                </div>
            </div>
        </div>
    ` : '';

    const latestBlock = data.protection.blockedRequests?.[0];
    const blockSubtitle = latestBlock
        ? `Latest block: <code>${latestBlock.target}</code> on ${latestBlock.clientName || 'client'} (${latestBlock.timeAgo || 'recently'})`
        : 'Ad-blocking sinkhole & threat defense active';

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
                    <p>${allKidsPaused ? 'All kids paused' : (kids.length > 0 ? `Pause ${kids.map(k => k.name).join(' & ')}` : 'Pause kids screens')}</p>
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
                ${data.people.length === 0 ? `
                    <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted);">
                        <p>No family profiles created yet.</p>
                        <button class="btn btn-primary btn-sm" style="margin-top: 8px;" id="btn-add-first-family">+ Add Family Member</button>
                    </div>
                ` : data.people.map(p => {
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
                                ${p.role === 'kid' ? `<button class="btn btn-secondary btn-sm bonus-time-btn" data-id="${p.id}">+30m</button>` : ''}
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
                        ${data.devices.filter(d => !!d.owner).length} Online
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
                    <p class="card-subtitle">${blockSubtitle}</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-view-blocked-feed">View Blocked Requests →</button>
            </div>
        </div>

        <div id="guest-qr-modal-container"></div>
    `;

    // Event handlers
    container.querySelector('#qa-pause-kids')?.addEventListener('click', () => {
        store.togglePauseKids(!allKidsPaused);
    });
    container.querySelector('#qa-dinner-time')?.addEventListener('click', () => {
        store.triggerDinnerTime(60);
    });
    container.querySelector('#qa-bonus-time')?.addEventListener('click', () => {
        kids.forEach(k => store.addBonusScreentime(k.id, 30));
    });
    container.querySelector('#qa-guest-qr')?.addEventListener('click', () => {
        showGuestWifiModal();
    });
    container.querySelector('#btn-view-all-family')?.addEventListener('click', () => window.c1SwitchTab('family'));
    container.querySelector('#btn-add-first-family')?.addEventListener('click', () => window.c1SwitchTab('family'));
    container.querySelector('#btn-view-all-devices')?.addEventListener('click', () => window.c1SwitchTab('devices'));
    container.querySelector('#btn-view-topo-map')?.addEventListener('click', () => window.c1SwitchTab('topology'));
    container.querySelector('#btn-view-blocked-feed')?.addEventListener('click', () => window.c1SwitchTab('safety'));

    container.querySelectorAll('.toggle-bedtime-btn').forEach(btn => {
        btn.addEventListener('click', () => store.toggleBedtime(btn.dataset.id));
    });
    container.querySelectorAll('.bonus-time-btn').forEach(btn => {
        btn.addEventListener('click', () => store.addBonusScreentime(btn.dataset.id, 30));
    });

    container.querySelector('#btn-allow-quarantine')?.addEventListener('click', () => {
        window.c1SwitchTab('devices');
    });
    container.querySelector('#btn-dismiss-quarantine')?.addEventListener('click', () => {
        store.data.system.unassignedDeviceAlert = false;
        store.notify("system");
    });

    function showGuestWifiModal() {
        const guestNet = data.wifiNetworks.find(w => w.ssid.includes('Guest') || w.isolate) || {
            ssid: 'RoostHome-Guest',
            password: 'GuestWelcome2026'
        };
        const modal = container.querySelector('#guest-qr-modal-container');
        modal.innerHTML = `
            <div class="drawer-backdrop" id="guest-qr-backdrop" style="justify-content: center; align-items: center;">
                <div class="card" style="max-width: 360px; width: 100%; text-align: center; padding: 24px; position: relative;">
                    <button class="btn btn-ghost btn-sm" id="close-guest-qr-btn" style="position: absolute; top: 14px; right: 14px; font-size: 18px;">✕</button>
                    <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">Guest Wi-Fi QR Code</h3>
                    <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 16px;">Scan with phone camera to connect instantly</p>
                    
                    <div style="background: #ffffff; padding: 18px; border-radius: var(--radius-md); display: inline-block; border: 1px solid var(--border-subtle); margin-bottom: 16px;">
                        <svg width="140" height="140" viewBox="0 0 160 160" fill="none">
                            <rect width="160" height="160" fill="white"/>
                            <rect x="10" y="10" width="40" height="40" fill="black"/>
                            <rect x="20" y="20" width="20" height="20" fill="white"/>
                            <rect x="110" y="10" width="40" height="40" fill="black"/>
                            <rect x="120" y="20" width="20" height="20" fill="white"/>
                            <rect x="10" y="110" width="40" height="40" fill="black"/>
                            <rect x="20" y="120" width="20" height="20" fill="white"/>
                            <rect x="60" y="20" width="10" height="30" fill="black"/>
                            <rect x="80" y="10" width="20" height="10" fill="black"/>
                            <rect x="60" y="70" width="40" height="20" fill="black"/>
                            <rect x="20" y="70" width="20" height="20" fill="black"/>
                            <rect x="120" y="70" width="20" height="20" fill="black"/>
                            <rect x="70" y="110" width="30" height="30" fill="black"/>
                        </svg>
                    </div>

                    <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-sm); font-size: 13px; margin-bottom: 16px; text-align: left;">
                        <div>Network: <strong>${guestNet.ssid}</strong></div>
                        <div style="margin-top: 4px;">Password: <code>${guestNet.password || guestNet.passphrase || 'GuestWelcome2026'}</code></div>
                    </div>

                    <button class="btn btn-primary" id="btn-copy-guest-pass" style="width: 100%;">📋 Copy Password</button>
                </div>
            </div>
        `;

        modal.querySelector('#close-guest-qr-btn').onclick = () => { modal.innerHTML = ''; };
        modal.querySelector('#guest-qr-backdrop').onclick = (e) => {
            if (e.target.id === 'guest-qr-backdrop') modal.innerHTML = '';
        };
        modal.querySelector('#btn-copy-guest-pass').onclick = (e) => {
            navigator.clipboard?.writeText(guestNet.password || guestNet.passphrase || 'GuestWelcome2026');
            e.target.textContent = '✓ Copied!';
            setTimeout(() => { modal.innerHTML = ''; }, 1200);
        };
    }
}
