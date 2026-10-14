// Concept 1: SysAdmin Console - DNS Resolver & Query Log (Compliant with AGENTS.md)
import { store } from '../state.js';
import { renderBlockedFeed } from './c1-blocked-feed.js';

export function renderAdminDns(container) {
    const data = store.data;
    const admin = data.admin;

    const renderDnsRows = () => admin.dnsRecords.map(r => `
        <tr id="dns-rec-row-${r.id}">
            <td><strong>${r.domain}</strong></td>
            <td><span class="badge badge-info">${r.type}</span></td>
            <td><code>${r.ip}</code></td>
            <td>
                <div style="display: flex; gap: 6px;">
                    <button class="btn btn-secondary btn-sm edit-dns-btn" data-id="${r.id}">Edit</button>
                    <button class="btn btn-danger btn-sm delete-dns-btn" data-id="${r.id}">Delete</button>
                </div>
            </td>
        </tr>
    `).join('');

    container.innerHTML = `
        <!-- DNS Forwarders & Cache -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">DNS Engine</div>
                <div class="metric-value">Technitium <span style="font-size: 13px; color: var(--accent-emerald);">• v12.1</span></div>
                <div class="metric-sub">Upstream: 1.1.1.1, 8.8.8.8 (DoH)</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Cache Hit Ratio</div>
                <div class="metric-value">88.4% <span style="font-size: 13px; color: var(--text-muted);">(0.2ms avg)</span></div>
                <div class="metric-sub">Cached records: 4,892</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Queries Today</div>
                <div class="metric-value">${store.data.protection.adBlocking.queriesToday.toLocaleString()}</div>
                <div class="metric-sub">Blocked: 18,432 (24.3%)</div>
            </div>
        </div>

        <!-- Local DNS Records Table (Compliant with AGENTS.md) -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📝 Local Domain Name Records (.home.lan)</h3>
                    <p class="card-subtitle">Custom internal hostname resolution overrides</p>
                </div>
            </div>

            <!-- Top Add Button per AGENTS.md -->
            <div class="table-action-bar">
                <span style="font-size: 13px; color: var(--text-muted);">Active Host Records (${admin.dnsRecords.length})</span>
                <button class="btn btn-primary btn-sm add-dns-btn" data-position="top">+ Add DNS Record</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="dns-table">
                    <thead>
                        <tr>
                            <th>Domain Hostname</th>
                            <th>Record Type</th>
                            <th>Target IP Address</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="dns-tbody">
                        ${renderDnsRows()}
                    </tbody>
                </table>
            </div>

            <!-- Bottom Add Button per AGENTS.md -->
            <div class="table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm add-dns-btn" data-position="bottom">+ Add DNS Record</button>
            </div>
        </div>
    `;

    renderBlockedFeed(container, { onReload: () => renderAdminDns(container) });

    const tbody = container.querySelector('#dns-tbody');

    const getFormFields = (r = {}) => `
        <td><input type="text" class="inline-input" id="inp-dns-domain" value="${r.domain || ''}" placeholder="e.g. printer.home.lan"></td>
        <td>
            <select class="inline-select" id="inp-dns-type">
                <option value="A" ${r.type === 'A' ? 'selected' : ''}>A (IPv4)</option>
                <option value="AAAA" ${r.type === 'AAAA' ? 'selected' : ''}>AAAA (IPv6)</option>
                <option value="CNAME" ${r.type === 'CNAME' ? 'selected' : ''}>CNAME</option>
            </select>
        </td>
        <td><input type="text" class="inline-input" id="inp-dns-ip" value="${r.ip || ''}" placeholder="192.168.1.80"></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-dns-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-dns-btn">Cancel</button>
            </div>
        </td>
    `;

    // Inline Add Row per AGENTS.md
    container.querySelectorAll('.add-dns-btn').forEach(btn => {
        btn.onclick = () => {
            container.querySelector('.inline-add-row')?.remove();
            const tr = document.createElement('tr');
            tr.className = 'inline-add-row';
            tr.innerHTML = getFormFields();

            if (btn.dataset.position === 'top') {
                tbody.prepend(tr);
            } else {
                tbody.append(tr);
            }

            tr.querySelector('.cancel-dns-btn').onclick = () => tr.remove();
            tr.querySelector('.save-dns-btn').onclick = () => {
                const domain = tr.querySelector('#inp-dns-domain').value.trim();
                const ip = tr.querySelector('#inp-dns-ip').value.trim();
                if (!domain || !ip) return alert('Please enter domain and IP');
                store.addDnsRecord({
                    domain,
                    type: tr.querySelector('#inp-dns-type').value,
                    ip
                });
            };
        };
    });

    // Inline Edit Row per AGENTS.md
    tbody.onclick = (e) => {
        const editBtn = e.target.closest('.edit-dns-btn');
        const deleteBtn = e.target.closest('.delete-dns-btn');

        if (editBtn) {
            const id = editBtn.dataset.id;
            const r = admin.dnsRecords.find(x => x.id === id);
            if (!r) return;

            const existingRow = container.querySelector(`#dns-rec-row-${id}`);
            if (!existingRow) return;

            const tr = document.createElement('tr');
            tr.className = 'inline-edit-row';
            tr.id = `dns-rec-row-${id}`;
            tr.innerHTML = getFormFields(r);

            existingRow.replaceWith(tr);

            tr.querySelector('.cancel-dns-btn').onclick = () => renderAdminDns(container);
            tr.querySelector('.save-dns-btn').onclick = () => {
                r.domain = tr.querySelector('#inp-dns-domain').value.trim();
                r.type = tr.querySelector('#inp-dns-type').value;
                r.ip = tr.querySelector('#inp-dns-ip').value.trim();
                renderAdminDns(container);
            };
        }

        if (deleteBtn) {
            if (confirm('Delete this DNS record?')) {
                store.deleteDnsRecord(deleteBtn.dataset.id);
            }
        }
    };
}
