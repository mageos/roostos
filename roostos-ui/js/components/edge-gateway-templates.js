/**
 * HTML Templates for Edge Gateway Web Component
 */

export const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export const createModal = (id, contentHtml) => {
    let existing = document.getElementById(id);
    if (existing) existing.remove();
    const modal = document.createElement("div");
    modal.id = id;
    modal.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,15,30,0.85);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:10000;";
    modal.innerHTML = `<div class="card" style="width:90%;max-width:540px;background:#131b2e;border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:24px;color:#f1f5f9;font-family:'Outfit',sans-serif;">${contentHtml}</div>`;
    document.body.appendChild(modal);
    return modal;
};

export const renderEdgeGatewayTemplate = (gateway, routes, routeRowsHtml, peers = [], peerRowsHtml = "") => html`
    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">VPS Edge Gateway (CGNAT Bypass & VPN Hub)</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">Public entrypoint routing external traffic over an encrypted WireGuard tunnel.</p>
            </div>
            <button class="btn btn-primary btn-sm" id="open-link-modal-btn">${gateway ? "Re-link Gateway" : "+ Connect Edge Gateway"}</button>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 16px;">
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">Status</div>
                <div style="font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <span style="width: 10px; height: 10px; border-radius: 50%; background: ${gateway && gateway.status === 'connected' ? '#10b981' : '#f59e0b'};"></span>
                    ${gateway ? (gateway.status === 'connected' ? 'Connected & Active' : 'Connecting...') : 'Unlinked'}
                </div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
                    <span>Endpoint (Domain / IP)</span>
                    ${gateway ? `<button class="btn btn-secondary btn-sm" id="edit-endpoint-btn" style="padding: 2px 6px; font-size: 11px;">Edit</button>` : ''}
                </div>
                <div style="font-family: monospace; font-size: 14px; font-weight: 600;">${gateway?.domain || gateway?.public_ip || 'None'}</div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">Tunnel Hub Subnet</div>
                <div style="font-family: monospace; font-size: 13px;">${gateway ? `${gateway.tunnel_ip_gateway}` : '10.42.0.0/24 (Inactive)'}</div>
            </div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Connected WireGuard Peers & Mobile Devices (${peers.length})</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Connect phones, laptops, and multiple home sites (e.g. Vacation House) with inter-LAN mesh routing.
                </p>
            </div>
            <button class="btn btn-primary btn-sm" id="top-add-peer-btn">+ Add Mobile / Site Peer</button>
        </div>
        <div class="table-responsive">
            <table class="data-table" id="peers-table">
                <thead>
                    <tr>
                        <th>Peer / Device</th>
                        <th>Type</th>
                        <th>VPN IP</th>
                        <th>Inter-LAN Subnets</th>
                        <th>Internet Exit</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="peers-tbody">${peerRowsHtml}</tbody>
            </table>
        </div>
        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-peer-btn">+ Add Mobile / Site Peer</button>
        </div>
    </div>

    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Ingress Reverse Proxy Routes (${routes.length})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-route-btn">+ Add Route</button>
        </div>
        <div class="table-responsive">
            <table class="data-table" id="routes-table">
                <thead><tr><th>Public Domain</th><th>Target LAN Destination</th><th>SSL / HTTPS</th><th>Actions</th></tr></thead>
                <tbody id="routes-tbody">${routeRowsHtml}</tbody>
            </table>
        </div>
        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-route-btn">+ Add Route</button>
        </div>
    </div>
`;

export const renderPeerRowTemplate = (p) => {
    const typeIcon = p.peer_type === "mobile" ? "📱 Mobile" : (p.peer_type === "site" ? "🏠 Site Router" : "💻 Client");
    return html`
    <tr id="peer-row-${p.id}">
        <td><strong>${p.name}</strong></td>
        <td><span class="badge badge-outline">${typeIcon}</span></td>
        <td><code>${p.assigned_ip}</code></td>
        <td>${p.subnets && p.subnets.length > 0 ? p.subnets.map(s => `<code>${s}</code>`).join(", ") : '<span style="color:var(--text-secondary);">None</span>'}</td>
        <td><span class="badge ${p.route_internet ? 'badge-success' : 'badge-secondary'}">${p.route_internet ? 'Full Tunnel' : 'Split Tunnel'}</span></td>
        <td>
            <button class="btn btn-primary btn-sm view-peer-qr-btn" data-id="${p.id}">QR / Config</button>
            <button class="btn btn-danger btn-sm delete-peer-btn" data-id="${p.id}">Revoke</button>
        </td>
    </tr>
    `;
};

