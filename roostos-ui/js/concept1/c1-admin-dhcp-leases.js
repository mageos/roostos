// Concept 1: SysAdmin Console - Active Dynamic DHCP Leases Component
import { store } from '../state.js';

let activeLeaseFilter = 'all';

export function renderDhcpLeases(container, onReload) {
    const admin = store.data.admin;
    const leases = admin.activeLeases.filter(l => activeLeaseFilter === 'all' || l.network === activeLeaseFilter);

    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
        <div class="card-header table-action-bar">
            <div>
                <h3 class="card-title">📋 Active Dynamic Leases (${leases.length})</h3>
                <p class="card-subtitle">Real-time IP allocations; click 'Convert to Static' to lock device IP permanently</p>
            </div>
            <div class="c1-nav-tabs">
                <button class="c1-nav-link lease-flt-btn ${activeLeaseFilter === 'all' ? 'active' : ''}" data-lfilter="all">All Networks</button>
                <button class="c1-nav-link lease-flt-btn ${activeLeaseFilter === 'br-lan' ? 'active' : ''}" data-lfilter="br-lan">Household LAN</button>
                <button class="c1-nav-link lease-flt-btn ${activeLeaseFilter === 'vlan-guest' ? 'active' : ''}" data-lfilter="vlan-guest">Guest</button>
                <button class="c1-nav-link lease-flt-btn ${activeLeaseFilter === 'vlan-iot' ? 'active' : ''}" data-lfilter="vlan-iot">IoT</button>
            </div>
        </div>

        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr><th>Hostname</th><th>Assigned IP</th><th>MAC Address</th><th>Interface</th><th>Time Remaining</th><th>Vendor</th><th>Action</th></tr>
                </thead>
                <tbody>
                    ${leases.length === 0 ? `
                        <tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">No active dynamic DHCP leases on selected network.</td></tr>
                    ` : leases.map(l => `
                        <tr>
                            <td><strong>${l.hostname}</strong></td>
                            <td><code>${l.ip}</code></td>
                            <td><code>${l.mac}</code></td>
                            <td><span class="badge badge-info">${l.network}</span></td>
                            <td>${l.expires}</td>
                            <td>${l.vendor}</td>
                            <td><button class="btn btn-secondary btn-sm reserve-lease-btn" data-mac="${l.mac}">📌 Convert to Static</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;

    container.appendChild(card);

    card.querySelectorAll('.lease-flt-btn').forEach(b => {
        b.onclick = () => {
            activeLeaseFilter = b.dataset.lfilter;
            onReload();
        };
    });

    card.querySelectorAll('.reserve-lease-btn').forEach(b => {
        b.onclick = () => {
            const lease = store.data.admin.activeLeases.find(l => l.mac === b.dataset.mac);
            if (lease) {
                store.reserveDynamicLease(lease);
                alert(`Static reservation created for ${lease.hostname} (${lease.ip})`);
                onReload();
            }
        };
    });
}
