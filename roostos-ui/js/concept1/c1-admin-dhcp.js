// Concept 1: SysAdmin Console - Kea DHCP Server Fleet Scopes & HA (AGENTS.md compliant)
import { store } from '../state.js';
import { renderDhcpReservations } from './c1-admin-dhcp-reservations.js';
import { renderDhcpLeases } from './c1-admin-dhcp-leases.js';

let activeScopeNodeFilter = 'all';

export function renderAdminDhcp(container) {
    const data = store.data;
    const admin = data.admin;
    const allScopes = admin.dhcpScopes;
    const scopes = allScopes.filter(s => activeScopeNodeFilter === 'all' || s.nodeId === activeScopeNodeFilter);
    const nodes = data.cluster.nodes.filter(n => !n.role.includes('Cloud'));

    const renderScopeRow = (s) => `
        <tr id="scope-row-${s.id}">
            <td><strong>${s.name}</strong><div style="font-size:11px;color:var(--text-muted);">Domain: <code>${s.domainName || 'local'}</code></div></td>
            <td>
                <span class="badge ${s.nodeId.includes('gateway') ? 'badge-info' : 'badge-neutral'}">
                    ${s.nodeId.includes('gateway') ? '🛡️' : '🖥️'} ${s.nodeId}
                </span>
                ${s.haStandby && s.haStandby !== 'none' ? `<div style="font-size:10px;color:var(--accent-emerald);margin-top:2px;">HA: ${s.haStandby}</div>` : ''}
            </td>
            <td><code>${s.interface}</code></td>
            <td><code>${s.subnet}</code></td>
            <td><code>${s.gateway}</code></td>
            <td><strong><code>${s.poolStart}</code> - <code>${s.poolEnd}</code></strong><div style="font-size:10px;color:var(--text-muted);">${s.poolSize} IPs (${s.activeLeasesCount || 0} leased)</div></td>
            <td><span class="badge badge-neutral">${s.leaseTimeHuman}</span></td>
            <td><span class="badge ${s.enabled ? 'badge-success' : 'badge-danger'}">${s.enabled ? 'Enabled' : 'Disabled'}</span></td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-secondary btn-sm edit-scope-btn" data-id="${s.id}">Edit</button>
                    ${s.id !== 'scope-lan' ? `<button class="btn btn-danger btn-sm delete-scope-btn" data-id="${s.id}">Remove</button>` : ''}
                </div>
            </td>
        </tr>
    `;

    container.innerHTML = `
        <!-- Multi-Node Kea DHCP Daemon Fleet Card -->
        <div class="card" style="border-left: 4px solid var(--accent-emerald);">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📡 Kea DHCP Server Engine (ISC Kea 2.4)</h3>
                    <p class="card-subtitle">Authoritative lease pools, client discovery, and High-Availability (HA) failover</p>
                </div>
                <span class="badge badge-success">● Kea DHCPv4 Active</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Primary Router Node</div>
                    <div style="font-size: 14px; font-weight: 700; color: var(--brand-primary); margin-top: 2px;">${data.system.hostname}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${allScopes.length} Scopes Active</div>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Cluster Management</div>
                    <div style="font-size: 14px; font-weight: 700; color: var(--accent-indigo); margin-top: 2px;">${nodes.length > 1 ? `${nodes.length} Nodes Synchronized` : 'Standalone Master'}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${nodes.length > 1 ? 'mTLS Sync Active' : 'Local Daemon'}</div>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">HA Protocol & Hook</div>
                    <div style="font-size: 14px; font-weight: 700; color: var(--accent-emerald); margin-top: 2px;">libdhcp_run_script</div>
                    <div style="font-size: 11px; color: var(--text-muted);">Sub-second Real-time Sync</div>
                </div>
                <div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-md);">
                    <div style="font-size: 11px; color: var(--text-muted);">Active Allocated Leases</div>
                    <div style="font-size: 14px; font-weight: 700; margin-top: 2px;">${admin.activeLeases.length} Dynamic + ${data.devices.filter(d => !!d.staticIp).length} Static</div>
                    <div style="font-size: 11px; color: var(--text-muted);">Shared Lease Sync: Active</div>
                </div>
            </div>
        </div>

        <!-- Scopes Table with Fleet Node Filter (AGENTS.md Compliant) -->
        <div class="card">
            <div class="card-header table-action-bar">
                <div>
                    <h3 class="card-title">🎛️ DHCP Scopes & Node Assignments (${scopes.length})</h3>
                    <p class="card-subtitle">Specify authoritative host node, pool range, and HA failover per subnet</p>
                </div>
                <button class="btn btn-primary btn-sm" id="top-add-scope-btn">+ Add Network Scope</button>
            </div>

            <!-- Cluster Node Filter Pills -->
            <div class="c1-nav-tabs" style="margin-bottom: 12px;">
                <button class="c1-nav-link node-flt-btn ${activeScopeNodeFilter === 'all' ? 'active' : ''}" data-nflt="all">
                    🌐 All Nodes (${allScopes.length})
                </button>
                ${nodes.map(n => `
                    <button class="c1-nav-link node-flt-btn ${activeScopeNodeFilter === n.id ? 'active' : ''}" data-nflt="${n.id}">
                        ${(n.role || '').includes('Gateway') ? '🛡️' : '🖥️'} ${n.hostname} (${allScopes.filter(s => s.nodeId === n.id).length})
                    </button>
                `).join('')}
            </div>

            <div class="table-responsive">
                <table class="data-table" id="dhcp-scopes-table">
                    <thead>
                        <tr>
                            <th>Network Scope</th><th>Host Node</th><th>Interface</th><th>Subnet</th>
                            <th>Gateway</th><th>Dynamic Pool</th><th>Lease</th><th>Status</th><th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="dhcp-scopes-tbody">
                        ${scopes.length === 0 ? `
                            <tr><td colspan="9" style="text-align:center; padding: 24px; color: var(--text-muted);">No DHCP scopes configured. Click "+ Add Network Scope" to define one.</td></tr>
                        ` : scopes.map(renderScopeRow).join('')}
                    </tbody>
                </table>
            </div>

            <div class="card-footer table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm" id="bottom-add-scope-btn">+ Add Network Scope</button>
            </div>
        </div>
    `;

    renderDhcpLeases(container, () => renderAdminDhcp(container));
    renderDhcpReservations(container, () => renderAdminDhcp(container));

    bindScopeEvents(container, scopes, nodes);
}

