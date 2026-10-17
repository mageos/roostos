// Concept 1: SysAdmin Console - Static DHCP MAC Reservations Component (AGENTS.md compliant)
import { store } from '../state.js';

export function renderDhcpReservations(container, onReload) {
    const staticDevices = store.data.devices.filter(d => !!d.staticIp);

    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
        <div class="card-header table-action-bar">
            <div>
                <h3 class="card-title">📌 Static DHCP MAC Address Reservations (${staticDevices.length})</h3>
                <p class="card-subtitle">Fixed IP mappings bound by hardware MAC address on Kea DHCP</p>
            </div>
            <button class="btn btn-primary btn-sm" id="top-add-res-btn">+ Add Reservation</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="res-table">
                <thead>
                    <tr><th>Device Name</th><th>MAC Address</th><th>Reserved IP</th><th>Zone</th><th>Actions</th></tr>
                </thead>
                <tbody id="res-tbody">
                    ${staticDevices.length === 0 ? `
                        <tr><td colspan="5" style="text-align:center; padding: 24px; color: var(--text-muted);">No static IP reservations configured.</td></tr>
                    ` : staticDevices.map(d => `
                        <tr id="res-row-${d.mac.replace(/:/g, '')}">
                            <td><strong>${d.name}</strong></td>
                            <td><code>${d.mac}</code></td>
                            <td><code>${d.staticIp}</code></td>
                            <td><span class="badge badge-info">${d.zone.toUpperCase()}</span></td>
                            <td>
                                <div style="display:flex;gap:6px;">
                                    <button class="btn btn-secondary btn-sm edit-res-btn" data-mac="${d.mac}">Edit</button>
                                    <button class="btn btn-danger btn-sm del-res-btn" data-mac="${d.mac}">Remove</button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-res-btn">+ Add Reservation</button>
        </div>
    `;

    container.appendChild(card);
    bindReservationEvents(card, staticDevices, onReload);
}

function bindReservationEvents(card, staticDevices, onReload) {
    const tbody = card.querySelector('#res-tbody');

    const handleEditRes = (mac) => {
        const d = staticDevices.find(x => x.mac === mac);
        if (!d) return;
        const row = card.querySelector(`#res-row-${mac.replace(/:/g, '')}`);
        if (!row) return;

        row.className = 'inline-edit-row';
        row.innerHTML = `
            <td><input type="text" class="form-input" id="edit-res-name" value="${d.name}"></td>
            <td><code>${d.mac}</code></td>
            <td><input type="text" class="form-input" id="edit-res-ip" value="${d.staticIp}"></td>
            <td>
                <select class="form-select" id="edit-res-zone">
                    <option value="lan" ${d.zone === 'lan' ? 'selected' : ''}>LAN</option>
                    <option value="guest" ${d.zone === 'guest' ? 'selected' : ''}>GUEST</option>
                    <option value="iot" ${d.zone === 'iot' ? 'selected' : ''}>IOT</option>
                </select>
            </td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="btn-save-res">Save</button>
                    <button class="btn btn-secondary btn-sm" id="btn-cancel-res">Cancel</button>
                </div>
            </td>
        `;

        row.querySelector('#btn-save-res').onclick = () => {
            store.updateDevice(mac, {
                name: row.querySelector('#edit-res-name').value,
                staticIp: row.querySelector('#edit-res-ip').value,
                zone: row.querySelector('#edit-res-zone').value
            });
            onReload();
        };
        row.querySelector('#btn-cancel-res').onclick = () => onReload();
    };

    const insertAddResRow = (position = 'top') => {
        card.querySelector('#inline-add-res-row')?.remove();
        const tr = document.createElement('tr');
        tr.id = 'inline-add-res-row';
        tr.className = 'inline-edit-row';
        tr.innerHTML = `
            <td><input type="text" class="form-input" id="new-res-name" placeholder="Printer / NAS"></td>
            <td><input type="text" class="form-input" id="new-res-mac" placeholder="aa:bb:cc:dd:ee:ff"></td>
            <td><input type="text" class="form-input" id="new-res-ip" placeholder="192.168.1.50"></td>
            <td><select class="form-select" id="new-res-zone"><option value="lan">LAN</option><option value="iot">IOT</option><option value="guest">GUEST</option></select></td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" id="btn-save-new-res">Save</button>
                    <button class="btn btn-secondary btn-sm" id="btn-cancel-new-res">Cancel</button>
                </div>
            </td>
        `;

        if (position === 'top') tbody.insertBefore(tr, tbody.firstChild);
        else tbody.appendChild(tr);

        tr.querySelector('#btn-save-new-res').onclick = () => {
            const mac = tr.querySelector('#new-res-mac').value.trim();
            const ip = tr.querySelector('#new-res-ip').value.trim();
            if (!mac || !ip) return alert('MAC and IP are required');
            store.addDevice({
                mac,
                name: tr.querySelector('#new-res-name').value || 'Reserved Host',
                staticIp: ip,
                zone: tr.querySelector('#new-res-zone').value
            });
            onReload();
        };
        tr.querySelector('#btn-cancel-new-res').onclick = () => tr.remove();
    };

    card.querySelector('#top-add-res-btn')?.addEventListener('click', () => insertAddResRow('top'));
    card.querySelector('#bottom-add-res-btn')?.addEventListener('click', () => insertAddResRow('bottom'));

    card.querySelectorAll('.edit-res-btn').forEach(b => {
        b.onclick = () => handleEditRes(b.dataset.mac);
    });

    card.querySelectorAll('.del-res-btn').forEach(b => {
        b.onclick = () => {
            store.updateDevice(b.dataset.mac, { staticIp: '' });
            onReload();
        };
    });
}
