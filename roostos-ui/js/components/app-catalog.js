/**
 * AppCatalogComponent - Web Component for RoostOS Application Catalog & Local Deployments
 */

import {
    renderCatalogTemplate,
    renderAppsGridTemplate,
    renderSourcesTemplate,
    renderSourceRowTemplate,
    renderInlineSourceRowTemplate,
    renderImagesTemplate,
    renderSourceDeployTemplate,
    renderInstallModalTemplate
} from "./app-catalog-templates.js";

export class AppCatalogComponent extends HTMLElement {
    constructor() {
        super();
        this.activeTab = "apps";
        this.selectedCategory = "all";
        this.apps = [];
        this.sources = [];
        this.images = [];
        this.inspectedManifest = null;
        this.buildStatusMsg = "";
        this.sourceUrl = "";
        this.sourceRef = "main";
        this.categories = ["all", "automation", "media", "privacy", "tools", "networking"];
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        try {
            const [sourcesData, appsData] = await Promise.all([
                window.catalogService.fetchSources().catch(() => ({ sources: [] })),
                window.catalogService.fetchApps().catch(() => ({ apps: [] }))
            ]);
            this.sources = sourcesData.sources || [];
            this.apps = appsData.apps || [];
            if (this.activeTab === "images") {
                const imgData = await window.catalogService.fetchImages().catch(() => ({ images: [] }));
                this.images = imgData.images || [];
            }
        } catch (e) {
            console.warn("Failed to load catalog data:", e);
        }
        this.render();
    }

    render() {
        const counts = { apps: this.apps.length, sources: this.sources.length, images: this.images.length };
        let bodyHtml = "";

        if (this.activeTab === "apps") {
            const filtered = this.selectedCategory === "all"
                ? this.apps
                : this.apps.filter(a => a.category.toLowerCase() === this.selectedCategory.toLowerCase());
            bodyHtml = renderAppsGridTemplate(filtered, this.selectedCategory, this.categories);
        } else if (this.activeTab === "source") {
            bodyHtml = renderSourceDeployTemplate(this.inspectedManifest, this.buildStatusMsg, this.sourceUrl, this.sourceRef);
        } else if (this.activeTab === "sources") {
            const rowsHtml = this.sources.length === 0
                ? `<tr><td colspan="6" class="empty-state">No catalog sources configured. Click "+ Add Repository" to add one.</td></tr>`
                : this.sources.map(s => renderSourceRowTemplate(s)).join("");
            bodyHtml = renderSourcesTemplate(this.sources, rowsHtml);
        } else if (this.activeTab === "images") {
            bodyHtml = renderImagesTemplate(this.images);
        }

        this.innerHTML = renderCatalogTemplate(this.activeTab, counts, bodyHtml);
        this.bindEvents();
    }

    bindEvents() {
        this.querySelectorAll(".tab-btn").forEach(btn => {
            btn.onclick = async () => {
                this.activeTab = btn.dataset.tab;
                if (this.activeTab === "images") {
                    const imgData = await window.catalogService.fetchImages().catch(() => ({ images: [] }));
                    this.images = imgData.images || [];
                }
                this.render();
            };
        });

        this.querySelectorAll(".category-filter-btn").forEach(btn => {
            btn.onclick = () => { this.selectedCategory = btn.dataset.category; this.render(); };
        });

        this.querySelector("#refresh-catalogs-btn")?.addEventListener("click", () => this.refreshCatalogs());
        this.querySelector("#refresh-sources-btn")?.addEventListener("click", () => this.refreshCatalogs());
        this.querySelector("#refresh-images-btn")?.addEventListener("click", async () => {
            const imgData = await window.catalogService.fetchImages().catch(() => ({ images: [] }));
            this.images = imgData.images || [];
            this.render();
        });

        this.querySelectorAll("#top-add-source-btn, #bottom-add-source-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddSource();
        });
        this.querySelectorAll(".edit-source-btn").forEach(btn => {
            btn.onclick = (e) => this.showInlineEditSource(e.target.dataset.id);
        });
        this.querySelectorAll(".delete-source-btn").forEach(btn => {
            btn.onclick = (e) => this.deleteSource(e.target.dataset.id);
        });
        this.querySelectorAll(".install-app-btn").forEach(btn => {
            btn.onclick = (e) => this.showInstallModal(e.target.dataset.id);
        });
        this.querySelectorAll(".check-update-btn").forEach(btn => {
            btn.onclick = (e) => this.handleCheckUpdate(e.target.dataset.id);
        });