export const renderInlinePeerRowTemplate = (p = {}) => html`
    <tr class="inline-add-row" ${p.id ? `id="edit-peer-row-${p.id}"` : ''}>
        <td><input type="text" class="inline-input peer-name-input" placeholder="Matt's iPhone / Vacation House" value="${p.name || ''}"></td>
        <td>
            <select class="inline-input peer-type-select">
                <option value="mobile" ${p.peer_type === 'mobile' ? 'selected' : ''}>📱 Mobile Device</option>
                <option value="site" ${p.peer_type === 'site' ? 'selected' : ''}>🏠 Site Router (Inter-LAN)</option>
                <option value="client" ${p.peer_type === 'client' ? 'selected' : ''}>💻 Desktop / Client</option>
            </select>
        </td>
        <td><span style="font-size: 12px; color: var(--text-secondary);">Auto (10.42.0.x)</span></td>
        <td>
            <input type="text" class="inline-input peer-subnets-input" placeholder="e.g. 192.168.2.0/24 (Site-to-Site)" value="${p.subnets ? p.subnets.join(', ') : ''}">
        </td>
        <td>
            <label style="font-size: 12px; display: flex; align-items: center; gap: 4px; cursor: pointer;">
                <input type="checkbox" class="peer-internet-input" ${p.route_internet ? 'checked' : ''}> Route Internet
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-peer-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-peer-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export const renderRouteRowTemplate = (r) => html`
    <tr id="route-row-${r.id}">
        <td><strong><code>${r.domain}</code></strong></td>
        <td><code>${r.target_ip}:${r.target_port}</code></td>
        <td><span class="badge ${r.ssl_enabled ? (r.ssl_status === 'pending' ? 'badge-warning' : (r.ssl_status === 'error' ? 'badge-danger' : 'badge-success')) : 'badge-secondary'}">${r.ssl_enabled ? (r.ssl_status === 'valid' ? '🔒 SSL Active' : (r.ssl_status === 'pending' ? '⏳ SSL Pending' : '🔒 TLS Enabled')) : '🔓 HTTP Only'}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-route-btn" data-id="${r.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-route-btn" data-id="${r.id}">Delete</button>
        </td>
    </tr>
`;

export const renderInlineRouteRowTemplate = (r = {}) => html`
    <tr class="inline-add-row" ${r.id ? `id="edit-row-${r.id}"` : ''}>
        <td><input type="text" class="inline-input route-domain-input" placeholder="app.yourdomain.com" value="${r.domain || ''}"></td>
        <td><div style="display: flex; gap: 6px;">
            <input type="text" class="inline-input route-ip-input" placeholder="192.168.1.50" value="${r.target_ip || ''}" style="flex: 2;">
            <input type="number" class="inline-input route-port-input" placeholder="8080" value="${r.target_port || ''}" style="flex: 1;">
        </div></td>
        <td><label style="font-size: 13px; display: flex; align-items: center; gap: 6px; cursor: pointer;">
            <input type="checkbox" class="route-ssl-input" ${r.ssl_enabled !== false ? 'checked' : ''}> Automated SSL
        </label></td>
        <td><div class="inline-form-controls">
            <button class="btn btn-success btn-sm save-route-btn">Save</button>
            <button class="btn btn-secondary btn-sm cancel-route-btn">Cancel</button>
        </div></td>
    </tr>
`;

export const renderPeerQrModalContent = (peer) => html`
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Connect "${peer.name}" via WireGuard</h3>
        <button class="btn btn-secondary btn-sm close-modal-btn">✕</button>
    </div>
    <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
        Scan this QR code with the WireGuard app on your mobile device (iOS / Android) or download the configuration file.
    </p>
    <div style="background: white; padding: 16px; border-radius: 12px; display: flex; justify-content: center; align-items: center; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
        <div style="width: 240px; height: 240px; display: flex; align-items: center; justify-content: center;">
            ${peer.qr_svg ? peer.qr_svg : `<img src="/api/edge/peers/${peer.id}/qr" alt="WireGuard QR Code" style="width: 240px; height: 240px; display: block;">`}
        </div>
    </div>
    <div style="display: flex; gap: 10px; justify-content: flex-end;">
        <a href="/api/edge/peers/${peer.id}/config" download="${peer.name}.conf" class="btn btn-primary btn-sm">⬇ Download .conf</a>
        <button class="btn btn-secondary btn-sm close-modal-btn">Done</button>
    </div>
`;
