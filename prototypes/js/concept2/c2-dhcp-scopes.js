// Concept 2: Unified Topology - DHCP Server Scopes & Pools Component (AGENTS.md compliant)
import { store } from '../state.js';

export function renderC2DhcpScopes(container, onReload) {
    const data = store.data;
    const scopes = data.admin.dhcpScopes;

    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
        <div class="card-header table-action-bar">
            <div>
                <h3 class="card-title">📡 Kea DHCP Scopes by Network (${scopes.length})</h3>
                <p class="card-subtitle">Configure host node binding, gateway IP, dynamic IP pools, and lease durations per subnet</p>
            </div>
            <button class="btn btn-primary btn-sm" id="c2-top-add-scope">+ Add Network Scope</button>
        </div>

        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Network Scope</th><th>Host Node</th><th>Interface</th><th>Subnet</th><th>Gateway</th>
                        <th>Dynamic Pool Range</th><th>Lease Duration</th><th>Status</th><th>Actions</th>
                    </tr>
                </thead>
                <tbody id="c2-dhcp-tbody">
                    ${scopes.map(s => `
                        <tr id="c2-sc-row-${s.id}">
                            <td><strong>${s.name}</strong></td>
                            <td>
                                <span class="badge ${s.nodeId.includes('gateway') ? 'badge-info' : 'badge-neutral'}">
                                    ${s.nodeId.includes('gateway') ? '🛡️' : '🖥️'} ${s.nodeId}
                                </span>
                            </td>
                            <td><code>${s.interface}</code></td>
                            <td><code>${s.subnet}</code></td>
                            <td><code>${s.gateway}</code></td>
                            <td><strong><code>${s.poolStart}</code> - <code>${s.poolEnd}</code></strong></td>
                            <td><span class="badge badge-neutral">${s.leaseTimeHuman}</span></td>
                            <td><span class="badge ${s.enabled ? 'badge-success' : 'badge-danger'}">${s.enabled ? 'Enabled' : 'Disabled'}</span></td>
                            <td>
                                <button class="btn btn-secondary btn-sm c2-edit-scope-btn" data-id="${s.id}">Edit</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="c2-bottom-add-scope">+ Add Network Scope</button>
        </div>
    `;

    container.appendChild(card);
    bindC2DhcpEvents(card, scopes, onReload);
}

function bindC2DhcpEvents(card, scopes, onReload) {
    const tbody = card.querySelector('#c2-dhcp-tbody');

    const handleEdit = (id) => {
        const sc = scopes.find(s => s.id === id);
        if (!sc) return;
        const row = card.querySelector(`#c2-sc-row-${id}`);
        if (!row) return;

        row.className = 'inline-edit-row';
        row.innerHTML = `
            <td><input type="text" class="form-input" id="c2-edit-name" value="${sc.name}"></td>
            <td>
                <select class="form-select" id="c2-edit-node">
                    <option value="roost-gateway-01" ${sc.nodeId === 'roost-gateway-01' ? 'selected' : ''}>🛡️ roost-gateway-01</option>
                    <option value="roost-controller-01" ${sc.nodeId === 'roost-controller-01' ? 'selected' : ''}>🖥️ roost-controller-01</option>
                </select>
            </td>
            <td><code>${sc.interface}</code></td>
            <td><code>${sc.subnet}</code></td>
            <td><input type="text" class="form-input" id="c2-edit-gw" value="${sc.gateway}"></td>
            <td>
                <div style="display:flex;gap:4px;align-items:center;">
                    <input type="text" class="form-input" id="c2-edit-pstart" value="${sc.poolStart}" style="width:110px;">
                    <span>-</span>
                    <input type="text" class="form-input" id="c2-edit-pend" value="${sc.poolEnd}" style="width:110px;">
                </div>
            </td>
            <td>
                <select class="form-select" id="c2-edit-ltime">
                    <option value="7200" ${sc.leaseTime == 7200 ? 'selected' : ''}>2 Hours</option>
                    <option value="43200" ${sc.leaseTime == 43200 ? 'selected' : ''}>12 Hours</option>
                    <option value="86400" ${sc.leaseTime == 86400 ? 'selected' : ''}>24 Hours</option>
                    <option value="604800" ${sc.leaseTime == 604800 ? 'selected' : ''}>7 Days</option>
                </select>
            </td>
            <td>
                <select class="form-select" id="c2-edit-en">
                    <option value="true" ${sc.enabled ? 'selected' : ''}>Enabled</option>
                    <option value="false" ${!sc.enabled ? 'selected' : ''}>Disabled</option>
                </select>
            </td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="c2-btn-save">Save</button>
                    <button class="btn btn-secondary btn-sm" id="c2-btn-cancel">Cancel</button>
                </div>
            </td>
        `;

        row.querySelector('#c2-btn-save').onclick = () => {
            const lSel = row.querySelector('#c2-edit-ltime');
            store.updateDhcpScope(id, {
                name: row.querySelector('#c2-edit-name').value,
                nodeId: row.querySelector('#c2-edit-node').value,
                gateway: row.querySelector('#c2-edit-gw').value,
                poolStart: row.querySelector('#c2-edit-pstart').value,
                poolEnd: row.querySelector('#c2-edit-pend').value,
                leaseTime: lSel.value,
                leaseTimeHuman: lSel.options[lSel.selectedIndex].text,
                enabled: row.querySelector('#c2-edit-en').value === 'true'
            });
            onReload();
        };
        row.querySelector('#c2-btn-cancel').onclick = () => onReload();
    };

    const insertAdd = (pos = 'top') => {
        card.querySelector('#c2-inline-add-scope')?.remove();
        const tr = document.createElement('tr');
        tr.id = 'c2-inline-add-scope';
        tr.className = 'inline-edit-row';
        tr.innerHTML = `
            <td><input type="text" class="form-input" id="c2-new-name" placeholder="Lab Subnet"></td>
            <td>
                <select class="form-select" id="c2-new-node">
                    <option value="roost-gateway-01">🛡️ roost-gateway-01</option>
                    <option value="roost-controller-01">🖥️ roost-controller-01</option>
                </select>
            </td>
            <td><input type="text" class="form-input" id="c2-new-iface" placeholder="vlan-lab"></td>
            <td><input type="text" class="form-input" id="c2-new-subnet" placeholder="192.168.40.0/24"></td>
            <td><input type="text" class="form-input" id="c2-new-gw" placeholder="192.168.40.1"></td>
            <td>
                <div style="display:flex;gap:4px;align-items:center;">
                    <input type="text" class="form-input" id="c2-new-pstart" placeholder="192.168.40.100" style="width:110px;">
                    <span>-</span>
                    <input type="text" class="form-input" id="c2-new-pend" placeholder="192.168.40.200" style="width:110px;">
                </div>
            </td>
            <td>
                <select class="form-select" id="c2-new-ltime"><option value="86400">24 Hours</option><option value="7200">2 Hours</option></select>
            </td>
            <td><select class="form-select" id="c2-new-en"><option value="true">Enabled</option><option value="false">Disabled</option></select></td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="c2-save-new">Save</button>
                    <button class="btn btn-secondary btn-sm" id="c2-cancel-new">Cancel</button>
                </div>
            </td>
        `;

        if (pos === 'top') tbody.insertBefore(tr, tbody.firstChild);
        else tbody.appendChild(tr);

        tr.querySelector('#c2-save-new').onclick = () => {
            const name = tr.querySelector('#c2-new-name').value;
            const gw = tr.querySelector('#c2-new-gw').value;
            if (!name || !gw) return alert('Name and Gateway are required');
            const lSel = tr.querySelector('#c2-new-ltime');
            store.addDhcpScope({
                name,
                nodeId: tr.querySelector('#c2-new-node').value,
                interface: tr.querySelector('#c2-new-iface').value || 'vlan-custom',
                subnet: tr.querySelector('#c2-new-subnet').value || '192.168.40.0/24',
                gateway: gw,
                poolStart: tr.querySelector('#c2-new-pstart').value || '192.168.40.100',
                poolEnd: tr.querySelector('#c2-new-pend').value || '192.168.40.200',
                leaseTime: lSel.value,
                leaseTimeHuman: lSel.options[lSel.selectedIndex].text,
                enabled: tr.querySelector('#c2-new-en').value === 'true'
            });
            onReload();
        };
        tr.querySelector('#c2-cancel-new').onclick = () => tr.remove();
    };

    card.querySelector('#c2-top-add-scope')?.addEventListener('click', () => insertAdd('top'));
    card.querySelector('#c2-bottom-add-scope')?.addEventListener('click', () => insertAdd('bottom'));
    card.querySelectorAll('.c2-edit-scope-btn').forEach(b => {
        b.onclick = () => handleEdit(b.dataset.id);
    });
}
