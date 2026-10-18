// Concept 1: SysAdmin Console - WireGuard VPN Server Nodes & Hostname Config (AGENTS.md compliant)
import { api } from '../api.js';

let editingServerId = null;
let cachedServers = [];

export function renderVpnServers(container, onUpdate) {
    const section = document.createElement('div');
    section.style.marginTop = '20px';
    section.style.paddingTop = '16px';
    section.style.borderTop = '1px solid var(--border-subtle)';

    section.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px; flex-wrap:wrap; gap:8px;">
            <div>
                <h4 style="font-size: 14px; font-weight: 700; margin: 0;">🛡️ Multi-Node WireGuard VPN Servers</h4>
                <p style="font-size: 12px; color: var(--text-muted); margin: 2px 0 0 0;">Designate cluster nodes as VPN servers and specify the public hostname/port mobile clients connect to.</p>
            </div>
            <button class="btn btn-secondary btn-sm" id="btn-refresh-vpn-servers">🔄 Refresh Servers</button>
        </div>

        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Node Name & Role</th>
                        <th>VPN Server Status</th>
                        <th>Mobile Client Endpoint (Hostname : Port)</th>
                        <th>Assigned Peers</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="vpn-servers-tbody">
                    <tr><td colspan="5" style="text-align:center; padding: 14px; color: var(--text-muted);">Loading VPN servers...</td></tr>
                </tbody>
            </table>
        </div>
    `;

    container.appendChild(section);

    async function loadAndRender() {
        try {
            cachedServers = await api.getVpnServers();
            renderRows();
        } catch (err) {
            const tbody = section.querySelector('#vpn-servers-tbody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="color:var(--accent-amber); padding:10px;">Failed to load VPN servers: ${err.message || err}</td></tr>`;
        }
    }

    function renderRows() {
        const tbody = section.querySelector('#vpn-servers-tbody');
        if (!tbody) return;

        if (cachedServers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 16px; color: var(--text-muted);">No cluster nodes available.</td></tr>';
            return;
        }

        tbody.innerHTML = cachedServers.map(s => {
            if (editingServerId === s.server_id) {
                return `
                    <tr class="inline-edit-row" style="background: var(--bg-subtle);">
                        <td>
                            <strong>${s.name}</strong>
                            <div style="font-size:10px; color:var(--text-muted);">${s.role}</div>
                        </td>
                        <td>
                            <label style="font-size:12px; display:flex; align-items:center; gap:6px; cursor:pointer;">
                                <input type="checkbox" id="edit-server-active" ${s.is_active ? 'checked' : ''}>
                                <strong>Active Server</strong>
                            </label>
                        </td>
                        <td>
                            <div style="display:flex; gap:6px; align-items:center;">
                                <input type="text" class="form-input" id="edit-server-hostname" value="${s.hostname || ''}" placeholder="vpn.example.com" style="padding:4px 8px; font-size:12px; flex:1;">
                                <span>:</span>
                                <input type="number" class="form-input" id="edit-server-port" value="${s.port || 51820}" style="padding:4px 8px; font-size:12px; width:75px;">
                            </div>
                        </td>
                        <td><code>${s.peer_count} peers</code></td>
                        <td>
                            <div style="display:flex; gap:6px;">
                                <button class="btn btn-primary btn-sm btn-save-server" data-id="${s.server_id}">Save</button>
                                <button class="btn btn-secondary btn-sm btn-cancel-server">Cancel</button>
                            </div>
                        </td>
                    </tr>
                `;
            }
            return `
                <tr>
                    <td>
                        <strong>${s.role === 'edge_gateway' ? '☁️' : '🛡️'} ${s.name}</strong>
                        <div style="font-size:10px; color:var(--text-muted);">${s.role}</div>
                    </td>
                    <td>
                        <span class="badge ${s.is_active ? 'badge-success' : 'badge-neutral'}">
                            ${s.is_active ? '● Active VPN Server' : '○ Disabled'}
                        </span>
                    </td>
                    <td>
                        ${s.hostname ? `<code>${s.hostname}:${s.port}</code>` : '<span style="color:var(--text-muted); font-size:12px;">Not configured (Click Edit)</span>'}
                    </td>
                    <td><span class="badge badge-neutral">${s.peer_count} connected</span></td>
                    <td>
                        <button class="btn btn-secondary btn-sm btn-edit-server" data-id="${s.server_id}">Edit</button>
                    </td>
                </tr>
            `;
        }).join('');

        tbody.querySelectorAll('.btn-edit-server').forEach(btn => {
            btn.onclick = () => {
                editingServerId = btn.dataset.id;
                renderRows();
            };
        });

        tbody.querySelectorAll('.btn-cancel-server').forEach(btn => {
            btn.onclick = () => {
                editingServerId = null;
                renderRows();
            };
        });

        tbody.querySelectorAll('.btn-save-server').forEach(btn => {
            btn.onclick = async () => {
                const serverId = btn.dataset.id;
                const isActive = section.querySelector('#edit-server-active')?.checked ?? true;
                const hostname = section.querySelector('#edit-server-hostname')?.value.trim() || null;
                const port = parseInt(section.querySelector('#edit-server-port')?.value || '51820', 10);
                try {
                    await api.updateVpnServer(serverId, { is_vpn_server: isActive, vpn_hostname: hostname, vpn_port: port });
                    editingServerId = null;
                    await loadAndRender();
                    onUpdate();
                } catch (err) {
                    alert(`Failed to update VPN server: ${err.message || err}`);
                }
            };
        });
    }

    section.querySelector('#btn-refresh-vpn-servers')?.addEventListener('click', loadAndRender);
    loadAndRender();
}
