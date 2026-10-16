// Concept 1: Household Hub - Devices Management (Compliant with AGENTS.md)
import { store } from '../state.js';

let activeCategory = 'all';
let searchQuery = '';

export function renderHouseholdDevices(container) {
    const data = store.data;

    let filtered = data.devices.filter(d => {
        const matchesSearch = !searchQuery ||
            d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            d.mac.toLowerCase().includes(searchQuery.toLowerCase()) ||
            d.ip.includes(searchQuery);
        if (!matchesSearch) return false;
        if (activeCategory === 'family') return ['dad', 'mom', 'alice', 'bob'].includes(d.owner);
        if (activeCategory === 'entertainment') return (d.tags || []).includes('entertainment');
        if (activeCategory === 'iot') return d.zone === 'iot';
        if (activeCategory === 'guest') return d.zone === 'guest';
        return true;
    });

    const renderRows = () => filtered.map(d => {
        const ownerObj = data.people.find(p => p.id === d.owner);
        const ownerLabel = ownerObj ? `${ownerObj.avatar} ${ownerObj.name}` : (d.owner || '<em>Unassigned</em>');
        const isPaused = d.status === 'paused' || d.status === 'blocked';
        return `
            <tr id="dev-row-${d.mac.replace(/:/g, '')}">
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 20px;">${d.icon}</span>
                        <div>
                            <strong class="dev-name-link" data-mac="${d.mac}" style="cursor: pointer; color: var(--brand-primary);">${d.name}</strong>
                            <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">${d.mac}</div>
                        </div>
                    </div>
                </td>
                <td>${ownerLabel}</td>
                <td>${d.location || '-'}</td>
                <td><code>${d.ip}</code></td>
                <td><span class="badge ${d.zone === 'iot' ? 'badge-warning' : d.zone === 'guest' ? 'badge-info' : 'badge-neutral'}">${d.zone.toUpperCase()}</span></td>
                <td>
                    <button class="btn btn-sm ${isPaused ? 'btn-danger' : 'btn-success'} pause-dev-btn" data-mac="${d.mac}">
                        ${isPaused ? '⏸ Paused' : '🟢 Active'}
                    </button>
                </td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary btn-sm edit-dev-btn" data-mac="${d.mac}">Edit</button>
                        <button class="btn btn-danger btn-sm delete-dev-btn" data-mac="${d.mac}">Delete</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    container.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📱 Household Devices</h3>
                    <p class="card-subtitle">Control network access, static IPs, and ownership for all connected hardware</p>
                </div>
            </div>

            <div class="c2-directory-controls">
                <div class="c1-nav-tabs">
                    <button class="c1-nav-link cat-tab ${activeCategory === 'all' ? 'active' : ''}" data-cat="all">All (${data.devices.length})</button>
                    <button class="c1-nav-link cat-tab ${activeCategory === 'family' ? 'active' : ''}" data-cat="family">Family</button>
                    <button class="c1-nav-link cat-tab ${activeCategory === 'entertainment' ? 'active' : ''}" data-cat="entertainment">Media / TV</button>
                    <button class="c1-nav-link cat-tab ${activeCategory === 'iot' ? 'active' : ''}" data-cat="iot">Smart Home</button>
                    <button class="c1-nav-link cat-tab ${activeCategory === 'guest' ? 'active' : ''}" data-cat="guest">Guests</button>
                </div>
                <input type="text" class="c2-search-input" id="dev-search-input" placeholder="🔍 Search device name, MAC or IP..." value="${searchQuery}">
            </div>

            <!-- Top Add Button per AGENTS.md -->
            <div class="table-action-bar">
                <span style="font-size: 13px; color: var(--text-muted);">Showing ${filtered.length} devices</span>
                <button class="btn btn-primary btn-sm add-dev-btn" data-position="top">+ Register Device</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="devices-table">
                    <thead>
                        <tr>
                            <th>Device</th><th>Assigned Owner</th><th>Room Location</th><th>IP Address</th>
                            <th>Network Zone</th><th>Internet Access</th><th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="devices-tbody">${renderRows()}</tbody>
                </table>
            </div>

            <!-- Bottom Add Button per AGENTS.md -->
            <div class="table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm add-dev-btn" data-position="bottom">+ Register Device</button>
            </div>
        </div>
        <div id="dev-drawer-container"></div>
    `;

    const tbody = container.querySelector('#devices-tbody');

    const getFormFields = (d = {}) => `
        <td>
            <input type="text" class="inline-input" id="inp-dev-name" value="${d.name || ''}" placeholder="e.g. iPad Pro">
            <input type="text" class="inline-input" id="inp-dev-mac" value="${d.mac || ''}" placeholder="MAC (aa:bb:cc:dd:ee:ff)" style="margin-top: 4px;">
        </td>
        <td>
            <select class="inline-select" id="inp-dev-owner">
                <option value="">-- None (Household) --</option>
                ${data.people.map(p => `<option value="${p.id}" ${d.owner === p.id ? 'selected' : ''}>${p.name}</option>`).join('')}
            </select>
        </td>
        <td>
            <select class="inline-select" id="inp-dev-loc">
                <option value="Living Room" ${d.location === 'Living Room' ? 'selected' : ''}>Living Room</option>
                <option value="Office" ${d.location === 'Office' ? 'selected' : ''}>Office</option>
                <option value="Kitchen" ${d.location === 'Kitchen' ? 'selected' : ''}>Kitchen</option>
                <option value="Kids Bedroom" ${d.location === 'Kids Bedroom' ? 'selected' : ''}>Kids Bedroom</option>
                <option value="Hallway" ${d.location === 'Hallway' ? 'selected' : ''}>Hallway</option>
            </select>
        </td>
        <td><input type="text" class="inline-input" id="inp-dev-ip" value="${d.staticIp || d.ip || ''}" placeholder="Static IP (Optional)"></td>
        <td>
            <select class="inline-select" id="inp-dev-zone">
                <option value="lan" ${d.zone === 'lan' ? 'selected' : ''}>Household LAN</option>
                <option value="iot" ${d.zone === 'iot' ? 'selected' : ''}>Smart Home IoT</option>
                <option value="guest" ${d.zone === 'guest' ? 'selected' : ''}>Guest Wi-Fi</option>
            </select>
        </td>
        <td><span class="badge badge-neutral">Normal</span></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-dev-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-dev-btn">Cancel</button>
            </div>
        </td>
    `;

    // Filter tabs & Search
    container.querySelectorAll('.cat-tab').forEach(b => {
        b.onclick = () => { activeCategory = b.dataset.cat; renderHouseholdDevices(container); };
    });
    const searchInp = container.querySelector('#dev-search-input');
    searchInp.oninput = (e) => { searchQuery = e.target.value; tbody.innerHTML = renderRows(); };

    // Inline Add Row per AGENTS.md
    container.querySelectorAll('.add-dev-btn').forEach(btn => {
        btn.onclick = () => {
            container.querySelector('.inline-add-row')?.remove();
            const tr = document.createElement('tr');
            tr.className = 'inline-add-row';
            tr.innerHTML = getFormFields();

            if (btn.dataset.position === 'top') tbody.prepend(tr);
            else tbody.append(tr);

            tr.querySelector('.cancel-dev-btn').onclick = () => tr.remove();
            tr.querySelector('.save-dev-btn').onclick = () => {
                const mac = tr.querySelector('#inp-dev-mac').value.trim();
                const name = tr.querySelector('#inp-dev-name').value.trim();
                if (!mac || !name) return alert('Please enter both device name and MAC address');
                store.addDevice({
                    mac, name,
                    owner: tr.querySelector('#inp-dev-owner').value,
                    location: tr.querySelector('#inp-dev-loc').value,
                    staticIp: tr.querySelector('#inp-dev-ip').value.trim(),
                    zone: tr.querySelector('#inp-dev-zone').value
                });
            };
        };
    });

    // Inline Edit Row & Action buttons
    tbody.onclick = (e) => {
        const pauseBtn = e.target.closest('.pause-dev-btn');
        const editBtn = e.target.closest('.edit-dev-btn');
        const deleteBtn = e.target.closest('.delete-dev-btn');
        const nameLink = e.target.closest('.dev-name-link');

        if (pauseBtn) store.togglePauseDevice(pauseBtn.dataset.mac);
        if (deleteBtn && confirm('Forget and delete this device?')) store.deleteDevice(deleteBtn.dataset.mac);
        if (nameLink) openDeviceDrawer(nameLink.dataset.mac, container);

        if (editBtn) {
            const mac = editBtn.dataset.mac;
            const d = store.data.devices.find(x => x.mac === mac);
            if (!d) return;

            const rowId = `dev-row-${mac.replace(/:/g, '')}`;
            const existingRow = container.querySelector(`#${rowId}`);
            if (!existingRow) return;

            const tr = document.createElement('tr');
            tr.className = 'inline-edit-row';
            tr.id = rowId;
            tr.innerHTML = getFormFields(d);

            existingRow.replaceWith(tr);
            tr.querySelector('.cancel-dev-btn').onclick = () => renderHouseholdDevices(container);
            tr.querySelector('.save-dev-btn').onclick = () => {
                store.updateDevice(mac, {
                    name: tr.querySelector('#inp-dev-name').value.trim(),
                    owner: tr.querySelector('#inp-dev-owner').value,
                    location: tr.querySelector('#inp-dev-loc').value,
                    staticIp: tr.querySelector('#inp-dev-ip').value.trim(),
                    zone: tr.querySelector('#inp-dev-zone').value
                });
            };
        }
    };
}

function openDeviceDrawer(mac, container) {
    const d = store.data.devices.find(x => x.mac === mac);
    if (!d) return;
    const drawer = container.querySelector('#dev-drawer-container');
    drawer.innerHTML = `
        <div class="drawer-backdrop" id="drawer-backdrop">
            <div class="drawer-panel">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
                    <div>
                        <span style="font-size: 32px;">${d.icon}</span>
                        <h3 style="font-size: 18px; font-weight: 700; margin-top: 6px;">${d.name}</h3>
                        <p style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);">${d.mac}</p>
                    </div>
                    <button class="btn btn-ghost btn-sm" id="close-drawer-btn" style="font-size: 18px;">✕</button>
                </div>
                <div class="card" style="padding: 14px; margin-bottom: 16px;">
                    <h4 style="font-size: 13px; font-weight: 600; margin-bottom: 10px;">Connection Diagnostics</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                        <div><span style="color: var(--text-muted);">IP Address:</span> <code>${d.ip}</code></div>
                        <div><span style="color: var(--text-muted);">Wi-Fi Signal:</span> <strong>${d.signal} dBm</strong></div>
                        <div><span style="color: var(--text-muted);">Rx Rate:</span> <strong>${d.rxMbps} Mbps</strong></div>
                        <div><span style="color: var(--text-muted);">Tx Rate:</span> <strong>${d.txMbps} Mbps</strong></div>
                        <div><span style="color: var(--text-muted);">Vendor:</span> <strong>${d.vendor}</strong></div>
                        <div><span style="color: var(--text-muted);">Location:</span> <strong>${d.location}</strong></div>
                    </div>
                </div>
                <div style="display: flex; gap: 10px; margin-top: auto;">
                    <button class="btn ${d.status === 'paused' ? 'btn-success' : 'btn-danger'}" id="drawer-toggle-pause" style="flex: 1;">
                        ${d.status === 'paused' ? 'Unpause Access' : 'Pause Internet Access'}
                    </button>
                </div>
            </div>
        </div>
    `;
    drawer.querySelector('#close-drawer-btn').onclick = () => drawer.innerHTML = '';
    drawer.querySelector('#drawer-backdrop').onclick = (e) => {
        if (e.target.id === 'drawer-backdrop') drawer.innerHTML = '';
    };
    drawer.querySelector('#drawer-toggle-pause').onclick = () => {
        store.togglePauseDevice(mac);
        drawer.innerHTML = '';
    };
}
