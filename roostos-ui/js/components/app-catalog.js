/**
 * AppCatalogComponent - Web Component for RoostOS Application Catalog & Local Deployments
 */

import {
    renderCatalogTemplate,
    renderAppsGridTemplate,
    renderSourcesTemplate,
    renderSourceRowTemplate,
    renderInlineSourceRowTemplate,
    renderImagesTemplate
} from "./app-catalog-templates.js";

export class AppCatalogComponent extends HTMLElement {
    constructor() {
        super();
        this.activeTab = "apps";
        this.selectedCategory = "all";
        this.apps = [];
        this.sources = [];
        this.images = [];
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
            btn.onclick = () => {
                this.selectedCategory = btn.dataset.category;
                this.render();
            };
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

        this.querySelector("#upload-image-btn")?.addEventListener("click", () => this.uploadDockerImage());
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
        modal.innerHTML = `
            <div class="card" style="width:90%;max-width:540px;background:#131b2e;border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:24px;color:#f1f5f9;font-family:'Outfit',sans-serif;">
                <h3 style="margin-top:0;margin-bottom:8px;">Install ${app.name}</h3>
                <p style="font-size:13px;color:#94a3b8;margin-bottom:16px;">${app.description}</p>
                <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:12px;margin-bottom:16px;font-size:12px;">
                    <div style="font-weight:600;margin-bottom:6px;color:#e2e8f0;">Required System Scopes & Permissions:</div>
                    <div style="color:#94a3b8;">Ports: ${(app.container.ports || []).map(p => `${p.host_port}➔${p.container_port}`).join(", ") || "None"}</div>
                    <div style="color:#94a3b8;">Volumes: ${(app.container.volumes || []).map(v => `${v.host_path}➔${v.container_path}`).join(", ") || "None"}</div>
                </div>
                <div style="margin-bottom:12px;">
                    <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Target Node / Compute:</label>
                    <select id="install-node-select" class="input-field" style="width:100%;">
                        <option value="local">local (Current Node)</option>
                    </select>
                </div>
                <div style="margin-bottom:16px;">
                    <label style="font-size:13px;display:flex;align-items:center;gap:8px;cursor:pointer;">
                        <input type="checkbox" id="install-consent-check">
                        <span>I consent to granting these container volume & port permissions.</span>
                    </label>
                </div>
                <div style="border-top:1px solid rgba(255,255,255,0.08);padding-top:12px;margin-bottom:16px;">
                    <label style="font-size:13px;display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:8px;">
                        <input type="checkbox" id="install-edge-check">
                        <span>Expose externally via Edge Gateway (CGNAT Bypass)</span>
                    </label>
                    <div id="install-edge-domain-box" style="display:none;margin-left:22px;">
                        <input type="text" id="install-edge-domain" class="input-field" placeholder="${app.id}.yourdomain.com" style="width:100%;font-size:13px;">
                    </div>
                </div>
                <div style="display:flex;justify-content:flex-end;gap:12px;">
                    <button class="btn btn-secondary btn-sm" id="close-install-modal-btn">Cancel</button>
                    <button class="btn btn-primary btn-sm" id="confirm-install-btn">Confirm & Install</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        const edgeCheck = modal.querySelector("#install-edge-check");
        const domainBox = modal.querySelector("#install-edge-domain-box");
        edgeCheck.onchange = () => { domainBox.style.display = edgeCheck.checked ? "block" : "none"; };
        modal.querySelector("#close-install-modal-btn").onclick = () => modal.remove();

        modal.querySelector("#confirm-install-btn").onclick = async () => {
            const consented = modal.querySelector("#install-consent-check").checked;
            if (!consented) return alert("Please confirm consent to the required container permissions.");
            const target_node = modal.querySelector("#install-node-select").value;
            const expose_edge = edgeCheck.checked;
            const domain = modal.querySelector("#install-edge-domain").value.trim() || `${app.id}.roost.local`;
            try {
                await window.catalogService.installApp({
                    app_id: app.id,
                    target_node,
                    expose_edge_ingress: expose_edge,
                    edge_domain: expose_edge ? domain : null
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
