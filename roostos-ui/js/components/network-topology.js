/**
 * NetworkTopologyComponent - Web Component for Network Topology and Inter-Network Links
 * Visualizes subnets, routing links, and firewall policies via interactive diagram and tables.
 */

import {
    html,
    renderTopologyTemplate,
    renderLinkRowTemplate,
    renderInlineLinkFormTemplate,
    renderNetRowTemplate,
    renderInlineNetFormTemplate,
} from "./network-topology-templates.js";

const apiFetch = (url, options = {}) => {
    if (window.authService?.apiFetch) return window.authService.apiFetch(url, options);
    const token = localStorage.getItem("roostos_token");
    const headers = { ...options.headers };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, { ...options, headers });
};

export class NetworkTopologyComponent extends HTMLElement {
    constructor() {
        super();
        this.networks = [];
        this.links = [];
        this.activeView = "diagram";
        this.selectedNodeId = null;
        this.selectedLinkId = null;
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        try {
            const res = await apiFetch("/api/network/topology");
            if (res.ok) {
                const data = await res.json();
                this.networks = Array.isArray(data.networks) ? data.networks : [];
                this.links = Array.isArray(data.links) ? data.links : [];
            }
        } catch (e) {
            console.warn("Could not load network topology data:", e);
        }
        this.render();
    }

    render() {
        const linkRowsHtml = this.links.length === 0
            ? html`<tr><td colspan="6" class="empty-state">No inter-network connections defined. Click "+ Add Connection" to connect subnets.</td></tr>`
            : this.links.map(l => renderLinkRowTemplate(l, this.networks)).join("");

        const netRowsHtml = this.networks.length === 0
            ? html`<tr><td colspan="6" class="empty-state">No managed subnets found. Click "+ Add Subnet" to register networks.</td></tr>`
            : this.networks.map(n => renderNetRowTemplate(n)).join("");

        this.innerHTML = renderTopologyTemplate(
            this.networks, this.links, netRowsHtml, linkRowsHtml,
            this.activeView, this.selectedNodeId, this.selectedLinkId
        );

        // View toggle buttons
        const diagBtn = this.querySelector("#toggle-view-diagram");
        const cardsBtn = this.querySelector("#toggle-view-cards");
        if (diagBtn) diagBtn.onclick = () => { this.activeView = "diagram"; this.render(); };
        if (cardsBtn) cardsBtn.onclick = () => { this.activeView = "cards"; this.render(); };

        // Diagram node click interaction
        this.querySelectorAll(".diagram-node").forEach(nodeEl => {
            nodeEl.onclick = () => {
                const id = nodeEl.dataset.nodeId;
                this.selectedNodeId = (this.selectedNodeId === id ? null : id);
                this.render();
                const tableRow = this.querySelector(`#net-row-${id}`);
                if (tableRow && typeof tableRow.scrollIntoView === "function") {
                    tableRow.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            };
        });

        // Diagram link badge click interaction
        this.querySelectorAll(".diagram-link-badge").forEach(badgeEl => {
            badgeEl.onclick = (e) => {
                e.stopPropagation();
                const linkId = badgeEl.dataset.linkId;
                this.selectedLinkId = linkId;
                this.showInlineEditLinkRow(linkId);
            };
        });

        // Connection table actions
        this.querySelectorAll("#top-add-link-btn").forEach(b => { b.onclick = () => this.showInlineAddLinkRow(false); });
        this.querySelectorAll("#bottom-add-link-btn").forEach(b => { b.onclick = () => this.showInlineAddLinkRow(true); });
        this.querySelectorAll(".edit-link-btn").forEach(b => { b.onclick = (e) => this.showInlineEditLinkRow(e.target.dataset.id); });
        this.querySelectorAll(".delete-link-btn").forEach(b => { b.onclick = (e) => this.deleteLink(e.target.dataset.id); });

        // Subnet table actions
        this.querySelectorAll("#top-add-net-btn").forEach(b => { b.onclick = () => this.showInlineAddNetRow(false); });
        this.querySelectorAll("#bottom-add-net-btn").forEach(b => { b.onclick = () => this.showInlineAddNetRow(true); });
        this.querySelectorAll(".edit-net-btn").forEach(b => { b.onclick = (e) => this.showInlineEditNetRow(e.target.dataset.id); });
        this.querySelectorAll(".delete-net-btn").forEach(b => { b.onclick = (e) => this.deleteNet(e.target.dataset.id); });
    }

    showInlineAddLinkRow(atBottom = false) {
        const tbody = this.querySelector("#links-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineLinkFormTemplate({}, this.networks);
        const addTr = temp.firstElementChild;
        if (atBottom) tbody.appendChild(addTr);
        else tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector(".save-link-btn").onclick = async () => {
            const src = addTr.querySelector(".link-src-select").value;
            const tgt = addTr.querySelector(".link-tgt-select").value;
            const connType = addTr.querySelector(".link-type-select").value;
            const routingMode = addTr.querySelector(".link-routing-select").value;
            const policy = addTr.querySelector(".link-policy-select").value;
            const portsRaw = addTr.querySelector(".link-ports-input").value.trim();
            const allowed_ports = portsRaw ? portsRaw.split(",").map(p => p.trim()).filter(Boolean) : [];
            const description = addTr.querySelector(".link-desc-input").value.trim();

            if (src === tgt) return alert("Source and target networks cannot be the same.");

            try {
                const res = await apiFetch("/api/network/topology/links", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        source_network_id: src, target_network_id: tgt,
                        connection_type: connType, routing_mode: routingMode,
                        firewall_policy: policy, allowed_ports, description,
                    })
                });
                if (res.ok) await this.loadData();
                else {
                    const err = await res.json();
                    alert(`Failed to save link: ${err.detail || "Error"}`);
                }
            } catch (err) {
                alert(`Network error: ${err}`);
            }
        };

