// Concept 2: Unified Topology - Directory (People, Devices & Rooms per AGENTS.md)
import { store } from '../state.js';

let directoryTab = 'all';

export function renderDirectoryView(container) {
    const data = store.data;
    const isExpert = store.concept2Density === 'expert';

    const renderDeviceRows = () => data.devices.map(d => `
        <tr id="c2-dev-row-${d.mac.replace(/:/g, '')}">
            <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span>${d.icon}</span>
                    <div>
                        <strong>${d.name}</strong>
                        ${isExpert ? `<div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">${d.hostname && d.hostname !== d.name ? `${d.hostname} • ` : ''}${d.mac}</div>` : ''}
                    </div>
                </div>
            </td>
            <td>${d.owner || '<em>Unassigned</em>'}</td>
            <td>${d.location}</td>
            <td><code>${d.ip}</code></td>
            ${isExpert ? `
                <td>${d.staticIp ? `<code>${d.staticIp}</code>` : '<span style="color:var(--text-muted);">Dynamic</span>'}</td>
                <td><span class="badge badge-neutral">${d.zone.toUpperCase()}</span></td>
                <td>${d.vendor}</td>
            ` : ''}
            <td>
                <button class="btn btn-sm ${d.status === 'online' ? 'btn-success' : 'btn-danger'} toggle-pause-btn" data-mac="${d.mac}">
                    ${d.status === 'online' ? 'Active' : 'Paused'}
                </button>
            </td>
            <td>
                <div style="display: flex; gap: 6px;">
                    <button class="btn btn-secondary btn-sm edit-dev-btn" data-mac="${d.mac}">Edit</button>
                    <button class="btn btn-danger btn-sm delete-dev-btn" data-mac="${d.mac}">Delete</button>
                </div>
            </td>
        </tr>
    `).join('');

    container.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">👥 Unified Directory & Inventory</h3>
                    <p class="card-subtitle">Integrated view of household people, physical rooms, and network hardware</p>
                </div>
            </div>

            <!-- Segmented filter buttons -->
            <div class="c2-directory-controls">
                <div class="c1-nav-tabs">
                    <button class="c1-nav-link tab-btn ${directoryTab === 'all' ? 'active' : ''}" data-tab="all">All Devices (${data.devices.length})</button>
                    <button class="c1-nav-link tab-btn ${directoryTab === 'people' ? 'active' : ''}" data-tab="people">By Family Member</button>
                    <button class="c1-nav-link tab-btn ${directoryTab === 'rooms' ? 'active' : ''}" data-tab="rooms">By Room / Location</button>
                </div>
            </div>

            ${directoryTab === 'people' ? `
                <!-- Grouped by Family Member Cards -->
                <div class="c1-family-grid">
                    ${data.people.map(p => {
                        const devs = data.devices.filter(d => d.owner === p.id);
                        return `
                            <div class="c1-family-card" style="border-left: 4px solid ${p.color};">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span style="font-size: 28px;">${p.avatar}</span>
                                    <div>
                                        <h4 style="font-size: 15px; font-weight: 700;">${p.name}</h4>
                                        <p style="font-size: 12px; color: var(--text-muted);">${devs.length} assigned devices</p>
                                    </div>
                                </div>
                                <div style="font-size: 12px; display: flex; flex-direction: column; gap: 4px;">
                                    ${devs.map(d => `<div>• <strong>${d.name}</strong> (<code>${d.ip}</code>)</div>`).join('') || '<em>No devices assigned</em>'}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            ` : directoryTab === 'rooms' ? `
                <!-- Grouped by Room Cards -->
                <div class="c1-family-grid">
                    ${data.rooms.map(r => {
                        const devs = data.devices.filter(d => d.location.toLowerCase() === r.name.toLowerCase());
                        return `
                            <div class="c1-family-card">
                                <h4 style="font-size: 15px; font-weight: 700;">📍 ${r.name}</h4>
                                <p style="font-size: 12px; color: var(--text-muted);">${devs.length} devices in room</p>
                                <div style="font-size: 12px; display: flex; flex-direction: column; gap: 4px; margin-top: 6px;">
                                    ${devs.map(d => `<div>• <strong>${d.name}</strong></div>`).join('') || '<em>Empty room</em>'}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            ` : `
                <!-- Full Table per AGENTS.md -->
                <div class="table-action-bar">
                    <span style="font-size: 13px; color: var(--text-muted);">Registered Devices (${data.devices.length})</span>
                    <button class="btn btn-primary btn-sm add-dev-btn" data-position="top">+ Add Device</button>
                </div>

                <div class="table-responsive">
                    <table class="data-table" id="c2-dev-table">
                        <thead>
                            <tr>
                                <th>Device Name</th>
                                <th>Owner</th>
                                <th>Room Location</th>
                                <th>IP Address</th>
                                ${isExpert ? '<th>Static IP Reservation</th><th>VLAN Zone</th><th>Vendor OUI</th>' : ''}
                                <th>Access</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="c2-dev-tbody">
                            ${renderDeviceRows()}
                        </tbody>
                    </table>
                </div>

                <div class="table-action-bar" style="margin-top: 12px;">
                    <span></span>
                    <button class="btn btn-primary btn-sm add-dev-btn" data-position="bottom">+ Add Device</button>
                </div>
            `}
        </div>
    `;

    // Filter tabs
    container.querySelectorAll('.tab-btn').forEach(b => {
        b.onclick = () => {
            directoryTab = b.dataset.tab;
            renderDirectoryView(container);
        };
    });

    const tbody = container.querySelector('#c2-dev-tbody');
    if (!tbody) return;

    const getFormFields = (d = {}) => `
        <td>
            <input type="text" class="inline-input" id="inp-c2-name" value="${d.name || ''}" placeholder="Name">
            <input type="text" class="inline-input" id="inp-c2-mac" value="${d.mac || ''}" placeholder="MAC (aa:bb:cc:dd:ee:ff)" style="margin-top:4px;">
        </td>
        <td>
            <select class="inline-select" id="inp-c2-owner">
                <option value="">-- None --</option>
                ${data.people.map(p => `<option value="${p.id}" ${d.owner === p.id ? 'selected' : ''}>${p.name}</option>`).join('')}
            </select>
        </td>
        <td><input type="text" class="inline-input" id="inp-c2-loc" value="${d.location || 'Living Room'}"></td>
        <td><input type="text" class="inline-input" id="inp-c2-ip" value="${d.staticIp || d.ip || ''}" placeholder="192.168.1.50"></td>
        ${isExpert ? `
            <td><input type="text" class="inline-input" id="inp-c2-static" value="${d.staticIp || ''}"></td>
            <td>
                <select class="inline-select" id="inp-c2-zone">
                    <option value="lan" ${d.zone === 'lan' ? 'selected' : ''}>LAN</option>
                    <option value="iot" ${d.zone === 'iot' ? 'selected' : ''}>IoT</option>
                    <option value="guest" ${d.zone === 'guest' ? 'selected' : ''}>Guest</option>
                </select>
            </td>
            <td><input type="text" class="inline-input" id="inp-c2-vendor" value="${d.vendor || 'Apple'}"></td>
        ` : ''}
        <td><span class="badge badge-neutral">Active</span></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-c2-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-c2-btn">Cancel</button>
            </div>
        </td>
    `;

    // Inline Add per AGENTS.md
    container.querySelectorAll('.add-dev-btn').forEach(btn => {
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

            tr.querySelector('.cancel-c2-btn').onclick = () => tr.remove();
            tr.querySelector('.save-c2-btn').onclick = () => {
                const mac = tr.querySelector('#inp-c2-mac').value.trim();
                const name = tr.querySelector('#inp-c2-name').value.trim();
                if (!mac || !name) return alert('Enter name and MAC');
                store.addDevice({
                    mac,
                    name,
                    owner: tr.querySelector('#inp-c2-owner').value,
                    location: tr.querySelector('#inp-c2-loc').value,
                    staticIp: tr.querySelector('#inp-c2-ip').value.trim(),
                    zone: isExpert ? tr.querySelector('#inp-c2-zone').value : 'lan'
                });
            };
        };
    });

    // Inline Edit per AGENTS.md
    tbody.onclick = (e) => {
        const pauseBtn = e.target.closest('.toggle-pause-btn');
        const editBtn = e.target.closest('.edit-dev-btn');
        const deleteBtn = e.target.closest('.delete-dev-btn');

        if (pauseBtn) {
            store.togglePauseDevice(pauseBtn.dataset.mac);
        }

        if (deleteBtn) {
            if (confirm('Delete this device?')) {
                store.deleteDevice(deleteBtn.dataset.mac);
            }
        }

        if (editBtn) {
            const mac = editBtn.dataset.mac;
            const d = store.data.devices.find(x => x.mac === mac);
            if (!d) return;

            const rowId = `c2-dev-row-${mac.replace(/:/g, '')}`;
            const existingRow = container.querySelector(`#${rowId}`);
            if (!existingRow) return;

            const tr = document.createElement('tr');
            tr.className = 'inline-edit-row';
            tr.id = rowId;
            tr.innerHTML = getFormFields(d);

            existingRow.replaceWith(tr);

            tr.querySelector('.cancel-c2-btn').onclick = () => renderDirectoryView(container);
            tr.querySelector('.save-c2-btn').onclick = () => {
                store.updateDevice(mac, {
                    name: tr.querySelector('#inp-c2-name').value.trim(),
                    owner: tr.querySelector('#inp-c2-owner').value,
                    location: tr.querySelector('#inp-c2-loc').value,
                    staticIp: tr.querySelector('#inp-c2-ip').value.trim(),
                    zone: isExpert ? tr.querySelector('#inp-c2-zone').value : d.zone
                });
            };
        }
    };
}
