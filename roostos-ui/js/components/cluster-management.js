/**
 * ClusterManagementComponent - Web Component for Multi-Node Cluster Orchestration.
 */

import {
    renderClusterOverviewTemplate,
    renderClusterNodesTableTemplate,
    renderNodeRowTemplate,
    renderInlineNodeRowTemplate,
    renderFleetUpdatesTemplate
} from "./cluster-templates.js";

export class ClusterManagementComponent extends HTMLElement {
    constructor() {
        super();
        this.status = { role: "controller", registered_nodes_count: 1, nodes: [] };
        this.nodes = [];
        this.updatesSummary = null;
        this.tokenData = null;
        this.discovered = [];
        this.isLoading = false;
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        this.isLoading = true;
        try {
            const [status, nodes, updates] = await Promise.all([
                window.clusterService.fetchClusterStatus().catch(() => ({ role: "controller" })),
                window.clusterService.fetchNodes().catch(() => []),
                window.clusterService.fetchClusterUpdates().catch(() => null)
            ]);
            this.status = status;
            this.nodes = nodes || [];
            this.updatesSummary = updates;
        } catch (e) {
            console.error("Failed to load cluster data:", e);
        } finally {
            this.isLoading = false;
        }
        this.render();
    }

    async refresh() {
        return this.loadData();
    }

    mount(container) {
        if (!container) return;
        let pane = container.querySelector("#cluster-view");
        if (!pane) {
            pane = document.createElement("div");
            pane.id = "cluster-view";
            pane.className = "view-pane";
            pane.appendChild(this);
            container.appendChild(pane);
        } else if (!pane.contains(this)) {
            pane.appendChild(this);
        }
    }

    render() {
        const localNodeId = this.status.node_id || "node-01";
        const rowsHtml = this.nodes.length === 0
            ? '<tr><td colspan="7" class="empty-state">No cluster nodes enrolled. Click "+ Add Node" to register one.</td></tr>'
            : this.nodes.map(n => {
                const nodeUpdates = this.updatesSummary && this.updatesSummary.nodes
                    ? this.updatesSummary.nodes[n.id]
                    : null;
                return renderNodeRowTemplate(n, nodeUpdates, n.id === localNodeId);
            }).join("");

        const overviewHtml = renderClusterOverviewTemplate(this.status, this.tokenData, this.discovered);
        const nodesTableHtml = renderClusterNodesTableTemplate(this.nodes.length, rowsHtml);
        const fleetUpdatesHtml = renderFleetUpdatesTemplate(this.updatesSummary);

        this.innerHTML = `
            ${overviewHtml}
            ${nodesTableHtml}
            ${fleetUpdatesHtml}
        `;

        this.bindEvents();
    }

    bindEvents() {
        // Add Node buttons (Top & Bottom)
        const topBtn = this.querySelector("#top-add-node-btn");
        const bottomBtn = this.querySelector("#bottom-add-node-btn");
        if (topBtn) topBtn.onclick = () => this.showInlineAddRow("top");
        if (bottomBtn) bottomBtn.onclick = () => this.showInlineAddRow("bottom");

        // Cluster Actions
        const genTokenBtn = this.querySelector("#gen-token-btn");
        if (genTokenBtn) genTokenBtn.onclick = () => this.handleGenerateToken();

        const copyTokenBtn = this.querySelector("#copy-token-btn");
        if (copyTokenBtn) {
            copyTokenBtn.onclick = () => {
                const token = copyTokenBtn.getAttribute("data-token");
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(token);
                    copyTokenBtn.textContent = "Copied!";
                    setTimeout(() => { copyTokenBtn.textContent = "Copy Token"; }, 2000);
                }
            };
        }

        const dismissTokenBtn = this.querySelector("#dismiss-token-btn");
        if (dismissTokenBtn) dismissTokenBtn.onclick = () => {
            this.tokenData = null;
            this.render();
        };

        const discoverBtn = this.querySelector("#discover-controllers-btn");
        if (discoverBtn) discoverBtn.onclick = () => this.handleDiscoverControllers();

        // Node Row actions
        this.querySelectorAll(".edit-node-btn").forEach(btn => {
            btn.onclick = () => this.showInlineEditRow(btn.getAttribute("data-id"));
        });

        this.querySelectorAll(".promote-node-btn").forEach(btn => {
            btn.onclick = () => this.handlePromoteNode(btn.getAttribute("data-id"));
        });

        this.querySelectorAll(".delete-node-btn").forEach(btn => {
            btn.onclick = () => this.handleRemoveNode(btn.getAttribute("data-id"));
        });