        addTr.querySelector(".cancel-link-btn").onclick = () => addTr.remove();
    }

    showInlineEditLinkRow(linkId) {
        const row = this.querySelector(`#link-row-${linkId}`);
        const link = this.links.find(l => l.id === linkId);
        if (!row || !link) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineLinkFormTemplate(link, this.networks);
        const editTr = temp.firstElementChild;
        row.replaceWith(editTr);
        if (typeof editTr.scrollIntoView === "function") {
            editTr.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        editTr.querySelector(".save-link-btn").onclick = async () => {
            const src = editTr.querySelector(".link-src-select").value;
            const tgt = editTr.querySelector(".link-tgt-select").value;
            const connType = editTr.querySelector(".link-type-select").value;
            const routingMode = editTr.querySelector(".link-routing-select").value;
            const policy = editTr.querySelector(".link-policy-select").value;
            const portsRaw = editTr.querySelector(".link-ports-input").value.trim();
            const allowed_ports = portsRaw ? portsRaw.split(",").map(p => p.trim()).filter(Boolean) : [];
            const description = editTr.querySelector(".link-desc-input").value.trim();

            try {
                const res = await apiFetch("/api/network/topology/links", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: linkId, source_network_id: src, target_network_id: tgt,
                        connection_type: connType, routing_mode: routingMode,
                        firewall_policy: policy, allowed_ports, description,
                    })
                });
                if (res.ok) await this.loadData();
            } catch (err) {
                alert(`Error: ${err}`);
            }
        };

        editTr.querySelector(".cancel-link-btn").onclick = () => this.render();
    }

    async deleteLink(linkId) {
        if (!confirm("Are you sure you want to delete this inter-network link?")) return;
        try {
            const res = await apiFetch(`/api/network/topology/links/${linkId}`, { method: "DELETE" });
            if (res.ok) await this.loadData();
        } catch (e) {
            alert(`Failed to delete link: ${e}`);
        }
    }

    showInlineAddNetRow(atBottom = false) {
        const tbody = this.querySelector("#nets-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineNetFormTemplate({});
        const addTr = temp.firstElementChild;
        if (atBottom) tbody.appendChild(addTr);
        else tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector(".save-net-btn").onclick = async () => {
            const name = addTr.querySelector(".net-name-input").value.trim();
            const subnet = addTr.querySelector(".net-subnet-input").value.trim();
            const gw = addTr.querySelector(".net-gw-input").value.trim();
            const type = addTr.querySelector(".net-type-select").value;
            const iface = addTr.querySelector(".net-if-input").value.trim();

            if (!name || !subnet) return alert("Network name and subnet CIDR are required.");

            try {
                const res = await apiFetch("/api/network/topology/subnets", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name, subnet, gateway_ip: gw || null,
                        network_type: type, interface: iface || null,
                    })
                });
                if (res.ok) await this.loadData();
            } catch (err) {
                alert(`Error: ${err}`);
            }
        };

        addTr.querySelector(".cancel-net-btn").onclick = () => addTr.remove();
    }

    showInlineEditNetRow(netId) {
        const row = this.querySelector(`#net-row-${netId}`);
        const net = this.networks.find(n => n.id === netId);
        if (!row || !net) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineNetFormTemplate(net);
        const editTr = temp.firstElementChild;
        row.replaceWith(editTr);
        if (typeof editTr.scrollIntoView === "function") {
            editTr.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        editTr.querySelector(".save-net-btn").onclick = async () => {
            const name = editTr.querySelector(".net-name-input").value.trim();
            const subnet = editTr.querySelector(".net-subnet-input").value.trim();
            const gw = editTr.querySelector(".net-gw-input").value.trim();
            const type = editTr.querySelector(".net-type-select").value;
            const iface = editTr.querySelector(".net-if-input").value.trim();

            try {
                const res = await apiFetch("/api/network/topology/subnets", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: netId, name, subnet, gateway_ip: gw || null,
                        network_type: type, interface: iface || null,
                    })
                });
                if (res.ok) await this.loadData();
            } catch (err) {
                alert(`Error: ${err}`);
            }
        };

        editTr.querySelector(".cancel-net-btn").onclick = () => this.render();
    }

    async deleteNet(netId) {
        if (!confirm("Are you sure you want to remove this subnet from topology? Connected links will be severed.")) return;
        try {
            const res = await apiFetch(`/api/network/topology/subnets/${netId}`, { method: "DELETE" });
            if (res.ok) await this.loadData();
        } catch (e) {
            alert(`Failed to delete subnet: ${e}`);
        }
    }
}

if (!customElements.get("roost-network-topology")) {
    customElements.define("roost-network-topology", NetworkTopologyComponent);
}
