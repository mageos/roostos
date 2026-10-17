// Concept 1: SysAdmin Console - Firewall Rules & Port Forwards (Compliant with AGENTS.md)
import { store } from '../state.js';

export function renderAdminFirewall(container) {
    const data = store.data;
    const admin = data.admin;

    const renderPfRows = () => {
        if (admin.portForwards.length === 0) {
            return `<tr><td colspan="6" style="text-align:center; padding: 24px; color: var(--text-muted);">No port forwarding rules configured.</td></tr>`;
        }
        return admin.portForwards.map(p => `
            <tr id="pf-row-${p.id}">
                <td><strong>${p.name}</strong></td>
                <td><span class="badge badge-info">${p.proto}</span></td>
                <td><code>${p.wanPort}</code></td>
                <td><code>${p.lanIp}:${p.lanPort}</code></td>
                <td>${p.hits.toLocaleString()} hits</td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary btn-sm edit-pf-btn" data-id="${p.id}">Edit</button>
                        <button class="btn btn-danger btn-sm delete-pf-btn" data-id="${p.id}">Delete</button>
                    </div>
                </td>
            </tr>
        `).join('');
    };

    container.innerHTML = `
        <!-- Zone Security Policy Matrix -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🛡️ nftables Zone Isolation Matrix</h3>
                    <p class="card-subtitle">Inter-zone stateful packet filtering and forwarding policy</p>
                </div>
            </div>

            <div class="table-responsive">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>From Zone</th>
                            <th>To WAN (Internet)</th>
                            <th>To Household LAN</th>
                            <th>To Smart Home IoT</th>
                            <th>To Guest Network</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Household LAN</strong></td>
                            <td><span class="badge badge-success">ALLOW (NAT)</span></td>
                            <td><span class="badge badge-success">ALLOW</span></td>
                            <td><span class="badge badge-success">ALLOW</span></td>
                            <td><span class="badge badge-warning">BLOCK</span></td>
                        </tr>
                        <tr>
                            <td><strong>Smart Home (IoT)</strong></td>
                            <td><span class="badge badge-warning">RESTRICTED</span></td>
                            <td><span class="badge badge-danger">DROP (Blocked)</span></td>
                            <td><span class="badge badge-success">ALLOW</span></td>
                            <td><span class="badge badge-danger">DROP (Blocked)</span></td>
                        </tr>
                        <tr>
                            <td><strong>Guest Wi-Fi</strong></td>
                            <td><span class="badge badge-success">ALLOW (NAT)</span></td>
                            <td><span class="badge badge-danger">DROP (Blocked)</span></td>
                            <td><span class="badge badge-danger">DROP (Blocked)</span></td>
                            <td><span class="badge badge-success">CLIENT ISOLATION</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Port Forwarding Rules Table (Compliant with AGENTS.md) -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🔀 Destination NAT (Port Forwarding)</h3>
                    <p class="card-subtitle">Expose internal services through WAN IP interfaces</p>
                </div>
            </div>

            <!-- Top Add Button per AGENTS.md -->
            <div class="table-action-bar">
                <span style="font-size: 13px; color: var(--text-muted);">Active Forward Rules (${admin.portForwards.length})</span>
                <button class="btn btn-primary btn-sm add-pf-btn" data-position="top">+ Add Port Forward</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="pf-table">
                    <thead>
                        <tr>
                            <th>Rule Name</th>
                            <th>Protocol</th>
                            <th>WAN Port</th>
                            <th>Target Destination</th>
                            <th>Packet Hits</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="pf-tbody">
                        ${renderPfRows()}
                    </tbody>
                </table>
            </div>

            <!-- Bottom Add Button per AGENTS.md -->
            <div class="table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm add-pf-btn" data-position="bottom">+ Add Port Forward</button>
            </div>
        </div>
    `;

    const tbody = container.querySelector('#pf-tbody');

    const getFormFields = (p = {}) => `
        <td><input type="text" class="inline-input" id="inp-pf-name" value="${p.name || ''}" placeholder="e.g. WireGuard"></td>
        <td>
            <select class="inline-select" id="inp-pf-proto">
                <option value="TCP" ${p.proto === 'TCP' ? 'selected' : ''}>TCP</option>
                <option value="UDP" ${p.proto === 'UDP' ? 'selected' : ''}>UDP</option>
                <option value="TCP/UDP" ${p.proto === 'TCP/UDP' ? 'selected' : ''}>TCP/UDP</option>
            </select>
        </td>
        <td><input type="number" class="inline-input" id="inp-pf-wan" value="${p.wanPort || ''}" placeholder="8080"></td>
        <td>
            <div style="display: flex; gap: 4px;">
                <input type="text" class="inline-input" id="inp-pf-ip" value="${p.lanIp || ''}" placeholder="192.168.1.50">
                <input type="number" class="inline-input" id="inp-pf-port" value="${p.lanPort || ''}" placeholder="80" style="width: 80px;">
            </div>
        </td>
        <td><span class="badge badge-neutral">0 hits</span></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-pf-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-pf-btn">Cancel</button>
            </div>
        </td>
    `;

    // Inline Add Row per AGENTS.md
    container.querySelectorAll('.add-pf-btn').forEach(btn => {
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

            tr.querySelector('.cancel-pf-btn').onclick = () => tr.remove();
            tr.querySelector('.save-pf-btn').onclick = () => {
                const name = tr.querySelector('#inp-pf-name').value.trim();
                const wanPort = tr.querySelector('#inp-pf-wan').value;
                const lanIp = tr.querySelector('#inp-pf-ip').value.trim();
                const lanPort = tr.querySelector('#inp-pf-port').value;

                if (!name || !wanPort || !lanIp) return alert('Please fill in required fields');

                store.addPortForward({
                    name,
                    proto: tr.querySelector('#inp-pf-proto').value,
                    wanPort: Number(wanPort),
                    lanIp,
                    lanPort: Number(lanPort || wanPort)
                });
            };
        };
    });

    // Inline Edit Row per AGENTS.md
    tbody.onclick = (e) => {
        const editBtn = e.target.closest('.edit-pf-btn');
        const deleteBtn = e.target.closest('.delete-pf-btn');

        if (editBtn) {
            const id = editBtn.dataset.id;
            const p = admin.portForwards.find(x => x.id === id);
            if (!p) return;

            const existingRow = container.querySelector(`#pf-row-${id}`);
            if (!existingRow) return;

            const tr = document.createElement('tr');
            tr.className = 'inline-edit-row';
            tr.id = `pf-row-${id}`;
            tr.innerHTML = getFormFields(p);

            existingRow.replaceWith(tr);

            tr.querySelector('.cancel-pf-btn').onclick = () => renderAdminFirewall(container);
            tr.querySelector('.save-pf-btn').onclick = () => {
                const name = tr.querySelector('#inp-pf-name').value.trim();
                const wanPort = tr.querySelector('#inp-pf-wan').value;
                const lanIp = tr.querySelector('#inp-pf-ip').value.trim();
                const lanPort = tr.querySelector('#inp-pf-port').value;
                if (!name || !wanPort || !lanIp) return alert('Please fill in required fields');

                store.addPortForward({
                    id,
                    name,
                    proto: tr.querySelector('#inp-pf-proto').value,
                    wanPort: Number(wanPort),
                    lanIp,
                    lanPort: Number(lanPort || wanPort)
                });
            };
        }

        if (deleteBtn) {
            if (confirm('Delete this port forwarding rule?')) {
                store.deletePortForward(deleteBtn.dataset.id);
            }
        }
    };
}
