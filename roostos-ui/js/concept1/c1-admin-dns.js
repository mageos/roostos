// Concept 1: SysAdmin Console - DNS Resolver & Query Log (Compliant with AGENTS.md)
import { store } from '../state.js';
import { renderBlockedFeed } from './c1-blocked-feed.js';

export function renderAdminDns(container) {
    const data = store.data;
    const admin = data.admin;

    const renderDnsRows = () => {
        if (admin.dnsRecords.length === 0) {
            return `<tr><td colspan="4" style="text-align:center; padding: 24px; color: var(--text-muted);">No custom DNS records configured. Click "+ Add DNS Record" to create one.</td></tr>`;
        }
        return admin.dnsRecords.map(r => `
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
    };

    const forwarders = (admin.dnsForwarders || ['1.1.1.1', '8.8.8.8']).join(', ');
    const domainSuffix = data.system.domain || 'lan';

    container.innerHTML = `
        <!-- DNS Forwarders & Cache -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">DNS Resolver</div>
                <div class="metric-value">RoostDNS <span style="font-size: 13px; color: var(--accent-emerald);">• Active</span></div>
                <div class="metric-sub">Upstream: ${forwarders}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Ad & Tracker Shield</div>
                <div class="metric-value">${data.protection.adBlocking.enabled ? 'Enabled' : 'Disabled'}</div>
                <div class="metric-sub">SafeSearch: ${data.protection.safeSearch.enabled ? 'Active' : 'Off'}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Queries Today</div>
                <div class="metric-value">${store.data.protection.adBlocking.queriesToday.toLocaleString()}</div>
                <div class="metric-sub">Blocked Today: ${store.data.protection.adBlocking.blockedToday.toLocaleString()}</div>
            </div>
        </div>

        <!-- Root CA & Automated SSL Certificate Authority Card -->
        <div class="card" style="border-left: 4px solid var(--accent-emerald);">
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">🔒 RoostOS Internal Root Certificate Authority & ACME SSL</h3>
                    <p class="card-subtitle">Local X.509 PKI for LAN microservices and automated Let's Encrypt TLS issuance</p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                    <a href="/api/v1/system/certificates/ca.crt" download="roostos-root-ca.crt" class="btn btn-primary btn-sm" id="btn-download-ca">
                        📥 Download Root CA (.crt)
                    </a>
                </div>
            </div>
            <div style="font-size: 13px; color: var(--text-muted); line-height: 1.5; margin-bottom: 8px;">
                Download and install <code>roostos-root-ca.crt</code> into your phone, tablet, or browser trust store to enable trusted HTTPS encryption for all local LAN devices (e.g. <code>*.${domainSuffix}</code>) without browser security warnings.
            </div>
        </div>

        <!-- Local DNS Records Table (Compliant with AGENTS.md) -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📝 Local Domain Name Records (.${domainSuffix})</h3>
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
                const domain = tr.querySelector('#inp-dns-domain').value.trim();
                const ip = tr.querySelector('#inp-dns-ip').value.trim();
                if (!domain || !ip) return alert('Please enter domain and IP');
                store.addDnsRecord({
                    id,
                    domain,
                    type: tr.querySelector('#inp-dns-type').value,
                    ip
                });
            };
        }

        if (deleteBtn) {
            if (confirm('Delete this DNS record?')) {
                store.deleteDnsRecord(deleteBtn.dataset.id);
            }
        }
    };
}