        this.querySelector("#upload-image-btn")?.addEventListener("click", () => this.uploadDockerImage());
        this.querySelector("#inspect-manifest-btn")?.addEventListener("click", () => this.handleInspectManifest());
        this.querySelector("#deploy-source-btn")?.addEventListener("click", () => this.handleDeploySource());
    }

    async handleInspectManifest() {
        this.sourceUrl = this.querySelector("#source-input")?.value.trim() || "";
        this.sourceRef = this.querySelector("#source-ref-input")?.value.trim() || "main";
        if (!this.sourceUrl) return alert("Please enter a Git repo URL or local path.");
        this.buildStatusMsg = "Inspecting repository manifest...";
        this.render();
        try {
            this.inspectedManifest = await window.catalogService.inspectManifest(this.sourceUrl, this.sourceRef);
            this.buildStatusMsg = "Package manifest loaded successfully.";
        } catch (e) {
            this.buildStatusMsg = `Error: ${e.message}`;
        }
        this.render();
    }

    async handleDeploySource() {
        if (!this.inspectedManifest) return;
        const consented = this.querySelector("#source-consent-check")?.checked;
        if (!consented) return alert("Please confirm consent to build and add to catalog.");
        const networkRequired = this.inspectedManifest.build?.sandbox?.network_required;
        const networkApproved = this.querySelector("#approve-network-check")?.checked;
        if (networkRequired && !networkApproved) {
            return alert("Please review and approve the requested network access endpoints to build this application.");
        }
        const source = this.sourceUrl || this.querySelector("#source-input")?.value.trim();
        const ref = this.sourceRef || this.querySelector("#source-ref-input")?.value.trim() || "main";
        this.buildStatusMsg = `Building container for ${this.inspectedManifest.name}...`;
        this.render();
        try {
            await window.catalogService.importAppFromSource({
                source_url_or_path: source,
                git_ref: ref,
                approve_network: Boolean(networkApproved),
                approved_endpoints: this.inspectedManifest.build?.sandbox?.allowed_endpoints || [],
            });
            alert(`Successfully imported ${this.inspectedManifest.name} into Local Catalog! You can now install it from the Applications tab.`);
            await this.loadData();
            this.activeTab = "apps";
            this.render();
        } catch (e) {
            this.buildStatusMsg = `Import failed: ${e.message}`;
            this.render();
        }
    }

    async handleCheckUpdate(appId) {
        try {
            const res = await window.catalogService.checkAppUpdate(appId);
            if (res.update_available) {
                if (confirm(`Update available for ${appId} (${res.current_commit} ➔ ${res.latest_commit}). Rebuild and update now?`)) {
                    await window.catalogService.updateImportedApp(appId);
                    alert(`Application ${appId} updated successfully!`);
                    await this.loadData();
                }
            } else {
                alert(`Application ${appId} is already up to date (${res.current_commit || 'latest'}).`);
            }
        } catch (e) {
            alert(`Update check failed: ${e.message}`);
        }
    }

    showInlineAddSource() {
        const tbody = this.querySelector("#sources-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;
        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineSourceRowTemplate();
        const tr = temp.firstElementChild;
        tbody.insertBefore(tr, tbody.firstChild);

        tr.querySelector(".save-source-btn").onclick = async () => {
            const id = tr.querySelector(".src-id-input").value.trim();
            const name = tr.querySelector(".src-name-input").value.trim();
            const url = tr.querySelector(".src-url-input").value.trim();
            const signing_key = tr.querySelector(".src-key-input").value.trim() || null;
            const enabled = tr.querySelector(".src-enabled-input").checked;
            if (!id || !name || !url) return alert("Identifier, Name, and URL are required.");
            try {
                await window.catalogService.saveSource({ id, name, url, signing_key, enabled });
                await this.loadData();
            } catch (err) { alert(err.message); }
        };
        tr.querySelector(".cancel-source-btn").onclick = () => tr.remove();
    }

    showInlineEditSource(sourceId) {
        const row = this.querySelector(`#source-row-${sourceId}`);
        const source = this.sources.find(s => s.id === sourceId);
        if (!row || !source) return;
        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineSourceRowTemplate(source);
        const tr = temp.firstElementChild;
        row.replaceWith(tr);

        tr.querySelector(".save-source-btn").onclick = async () => {
            const name = tr.querySelector(".src-name-input").value.trim();
            const url = tr.querySelector(".src-url-input").value.trim();
            const signing_key = tr.querySelector(".src-key-input").value.trim() || null;
            const enabled = tr.querySelector(".src-enabled-input").checked;
            if (!name || !url) return alert("Name and URL are required.");
            try {
                await window.catalogService.saveSource({ id: source.id, name, url, signing_key, enabled });
                await this.loadData();
            } catch (err) { alert(err.message); }
        };
        tr.querySelector(".cancel-source-btn").onclick = () => this.render();
    }

    async deleteSource(sourceId) {
        if (!confirm(`Are you sure you want to remove catalog source '${sourceId}'?`)) return;
        try {
            await window.catalogService.deleteSource(sourceId);
            await this.loadData();
        } catch (e) { alert(e.message); }
    }

    async refreshCatalogs() {
        try {
            await window.catalogService.refreshCatalogs();
            await this.loadData();
            alert("Catalogs refreshed successfully.");
        } catch (e) { alert(e.message); }
    }

    async uploadDockerImage() {
        const fileInput = this.querySelector("#docker-image-file");
        const statusEl = this.querySelector("#upload-status");
        if (!fileInput || !fileInput.files.length) return alert("Please select a .tar image archive first.");
        const file = fileInput.files[0];
        if (statusEl) statusEl.textContent = `Uploading and loading ${file.name}...`;
        try {
            const res = await window.catalogService.uploadImage(file);
            if (statusEl) statusEl.textContent = `Success: ${res.message || 'Image loaded'}`;
            const imgData = await window.catalogService.fetchImages().catch(() => ({ images: [] }));
            this.images = imgData.images || [];
            this.render();
        } catch (e) {
            if (statusEl) statusEl.textContent = `Error: ${e.message}`;
        }
    }

    showInstallModal(appId) {
        const app = this.apps.find(a => a.id === appId);
        if (!app) return;
        const modal = document.createElement("div");
        modal.id = "app-install-modal";
        modal.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,15,30,0.85);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;z-index:10000;";
        modal.innerHTML = renderInstallModalTemplate(app);
        document.body.appendChild(modal);

        const edgeCheck = modal.querySelector("#install-edge-check");
        const domainBox = modal.querySelector("#install-edge-domain-box");
        edgeCheck.onchange = () => { domainBox.style.display = edgeCheck.checked ? "block" : "none"; };
        modal.querySelector("#close-install-modal-btn").onclick = () => modal.remove();

        modal.querySelector("#confirm-install-btn").onclick = async () => {
            if (!modal.querySelector("#install-consent-check").checked) return alert("Please confirm consent to permissions.");
            const target_node = modal.querySelector("#install-node-select").value;
            const expose_edge = edgeCheck.checked;
            const domain = modal.querySelector("#install-edge-domain").value.trim() || `${app.id}.roost.local`;
            try {
                await window.catalogService.installApp({
                    app_id: app.id, target_node, expose_edge_ingress: expose_edge, edge_domain: expose_edge ? domain : null
                });
                modal.remove();
                alert(`Successfully deployed ${app.name}!`);
                if (window.switchView) window.switchView("plugins");
            } catch (err) { alert(err.message); }
        };
    }
}

if (!customElements.get("roost-app-catalog")) {
    customElements.define("roost-app-catalog", AppCatalogComponent);
}
