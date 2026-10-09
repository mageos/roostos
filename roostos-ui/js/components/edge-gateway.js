/**
 * EdgeGatewayComponent - Web Component for VPS Edge Gateway & Ingress Reverse Proxy
 * Manages CGNAT bypass, WireGuard tunnel link, and domain proxy routes.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const apiFetch = (url, options = {}) => {
    if (window.authService?.apiFetch) return window.authService.apiFetch(url, options);
    const token = localStorage.getItem("roostos_token");
    const headers = { ...options.headers };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, { ...options, headers });
};

const renderEdgeGatewayTemplate = (gateway, routes, rowsHtml) => html`
    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">VPS Edge Gateway (CGNAT Bypass)</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Public static IP entrypoint routing external traffic over an encrypted WireGuard tunnel.
                </p>
            </div>
            <button class="btn btn-primary btn-sm" id="open-link-modal-btn">
                ${gateway ? "Re-link Gateway" : "+ Connect Edge Gateway"}
            </button>
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
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">VPS Public IP</div>
                <div style="font-family: monospace; font-size: 14px; font-weight: 600;">${gateway?.public_ip || 'None'}</div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">Tunnel Link</div>
                <div style="font-family: monospace; font-size: 13px;">${gateway ? `${gateway.tunnel_ip_home} ➔ ${gateway.tunnel_ip_gateway}` : '10.42.0.0/24 (Inactive)'}</div>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Ingress Reverse Proxy Routes (${routes.length})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-route-btn">+ Add Route</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="routes-table">
                <thead>
                    <tr>
                        <th>Public Domain</th>
                        <th>Target LAN Destination</th>
                        <th>SSL / HTTPS</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="routes-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-route-btn">+ Add Route</button>
        </div>
    </div>
`;

const renderRouteRowTemplate = (r) => html`
    <tr id="route-row-${r.id}">
        <td><strong><code>${r.domain}</code></strong></td>
        <td><code>${r.target_ip}:${r.target_port}</code></td>
        <td><span class="badge ${r.ssl_enabled ? 'badge-success' : 'badge-secondary'}">${r.ssl_enabled ? 'TLS Enabled' : 'HTTP Only'}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-route-btn" data-id="${r.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-route-btn" data-id="${r.id}">Delete</button>
        </td>
    </tr>
`;

const renderInlineRouteRowTemplate = (r = {}) => html`
    <tr class="inline-add-row" ${r.id ? `id="edit-row-${r.id}"` : ''}>
        <td><input type="text" class="inline-input route-domain-input" placeholder="app.yourdomain.com" value="${r.domain || ''}"></td>
        <td>
            <div style="display: flex; gap: 6px;">
                <input type="text" class="inline-input route-ip-input" placeholder="192.168.1.50" value="${r.target_ip || ''}" style="flex: 2;">
                <input type="number" class="inline-input route-port-input" placeholder="8080" value="${r.target_port || ''}" style="flex: 1;">
            </div>
        </td>
        <td>
            <label style="font-size: 13px; display: flex; align-items: center; gap: 6px; cursor: pointer;">
                <input type="checkbox" class="route-ssl-input" ${r.ssl_enabled !== false ? 'checked' : ''}> Automated SSL
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-route-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-route-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class EdgeGatewayComponent extends HTMLElement {
    constructor() {
        super();
        this.gateway = null;
        this.routes = [];
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        try {
            const statusRes = await apiFetch("/api/edge/status");
            if (statusRes.ok) {
                const data = await statusRes.json();
                this.gateway = data.gateways?.[0] || null;
            }
            const routesRes = await apiFetch("/api/edge/routes");
            if (routesRes.ok) {
                this.routes = await routesRes.json();
            }
        } catch (e) {
            console.warn("Could not load edge gateway data:", e);
        }
        this.render();
    }

    render() {
        const rowsHtml = this.routes.length === 0
            ? html`<tr><td colspan="4" class="empty-state">No ingress routes configured. Click "+ Add Route" to expose an application.</td></tr>`
            : this.routes.map(r => renderRouteRowTemplate(r)).join("");

        this.innerHTML = renderEdgeGatewayTemplate(this.gateway, this.routes, rowsHtml);

        this.querySelector("#open-link-modal-btn")?.addEventListener("click", () => this.showLinkModal());
        this.querySelectorAll("#top-add-route-btn, #bottom-add-route-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });

        this.querySelectorAll(".edit-route-btn").forEach(btn => {
            btn.onclick = (e) => this.showInlineEditRow(e.target.dataset.id);
        });

        this.querySelectorAll(".delete-route-btn").forEach(btn => {
            btn.onclick = (e) => this.deleteRoute(e.target.dataset.id);
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#routes-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineRouteRowTemplate();
        const addTr = tempContainer.firstElementChild;
        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector(".save-route-btn").onclick = async () => {
            const domain = addTr.querySelector(".route-domain-input").value.trim();
            const target_ip = addTr.querySelector(".route-ip-input").value.trim();
            const target_port = parseInt(addTr.querySelector(".route-port-input").value, 10);
            const ssl_enabled = addTr.querySelector(".route-ssl-input").checked;

            if (!domain || !target_ip || isNaN(target_port)) {
                alert("Please fill in domain, target IP, and port.");
                return;
            }

            try {
                const res = await apiFetch("/api/edge/routes", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ domain, target_ip, target_port, ssl_enabled })
                });
                if (res.ok) {
                    await this.loadData();
                } else {
                    const err = await res.json();
                    alert(`Error creating route: ${err.detail || 'Unknown error'}`);
                }
            } catch (err) {
                alert(`Network error: ${err}`);
            }
        };

        addTr.querySelector(".cancel-route-btn").onclick = () => addTr.remove();
    }

    showInlineEditRow(routeId) {
        const row = this.querySelector(`#route-row-${routeId}`);
        const route = this.routes.find(r => r.id === routeId);
        if (!row || !route) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineRouteRowTemplate(route);
        const editTr = tempContainer.firstElementChild;
        row.replaceWith(editTr);

        editTr.querySelector(".save-route-btn").onclick = async () => {
            route.domain = editTr.querySelector(".route-domain-input").value.trim();
            route.target_ip = editTr.querySelector(".route-ip-input").value.trim();
            route.target_port = parseInt(editTr.querySelector(".route-port-input").value, 10);
            route.ssl_enabled = editTr.querySelector(".route-ssl-input").checked;
            await this.loadData();
        };

        editTr.querySelector(".cancel-route-btn").onclick = () => this.render();
    }

    async deleteRoute(routeId) {
        if (!confirm("Are you sure you want to delete this ingress route?")) return;
        try {
            await apiFetch(`/api/edge/routes/${routeId}`, { method: "DELETE" });
            await this.loadData();
        } catch (e) {
            alert(`Error deleting route: ${e}`);
        }
    }

    showLinkModal() {
        const modal = document.createElement("div");
        modal.id = "edge-link-modal";
        modal.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,15,30,0.85);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:10000;";

        modal.innerHTML = `
            <div class="card" style="width:90%;max-width:560px;background:#131b2e;border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:24px;color:#f1f5f9;font-family:'Outfit',sans-serif;">
                <h3 style="margin-top:0;margin-bottom:12px;">Connect VPS Edge Gateway</h3>
                <p style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:16px;">
                    Run <code>roostos edge token</code> on your Debian VPS, then paste the generated bootstrap token below:
                </p>
                <div class="form-group" style="margin-bottom:16px;">
                    <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Bootstrap Token:</label>
                    <input type="text" id="edge-token-input" class="input-field" placeholder="roost-edge://<vps-ip>:8000?token=..." style="width:100%;">
                </div>
                <div style="display:flex;justify-content:flex-end;gap:12px;">
                    <button class="btn btn-secondary" id="edge-modal-cancel">Cancel</button>
                    <button class="btn btn-primary" id="edge-modal-connect">Connect & Establish Tunnel</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelector("#edge-modal-cancel").onclick = () => modal.remove();
        modal.querySelector("#edge-modal-connect").onclick = async () => {
            const token = modal.querySelector("#edge-token-input").value.trim();
            if (!token) return alert("Please enter the bootstrap token.");
            const btn = modal.querySelector("#edge-modal-connect");
            btn.disabled = true;
            btn.textContent = "Connecting...";

            try {
                const res = await apiFetch("/api/edge/connect", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token })
                });
                if (res.ok) {
                    modal.remove();
                    alert("Edge Gateway paired successfully! WireGuard tunnel active.");
                    await this.loadData();
                } else {
                    const err = await res.json();
                    alert(`Connection failed: ${err.detail || "Unknown error"}`);
                    btn.disabled = false;
                    btn.textContent = "Connect & Establish Tunnel";
                }
            } catch (err) {
                alert(`Error connecting to Edge Gateway: ${err}`);
                btn.disabled = false;
                btn.textContent = "Connect & Establish Tunnel";
            }
        };
    }
}

if (!customElements.get("roost-edge-gateway")) {
    customElements.define("roost-edge-gateway", EdgeGatewayComponent);
}