        this.querySelectorAll(".update-node-btn").forEach(btn => {
            btn.onclick = () => this.handleTriggerUpdate(btn.getAttribute("data-id"));
        });
    }

    showInlineAddRow(position = "top") {
        const tbody = this.querySelector("#cluster-nodes-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row") || tbody.querySelector(".inline-edit-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineNodeRowTemplate(null);
        const addTr = tempContainer.firstElementChild;

        if (position === "bottom" && tbody.lastElementChild) {
            tbody.appendChild(addTr);
        } else {
            tbody.insertBefore(addTr, tbody.firstChild);
        }

        const saveBtn = addTr.querySelector("#save-node-row-btn");
        const cancelBtn = addTr.querySelector("#cancel-node-row-btn");

        saveBtn.onclick = async () => {
            const id = addTr.querySelector("#node-form-id").value.trim();
            const name = addTr.querySelector("#node-form-name").value.trim();
            const rolesStr = addTr.querySelector("#node-form-roles").value.trim();
            const management_ip = addTr.querySelector("#node-form-ip").value.trim() || null;

            if (!id || !name) {
                alert("Node ID and Name are required.");
                return;
            }

            const roles = rolesStr ? rolesStr.split(",").map(r => r.trim()).filter(Boolean) : ["compute"];
            const nodeData = { id, name, roles, management_ip, interfaces: [] };

            try {
                await window.clusterService.saveNode(nodeData);
                await this.loadData();
            } catch (err) {
                alert(err.message || "Failed to save node");
            }
        };

        cancelBtn.onclick = () => addTr.remove();
    }

    showInlineEditRow(nodeId) {
        const row = this.querySelector(`#node-row-${nodeId}`);
        const node = this.nodes.find(n => n.id === nodeId);
        if (!row || !node) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineNodeRowTemplate(node);
        const editTr = tempContainer.firstElementChild;

        row.replaceWith(editTr);

        const saveBtn = editTr.querySelector("#save-node-row-btn");
        const cancelBtn = editTr.querySelector("#cancel-node-row-btn");

        saveBtn.onclick = async () => {
            const name = editTr.querySelector("#node-form-name").value.trim();
            const rolesStr = editTr.querySelector("#node-form-roles").value.trim();
            const management_ip = editTr.querySelector("#node-form-ip").value.trim() || null;

            if (!name) {
                alert("Node Name is required.");
                return;
            }

            const roles = rolesStr ? rolesStr.split(",").map(r => r.trim()).filter(Boolean) : ["compute"];
            const updatedNode = { ...node, name, roles, management_ip };

            try {
                await window.clusterService.saveNode(updatedNode);
                await this.loadData();
            } catch (err) {
                alert(err.message || "Failed to save node");
            }
        };

        cancelBtn.onclick = () => this.render();
    }

    async handleGenerateToken() {
        try {
            const data = await window.clusterService.generateJoinToken();
            this.tokenData = data;
            this.render();
        } catch (err) {
            alert(err.message || "Failed to generate join token");
        }
    }

    async handleDiscoverControllers() {
        try {
            const discovered = await window.clusterService.discoverControllers();
            this.discovered = discovered;
            if (discovered.length === 0) {
                alert("No controllers discovered on the local network via mDNS.");
            }
            this.render();
        } catch (err) {
            alert(err.message || "Discovery failed");
        }
    }

    async handleRemoveNode(nodeId) {
        if (!confirm(`Are you sure you want to remove and decommission node '${nodeId}'?`)) return;
        try {
            await window.clusterService.removeNode(nodeId);
            await this.loadData();
        } catch (err) {
            alert(err.message || "Failed to remove node");
        }
    }

    async handleTriggerUpdate(nodeId) {
        try {
            await window.clusterService.triggerNodeUpdate(nodeId, false);
            alert(`Update command queued successfully for node '${nodeId}'.`);
            await this.loadData();
        } catch (err) {
            alert(err.message || "Failed to queue update");
        }
    }

    async handlePromoteNode(nodeId) {
        if (!confirm(`Are you sure you want to promote node '${nodeId}' to cluster master?`)) return;
        try {
            await window.clusterService.promoteNode(nodeId);
            alert(`Node '${nodeId}' promoted to cluster master!`);
            await this.loadData();
        } catch (err) {
            alert(err.message || "Failed to promote node");
        }
    }
}

if (!customElements.get("roost-cluster-management")) {
    customElements.define("roost-cluster-management", ClusterManagementComponent);
}

if (typeof window !== "undefined") {
    window.ClusterManagementComponent = ClusterManagementComponent;
    if (!window.clusterComponent) {
        window.clusterComponent = new ClusterManagementComponent();
    }
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { ClusterManagementComponent };
}
