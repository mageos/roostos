/**
 * EdgeGatewayComponent - Web Component for VPS Edge Gateway & Ingress Reverse Proxy
 * Manages CGNAT bypass, WireGuard tunnel link, and domain proxy routes.
 */

import {
    html,
    createModal,
    renderEdgeGatewayTemplate,
    renderRouteRowTemplate,
    renderInlineRouteRowTemplate,
} from "./edge-gateway-templates.js";

const apiFetch = (url, options = {}) => {
    if (window.authService?.apiFetch) return window.authService.apiFetch(url, options);
    const token = localStorage.getItem("roostos_token");
    const headers = { ...options.headers };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, { ...options, headers });
};

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
        this.querySelector("#edit-endpoint-btn")?.addEventListener("click", () => this.showEditEndpointModal());
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

    showEditEndpointModal() {
        const currentHost = this.gateway?.domain || this.gateway?.public_ip || "";
        const currentPort = this.gateway?.listen_port || 51820;
        const modal = createModal("edge-endpoint-modal", `
            <h3 style="margin-top:0;margin-bottom:12px;">Update Edge Endpoint</h3>
            <p style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:16px;">
                Specify a domain name (e.g. <code>vps.example.com</code>) or IP address for WireGuard endpoint resolution.
            </p>
            <div class="form-group" style="margin-bottom:12px;">
                <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Domain Name or IP:</label>
                <input type="text" id="endpoint-host-input" class="input-field" placeholder="vps.example.com" value="${currentHost}" style="width:100%;">
            </div>
            <div class="form-group" style="margin-bottom:16px;">
                <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Port:</label>
                <input type="number" id="endpoint-port-input" class="input-field" value="${currentPort}" style="width:100%;">
            </div>
            <div style="display:flex;justify-content:flex-end;gap:12px;">
                <button class="btn btn-secondary" id="endpoint-modal-cancel">Cancel</button>
                <button class="btn btn-primary" id="endpoint-modal-save">Update Endpoint</button>
            </div>
        `);

        modal.querySelector("#endpoint-modal-cancel").onclick = () => modal.remove();
        modal.querySelector("#endpoint-modal-save").onclick = async () => {
            const host = modal.querySelector("#endpoint-host-input").value.trim();
            const port = parseInt(modal.querySelector("#endpoint-port-input").value, 10) || 51820;
            if (!host) return alert("Please specify a domain name or IP.");
            const isIp = /^(\d{1,3}\.){3}\d{1,3}$/.test(host);
            try {
                const res = await apiFetch("/api/edge/endpoint", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ domain: isIp ? null : host, ip: isIp ? host : null, port })
                });
                if (res.ok) {
                    modal.remove();
                    await this.loadData();
                } else {
                    const err = await res.json();
                    alert(`Update failed: ${err.detail || "Error"}`);
                }
            } catch (err) {
                alert(`Network error: ${err}`);
            }
        };
    }

    showLinkModal() {
        const modal = createModal("edge-link-modal", `
            <h3 style="margin-top:0;margin-bottom:12px;">Connect VPS Edge Gateway</h3>
            <p style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:16px;">
                Run <code>roostos edge token</code> on your Debian VPS, then paste the WireGuard invite token or upload the bundle file:
            </p>
            <div class="form-group" style="margin-bottom:12px;">
                <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Invitation Token:</label>
                <input type="text" id="edge-token-input" class="input-field" placeholder="roost-edge-wg://... or roost-edge://..." style="width:100%;">
            </div>
            <div class="form-group" style="margin-bottom:16px;">
                <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Or Upload Invitation File (.json):</label>
                <input type="file" id="edge-bundle-file" accept=".json" style="font-size:12px;color:#94a3b8;width:100%;">
            </div>
            <div style="display:flex;justify-content:flex-end;gap:12px;">
                <button class="btn btn-secondary" id="edge-modal-cancel">Cancel</button>
                <button class="btn btn-primary" id="edge-modal-connect">Connect & Establish Tunnel</button>
            </div>
        `);

        modal.querySelector("#edge-bundle-file").onchange = (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                try {
                    const parsed = JSON.parse(evt.target.result);
                    if (parsed.client_private_key && parsed.endpoint) {
                        modal.querySelector("#edge-token-input").value = `roost-edge-wg://${btoa(evt.target.result)}`;
                    } else if (parsed.token) {
                        modal.querySelector("#edge-token-input").value = parsed.token;
                    }
                } catch (err) {
                    alert("Could not read file: " + err);
                }
            };
            reader.readAsText(file);
        };

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