function bindScopeEvents(container, scopes, nodes) {
    const tbody = container.querySelector('#dhcp-scopes-tbody');

    const handleEditScope = (id) => {
        const sc = store.data.admin.dhcpScopes.find(s => s.id === id);
        if (!sc) return;
        const row = container.querySelector(`#scope-row-${id}`);
        if (!row) return;

        row.className = 'inline-edit-row';
        row.innerHTML = `
            <td><input type="text" class="form-input" id="edit-sc-name" value="${sc.name}"></td>
            <td>
                <select class="form-select" id="edit-sc-node">
                    ${nodes.map(n => `<option value="${n.id}" ${sc.nodeId === n.id ? 'selected' : ''}>${(n.role || '').includes('Gateway') ? '🛡️' : '🖥️'} ${n.hostname}</option>`).join('')}
                </select>
                <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">
                    HA: <select class="form-select" id="edit-sc-ha" style="font-size:11px;padding:2px 4px;">
                        <option value="none" ${sc.haStandby === 'none' ? 'selected' : ''}>None</option>
                        ${nodes.map(n => `<option value="${n.id}" ${sc.haStandby === n.id ? 'selected' : ''}>${n.hostname}</option>`).join('')}
                    </select>
                </div>
            </td>
            <td><input type="text" class="form-input" id="edit-sc-iface" value="${sc.interface}"></td>
            <td><input type="text" class="form-input" id="edit-sc-subnet" value="${sc.subnet}"></td>
            <td><input type="text" class="form-input" id="edit-sc-gw" value="${sc.gateway}"></td>
            <td>
                <div style="display:flex;gap:4px;align-items:center;">
                    <input type="text" class="form-input" id="edit-sc-pstart" value="${sc.poolStart}" style="width:105px;">
                    <span>-</span>
                    <input type="text" class="form-input" id="edit-sc-pend" value="${sc.poolEnd}" style="width:105px;">
                </div>
            </td>
            <td>
                <select class="form-select" id="edit-sc-ltime">
                    <option value="7200" ${sc.leaseTime == 7200 ? 'selected' : ''}>2 Hours</option>
                    <option value="43200" ${sc.leaseTime == 43200 ? 'selected' : ''}>12 Hours</option>
                    <option value="86400" ${sc.leaseTime == 86400 ? 'selected' : ''}>24 Hours</option>
                    <option value="604800" ${sc.leaseTime == 604800 ? 'selected' : ''}>7 Days</option>
                </select>
            </td>
            <td>
                <select class="form-select" id="edit-sc-enabled">
                    <option value="true" ${sc.enabled ? 'selected' : ''}>Enabled</option>
                    <option value="false" ${!sc.enabled ? 'selected' : ''}>Disabled</option>
                </select>
            </td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="btn-save-scope">Save</button>
                    <button class="btn btn-secondary btn-sm" id="btn-cancel-scope">Cancel</button>
                </div>
            </td>
        `;

        row.querySelector('#btn-save-scope').onclick = () => {
            const lSelect = row.querySelector('#edit-sc-ltime');
            store.updateDhcpScope(id, {
                name: row.querySelector('#edit-sc-name').value,
                nodeId: row.querySelector('#edit-sc-node').value,
                haStandby: row.querySelector('#edit-sc-ha').value,
                interface: row.querySelector('#edit-sc-iface').value,
                subnet: row.querySelector('#edit-sc-subnet').value,
                gateway: row.querySelector('#edit-sc-gw').value,
                poolStart: row.querySelector('#edit-sc-pstart').value,
                poolEnd: row.querySelector('#edit-sc-pend').value,
                leaseTime: lSelect.value,
                leaseTimeHuman: lSelect.options[lSelect.selectedIndex].text,
                enabled: row.querySelector('#edit-sc-enabled').value === 'true'
            });
            renderAdminDhcp(container);
        };
        row.querySelector('#btn-cancel-scope').onclick = () => renderAdminDhcp(container);
    };

    const insertAddScopeRow = (pos = 'top') => {
        container.querySelector('#inline-add-scope-row')?.remove();
        const tr = document.createElement('tr');
        tr.id = 'inline-add-scope-row';
        tr.className = 'inline-edit-row';
        tr.innerHTML = `
            <td><input type="text" class="form-input" id="new-sc-name" placeholder="Dev VLAN"></td>
            <td>
                <select class="form-select" id="new-sc-node">
                    ${nodes.map(n => `<option value="${n.id}">${(n.role || '').includes('Gateway') ? '🛡️' : '🖥️'} ${n.hostname}</option>`).join('')}
                </select>
            </td>
            <td><input type="text" class="form-input" id="new-sc-iface" placeholder="vlan-dev"></td>
            <td><input type="text" class="form-input" id="new-sc-subnet" placeholder="192.168.60.0/24"></td>
            <td><input type="text" class="form-input" id="new-sc-gw" placeholder="192.168.60.1"></td>
            <td>
                <div style="display:flex;gap:4px;align-items:center;">
                    <input type="text" class="form-input" id="new-sc-pstart" placeholder="192.168.60.100" style="width:105px;">
                    <span>-</span>
                    <input type="text" class="form-input" id="new-sc-pend" placeholder="192.168.60.200" style="width:105px;">
                </div>
            </td>
            <td><select class="form-select" id="new-sc-ltime"><option value="86400">24 Hours</option><option value="7200">2 Hours</option></select></td>
            <td><select class="form-select" id="new-sc-enabled"><option value="true">Enabled</option><option value="false">Disabled</option></select></td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="btn-save-new-scope">Save</button>
                    <button class="btn btn-secondary btn-sm" id="btn-cancel-new-scope">Cancel</button>
                </div>
            </td>
        `;

        if (pos === 'top') tbody.insertBefore(tr, tbody.firstChild);
        else tbody.appendChild(tr);

        tr.querySelector('#btn-save-new-scope').onclick = () => {
            const name = tr.querySelector('#new-sc-name').value;
            const gw = tr.querySelector('#new-sc-gw').value;
            if (!name || !gw) return alert('Name and Gateway are required');
            const lSelect = tr.querySelector('#new-sc-ltime');
            store.addDhcpScope({
                name,
                nodeId: tr.querySelector('#new-sc-node').value,
                interface: tr.querySelector('#new-sc-iface').value || 'vlan-custom',
                subnet: tr.querySelector('#new-sc-subnet').value || '192.168.60.0/24',
                gateway: gw,
                poolStart: tr.querySelector('#new-sc-pstart').value || '192.168.60.100',
                poolEnd: tr.querySelector('#new-sc-pend').value || '192.168.60.200',
                leaseTime: lSelect.value,
                leaseTimeHuman: lSelect.options[lSelect.selectedIndex].text,
                enabled: tr.querySelector('#new-sc-enabled').value === 'true'
            });
            renderAdminDhcp(container);
        };
        tr.querySelector('#btn-cancel-new-scope').onclick = () => tr.remove();
    };

    container.querySelector('#top-add-scope-btn')?.addEventListener('click', () => insertAddScopeRow('top'));
    container.querySelector('#bottom-add-scope-btn')?.addEventListener('click', () => insertAddScopeRow('bottom'));

    container.querySelectorAll('.edit-scope-btn').forEach(b => {
        b.onclick = () => handleEditScope(b.dataset.id);
    });

    container.querySelectorAll('.delete-scope-btn').forEach(b => {
        b.onclick = () => {
            if (confirm('Delete this DHCP scope?')) {
                store.deleteDhcpScope(b.dataset.id);
                renderAdminDhcp(container);
            }
        };
    });

    container.querySelectorAll('.node-flt-btn').forEach(b => {
        b.onclick = () => {
            activeScopeNodeFilter = b.dataset.nflt;
            renderAdminDhcp(container);
        };
    });
}
