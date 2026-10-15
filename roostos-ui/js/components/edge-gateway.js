/**
 * EdgeGatewayComponent - Web Component for VPS Edge Gateway & WireGuard Hub
 * Manages CGNAT bypass, reverse proxy ingress routes, and mobile/site VPN peers.
 */

import {
    html,
    renderEdgeGatewayTemplate,
    renderRouteRowTemplate,
    renderInlineRouteRowTemplate,
    renderPeerRowTemplate,
    renderInlinePeerRowTemplate,
} from "./edge-gateway-templates.js";
import {
    showPeerQrModal,
    showEditEndpointModal,
    showLinkModal,
} from "./edge-gateway-modals.js";

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
        this.peers = [];
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        try {
            const [statusRes, routesRes, peersRes] = await Promise.all([
                apiFetch("/api/v1/edge/status"),
                apiFetch("/api/v1/edge/routes"),
                apiFetch("/api/v1/edge/peers"),
            ]);
            if (statusRes.ok) {
                const data = await statusRes.json();
                this.gateway = data.gateways?.[0] || null;
            }
            if (routesRes.ok) {
                const data = await routesRes.json();
                this.routes = Array.isArray(data) ? data : (data.routes || []);
            }
            if (peersRes.ok) {
                const data = await peersRes.json();
                this.peers = Array.isArray(data) ? data : (data.peers || []);
            }
        } catch (e) {
            console.warn("Could not load edge gateway data:", e);
        }
        this.render();
    }

    render() {
        const peerRowsHtml = this.peers.length === 0
            ? html`<tr><td colspan="6" class="empty-state">No peers connected. Click "+ Add Mobile / Site Peer" to enroll mobile devices or link remote sites.</td></tr>`
            : this.peers.map(p => renderPeerRowTemplate(p)).join("");

        const routeRowsHtml = this.routes.length === 0
            ? html`<tr><td colspan="4" class="empty-state">No ingress routes configured. Click "+ Add Route" to expose an application.</td></tr>`
            : this.routes.map(r => renderRouteRowTemplate(r)).join("");

        this.innerHTML = renderEdgeGatewayTemplate(this.gateway, this.routes, routeRowsHtml, this.peers, peerRowsHtml);

        this.querySelector("#open-link-modal-btn")?.addEventListener("click", () => showLinkModal(this, apiFetch));
        this.querySelector("#edit-endpoint-btn")?.addEventListener("click", () => showEditEndpointModal(this, apiFetch));

        this.querySelectorAll("#top-add-peer-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddPeerRow(false);
        });
        this.querySelectorAll("#bottom-add-peer-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddPeerRow(true);
        });
        this.querySelectorAll(".view-peer-qr-btn").forEach(btn => {
            btn.onclick = (e) => {
                const peer = this.peers.find(p => p.id === e.target.dataset.id);
                if (peer) showPeerQrModal(peer);
            };
        });
        this.querySelectorAll(".delete-peer-btn").forEach(btn => {
            btn.onclick = (e) => this.deletePeer(e.target.dataset.id);
        });

        this.querySelectorAll("#top-add-route-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRouteRow(false);
        });
        this.querySelectorAll("#bottom-add-route-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRouteRow(true);
        });
        this.querySelectorAll(".edit-route-btn").forEach(btn => {
            btn.onclick = (e) => this.showInlineEditRouteRow(e.target.dataset.id);
        });
        this.querySelectorAll(".delete-route-btn").forEach(btn => {
            btn.onclick = (e) => this.deleteRoute(e.target.dataset.id);
        });
    }

    showInlineAddPeerRow(atBottom = false) {
        const tbody = this.querySelector("#peers-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlinePeerRowTemplate();
        const addTr = tempContainer.firstElementChild;
        if (atBottom) {
            tbody.appendChild(addTr);
        } else {
            tbody.insertBefore(addTr, tbody.firstChild);
        }

        addTr.querySelector(".save-peer-btn").onclick = async () => {
            const name = addTr.querySelector(".peer-name-input").value.trim();
            const peer_type = addTr.querySelector(".peer-type-select").value;
            const subnetsRaw = addTr.querySelector(".peer-subnets-input").value.trim();
            const subnets = subnetsRaw ? subnetsRaw.split(",").map(s => s.trim()).filter(Boolean) : [];
            const route_internet = addTr.querySelector(".peer-internet-input").checked;

            if (!name) return alert("Please specify a peer name.");

            try {
                const res = await apiFetch("/api/v1/edge/peers", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, peer_type, subnets, route_internet })
                });
                if (res.ok) {
                    const newPeer = await res.json();
                    await this.loadData();
                    showPeerQrModal(newPeer);
                } else {
                    const err = await res.json();
                    alert(`Failed to add peer: ${err.detail || "Error"}`);
                }
            } catch (err) {
                alert(`Network error: ${err}`);
            }
        };

        addTr.querySelector(".cancel-peer-btn").onclick = () => addTr.remove();
    }

    async deletePeer(peerId) {
        if (!confirm("Revoke this WireGuard peer? They will lose VPN access immediately.")) return;
        try {
            const res = await apiFetch(`/api/v1/edge/peers/${peerId}`, { method: "DELETE" });
            if (res.ok) {
                await this.loadData();
            } else {
                const err = await res.json();
                alert(`Error revoking peer: ${err.detail || "Error"}`);
            }
        } catch (e) {
            alert(`Error revoking peer: ${e}`);
        }
    }

    showInlineAddRouteRow(atBottom = false) {
        const tbody = this.querySelector("#routes-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineRouteRowTemplate();
        const addTr = tempContainer.firstElementChild;
        if (atBottom) {
            tbody.appendChild(addTr);
        } else {
            tbody.insertBefore(addTr, tbody.firstChild);
        }

        addTr.querySelector(".save-route-btn").onclick = async () => {
            const domain = addTr.querySelector(".route-domain-input").value.trim();
            const target_ip = addTr.querySelector(".route-ip-input").value.trim();
            const target_port = parseInt(addTr.querySelector(".route-port-input").value, 10);
            const ssl_enabled = addTr.querySelector(".route-ssl-input").checked;

            if (!domain || !target_ip || isNaN(target_port)) {
                return alert("Please fill in domain, target IP, and port.");
            }

            try {
                const res = await apiFetch("/api/v1/edge/routes", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ domain, target_ip, target_port, ssl_enabled })
                });
                if (res.ok) {
                    await this.loadData();
                } else {
                    const err = await res.json();
                    alert(`Error creating route: ${err.detail || "Unknown error"}`);
                }
            } catch (err) {
                alert(`Network error: ${err}`);
            }
        };

        addTr.querySelector(".cancel-route-btn").onclick = () => addTr.remove();
    }

    showInlineEditRouteRow(routeId) {
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
            await apiFetch(`/api/v1/edge/routes/${routeId}`, { method: "DELETE" });
            await this.loadData();
        } catch (e) {
            alert(`Error deleting route: ${e}`);
        }
    }
}

if (!customElements.get("roost-edge-gateway")) {
    customElements.define("roost-edge-gateway", EdgeGatewayComponent);
}
