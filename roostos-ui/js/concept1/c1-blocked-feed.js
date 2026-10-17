// Shared Component: Recently Blocked Requests & Threat Feed (AGENTS.md compliant)
import { store } from '../state.js';

let activeBlockedFilter = 'all';

export function renderBlockedFeed(container, options = {}) {
    const data = store.data;
    const allBlocked = data.protection?.blockedRequests || [];
    const isExpert = options.isExpert ?? (store.concept2Density === 'expert' || store.concept1Persona === 'admin');

    let filtered = allBlocked;
    if (activeBlockedFilter === 'ads') filtered = allBlocked.filter(b => b.category.includes('Ad') || b.category.includes('Telemetry'));
    else if (activeBlockedFilter === 'bedtime') filtered = allBlocked.filter(b => b.category.includes('Bedtime') || b.subsystem === 'TimeGuard');
    else if (activeBlockedFilter === 'security') filtered = allBlocked.filter(b => b.subsystem === 'nftables' || b.category.includes('Quarantine') || b.category.includes('Port Scan') || b.category.includes('Isolation'));

    const card = document.createElement('div');
    card.className = 'card';
    card.style.borderLeft = '4px solid var(--accent-rose)';

    card.innerHTML = `
        <div class="card-header table-action-bar">
            <div>
                <h3 class="card-title">🚫 Recently Blocked Requests & Protection Feed (${allBlocked.length})</h3>
                <p class="card-subtitle">Real-time log of blocked ads, trackers, bedtime enforcement, and firewall drops</p>
            </div>
            <span class="badge badge-danger">● Threat Defense Live</span>
        </div>

        <!-- Filter Pills -->
        <div class="c1-nav-tabs" style="margin-bottom: 14px;">
            <button class="c1-nav-link blk-flt-btn ${activeBlockedFilter === 'all' ? 'active' : ''}" data-bflt="all">
                🌐 All Blocked (${allBlocked.length})
            </button>
            <button class="c1-nav-link blk-flt-btn ${activeBlockedFilter === 'ads' ? 'active' : ''}" data-bflt="ads">
                🚫 Ads & Trackers (${allBlocked.filter(b => b.category.includes('Ad') || b.category.includes('Telemetry')).length})
            </button>
            <button class="c1-nav-link blk-flt-btn ${activeBlockedFilter === 'bedtime' ? 'active' : ''}" data-bflt="bedtime">
                🌙 Bedtime & Screentime (${allBlocked.filter(b => b.category.includes('Bedtime') || b.subsystem === 'TimeGuard').length})
            </button>
            <button class="c1-nav-link blk-flt-btn ${activeBlockedFilter === 'security' ? 'active' : ''}" data-bflt="security">
                🛡️ Firewall & Isolation (${allBlocked.filter(b => b.subsystem === 'nftables' || b.category.includes('Quarantine') || b.category.includes('Isolation') || b.category.includes('Port Scan')).length})
            </button>
        </div>

        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Device / Client</th>
                        <th>Blocked Target</th>
                        <th>Subsystem</th>
                        <th>Category & Rule</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${filtered.length === 0 ? `
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 32px 16px; color: var(--text-muted);">
                                🛡️ No blocked requests recorded yet. All active DNS queries and firewall filters are operating normally.
                            </td>
                        </tr>
                    ` : filtered.map(b => `
                        <tr style="${b.allowed ? 'opacity: 0.6; text-decoration: line-through;' : ''}">
                            <td style="white-space: nowrap;">
                                <strong>${b.timeAgo}</strong>
                                <div style="font-size: 10px; color: var(--text-muted);">${b.time}</div>
                            </td>
                            <td>
                                <strong>${b.clientName}</strong>
                                <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">${b.clientIp}</div>
                            </td>
                            <td>
                                <strong style="color: var(--text-main); font-family: var(--font-mono); font-size: 13px;">${b.target}</strong>
                            </td>
                            <td>
                                <span class="badge ${b.subsystem === 'DNS Sinkhole' ? 'badge-info' : b.subsystem === 'TimeGuard' ? 'badge-warning' : 'badge-danger'}">
                                    ${b.subsystem}
                                </span>
                            </td>
                            <td>
                                <div><strong>${b.category}</strong></div>
                                <div style="font-size: 11px; color: var(--text-muted);">${b.rule}</div>
                            </td>
                            <td>
                                <span class="badge ${b.allowed ? 'badge-success' : 'badge-danger'}">
                                    ${b.allowed ? 'Allowed (Whitelisted)' : b.action}
                                </span>
                            </td>
                            <td>
                                ${b.allowed ? `<span style="font-size:11px; color:var(--accent-emerald); font-weight:600;">✓ Allowed</span>` : `
                                    <div style="display: flex; gap: 6px;">
                                        ${b.canAllow ? `<button class="btn btn-secondary btn-sm allow-blk-btn" data-id="${b.id}" title="Whitelist this domain">Allow</button>` : ''}
                                        ${b.canBonus ? `<button class="btn btn-primary btn-sm bonus-blk-btn" data-id="${b.id}" title="Grant +30 min">+30m</button>` : ''}
                                        ${!b.canAllow && !b.canBonus ? `<span style="font-size:11px; color:var(--text-muted);">Blocked</span>` : ''}
                                    </div>
                                `}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;

    container.appendChild(card);

    card.querySelectorAll('.blk-flt-btn').forEach(btn => {
        btn.onclick = () => {
            activeBlockedFilter = btn.dataset.bflt;
            if (options.onReload) options.onReload();
            else {
                card.remove();
                renderBlockedFeed(container, options);
            }
        };
    });

    card.querySelectorAll('.allow-blk-btn').forEach(btn => {
        btn.onclick = () => {
            store.allowBlockedRequest(btn.dataset.id);
            if (options.onReload) options.onReload();
            else {
                card.remove();
                renderBlockedFeed(container, options);
            }
        };
    });

    card.querySelectorAll('.bonus-blk-btn').forEach(btn => {
        btn.onclick = () => {
            const blockedId = btn.dataset.id;
            const item = (store.data.protection?.blockedRequests || []).find(b => b.id === blockedId);
            const personId = item?.personId || (store.data.people.find(p => p.role === 'kid')?.id) || (store.data.people[0]?.id);
            if (personId) {
                store.addBonusScreentime(personId, 30);
                const personName = store.data.people.find(p => p.id === personId)?.name || 'User';
                alert(`Granted +30 minutes bonus time to ${personName}! Wi-Fi unpaused.`);
            }
            store.allowBlockedRequest(blockedId);
            if (options.onReload) options.onReload();
            else {
                card.remove();
                renderBlockedFeed(container, options);
            }
        };
    });
}
