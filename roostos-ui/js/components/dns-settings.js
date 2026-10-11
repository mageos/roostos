/**
 * DnsSettingsComponent - Web Component for DNS Subsystem & OS Dependencies
 */

import { renderDnsTemplate } from "./dns-settings-templates.js";

export class DnsSettingsComponent extends HTMLElement {
    constructor() {
        super();
        this.subsystem = "local";
        this.forwarders = ["1.1.1.1", "8.8.8.8"];
        this.adBlocking = false;
        this.dependencies = null;
        this.serviceUrl = null;
        this.systemDeps = null;
        this.statusMsg = null;
        this.isSaving = false;
        this.isInstalling = false;
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        try {
            if (window.securityService) {
                const data = await window.securityService.fetchDnsConfig();
                this.setData(data);
            }
            if (window.systemService) {
                this.systemDeps = await window.systemService.fetchDependencies();
                this.render();
            }
        } catch (err) {
            this.statusMsg = { type: "danger", text: `Failed to load DNS configuration: ${err.message}` };
            this.render();
        }
    }

    setData(data) {
        if (!data) return;
        this.subsystem = data.subsystem || "local";
        this.forwarders = data.forwarders || ["1.1.1.1", "8.8.8.8"];
        this.adBlocking = !!data.ad_blocking_enabled;
        this.dependencies = data.dependencies || null;
        this.serviceUrl = data.service_url || (this.subsystem === "technitium" ? `http://${window.location.hostname}:5380` : null);
        this.render();
    }

    render() {
        this.innerHTML = renderDnsTemplate({
            subsystem: this.subsystem,
            forwarders: this.forwarders,
            adBlocking: this.adBlocking,
            dependencies: this.dependencies,
            serviceUrl: this.serviceUrl,
            systemDeps: this.systemDeps,
            statusMsg: this.statusMsg,
            isSaving: this.isSaving,
            isInstalling: this.isInstalling,
        });
        this.bindEvents();
    }

    bindEvents() {
        const localCard = this.querySelector("#select-local-card");
        const techCard = this.querySelector("#select-tech-card");
        if (localCard) localCard.onclick = () => this.switchSubsystem("local");
        if (techCard) techCard.onclick = () => this.switchSubsystem("technitium");

        const saveBtn = this.querySelector("#save-dns-btn");
        if (saveBtn) saveBtn.onclick = () => this.saveSettings();

        const instSubBtn = this.querySelector("#install-subsystem-deps-btn");
        if (instSubBtn) instSubBtn.onclick = () => this.installSubsystemDeps();

        this.querySelectorAll(".install-feat-btn").forEach(btn => {
            btn.onclick = (e) => this.installFeatureDeps(e.target.dataset.feature);
        });
    }

    async switchSubsystem(subsystem) {
        if (this.subsystem === subsystem) return;
        this.subsystem = subsystem;
        if (subsystem === "technitium") this.adBlocking = true;

        if (this.systemDeps && this.systemDeps.reports) {
            const key = subsystem === "technitium" ? "dns_technitium" : "dns_local";
            const found = this.systemDeps.reports.find(r => r.feature === key);
            if (found) {
                this.dependencies = found;
            }
        }
        this.render();
    }

    async saveSettings() {
        const fwdInput = this.querySelector("#dns-forwarders-input");
        const adbInput = this.querySelector("#dns-adblock-input");
        const autoInput = this.querySelector("#dns-autoinstall-input");

        const forwarders = (fwdInput?.value || "")
            .split(",")
            .map(s => s.trim())
            .filter(Boolean);

        const payload = {
            subsystem: this.subsystem,
            forwarders: forwarders.length ? forwarders : ["1.1.1.1", "8.8.8.8"],
            ad_blocking_enabled: this.subsystem === "technitium" ? true : (adbInput ? adbInput.checked : false),
            auto_install_dependencies: autoInput ? autoInput.checked : false,
        };

        this.isSaving = true;
        this.statusMsg = null;
        this.render();

        try {
            const res = await window.securityService.saveDnsConfig(payload);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to save DNS configuration");
            this.statusMsg = { type: "success", text: "DNS configuration updated successfully!" };
            this.setData(data);
            if (window.systemService) {
                this.systemDeps = await window.systemService.fetchDependencies();
            }
        } catch (err) {
            this.statusMsg = { type: "danger", text: err.message };
        } finally {
            this.isSaving = false;
            this.render();
        }
    }

    async installSubsystemDeps() {
        const feature = this.subsystem === "technitium" ? "dns_technitium" : "dns_local";
        await this.installFeatureDeps(feature);
    }

    async installFeatureDeps(feature) {
        if (!feature || !window.systemService) return;
        this.isInstalling = true;
        this.statusMsg = null;
        this.render();

        try {
            await window.systemService.installDependencies(feature);
            this.statusMsg = { type: "success", text: `Dependencies for ${feature} installed successfully!` };
            await this.loadData();
        } catch (err) {
            this.statusMsg = { type: "danger", text: `Installation error: ${err.message}` };
        } finally {
            this.isInstalling = false;
            this.render();
        }
    }
}

if (!customElements.get("roost-dns-settings")) {
    customElements.define("roost-dns-settings", DnsSettingsComponent);
}
