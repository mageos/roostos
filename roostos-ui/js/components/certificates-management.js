/**
 * CertificatesManagementComponent - Web Component for SSL/TLS & ACME Management
 * Handles Let's Encrypt automated certificate issuance, DNS-01 and HTTP-01 validations,
 * Root CA export for LAN devices, and certificate renewal.
 */

import {
    html,
    renderCertificatesTemplate,
    renderCertRowTemplate,
    renderInlineCertRowTemplate,
} from "./certificates-templates.js";

const apiFetch = (url, options = {}) => {
    if (window.authService?.apiFetch) return window.authService.apiFetch(url, options);
    const token = localStorage.getItem("roostos_token");
    const headers = { ...options.headers };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, { ...options, headers });
};

export class CertificatesManagementComponent extends HTMLElement {
    constructor() {
        super();
        this.caStatus = null;
        this.acmeSettings = null;
        this.certificates = [];
    }

    connectedCallback() {
        this.loadData();
    }

    async loadData() {
        try {
            const [statusRes, acmeRes, certsRes] = await Promise.all([
                apiFetch("/api/v1/system/certificates"),
                apiFetch("/api/v1/system/certificates/acme/settings"),
                apiFetch("/api/v1/system/certificates/domains"),
            ]);

            if (statusRes?.ok) {
                const data = await statusRes.json();
                this.caStatus = data.root_ca || null;
            }
            if (acmeRes?.ok) {
                this.acmeSettings = await acmeRes.json();
            }
            if (certsRes?.ok) {
                const data = await certsRes.json();
                this.certificates = Array.isArray(data) ? data : [];
            }
        } catch (e) {
            console.warn("Could not load certificates data:", e);
        }
        this.render();
    }

    render() {
        const certList = Array.isArray(this.certificates) ? this.certificates : [];
        const rowsHtml = certList.length === 0
            ? html`<tr><td colspan="6" class="empty-state">No domain certificates ordered yet. Click "+ Request Certificate" to automate SSL.</td></tr>`
            : certList.map(c => renderCertRowTemplate(c)).join("");

        this.innerHTML = renderCertificatesTemplate(this.caStatus, this.acmeSettings, this.certificates, rowsHtml);

        this.querySelector("#save-acme-settings-btn")?.addEventListener("click", () => this.saveAcmeSettings());
        this.querySelectorAll("#top-add-cert-btn, #bottom-add-cert-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });

        this.querySelectorAll(".renew-cert-btn").forEach(btn => {
            btn.onclick = (e) => this.renewCert(e.target.dataset.domain);
        });

        this.querySelectorAll(".delete-cert-btn").forEach(btn => {
            btn.onclick = (e) => this.deleteCert(e.target.dataset.domain);
        });
    }

    async saveAcmeSettings() {
        const email = this.querySelector("#acme-email-input")?.value?.trim() || "";
        const defaultChallenge = this.querySelector("#acme-default-challenge-select")?.value || "dns-01";
        const staging = this.querySelector("#acme-staging-select")?.value === "true";

        const payload = {
            email,
            staging,
            default_challenge: defaultChallenge,
            dns_providers: this.acmeSettings?.dns_providers || {},
        };

        try {
            const res = await apiFetch("/api/v1/system/certificates/acme/settings", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (res.ok) {
                window.toastService?.success?.("ACME settings saved successfully.") || alert("Settings saved.");
                this.acmeSettings = payload;
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail || "Failed to save settings."}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#certificates-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const empty = tbody.querySelector(".empty-state");
        if (empty) empty.parentElement.remove();

        const tr = document.createElement("tr");
        tr.className = "inline-add-row";
        tr.innerHTML = renderInlineCertRowTemplate();
        tbody.prepend(tr);

        const challengeSelect = tr.querySelector(".cert-challenge-select");
        const provFields = tr.querySelector(".dns-prov-fields");
        challengeSelect?.addEventListener("change", (e) => {
            if (provFields) {
                provFields.style.display = e.target.value === "dns-01" ? "block" : "none";
            }
        });

        tr.querySelector(".cancel-cert-btn")?.addEventListener("click", () => {
            tr.remove();
            if (this.certificates.length === 0) this.render();
        });

        tr.querySelector(".save-cert-btn")?.addEventListener("click", () => this.submitOrder(tr));
    }

    async submitOrder(row) {
        const domain = row.querySelector(".cert-domain-input")?.value?.trim().toLowerCase();
        const sansRaw = row.querySelector(".cert-sans-input")?.value?.trim() || "";
        const challengeType = row.querySelector(".cert-challenge-select")?.value || "dns-01";
        const dnsProvider = row.querySelector(".cert-provider-select")?.value || "cloudflare";
        const token = row.querySelector(".cert-token-input")?.value?.trim() || "";
        const autoRenew = row.querySelector(".cert-autorenew-input")?.checked !== false;

        if (!domain) {
            alert("Please specify a domain name (e.g. router.yourdomain.com).");
            return;
        }

        const sans = sansRaw ? sansRaw.split(",").map(s => s.trim().toLowerCase()).filter(Boolean) : [];
        const payload = {
            domain,
            sans,
            challenge_type: challengeType,
            dns_provider: challengeType === "dns-01" ? dnsProvider : null,
            dns_credentials: token ? { api_token: token, token: token } : {},
            auto_renew: autoRenew,
        };

        const saveBtn = row.querySelector(".save-cert-btn");
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = "Ordering...";
        }

        try {
            const res = await apiFetch("/api/v1/system/certificates/domains", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                window.toastService?.success?.(`SSL Certificate for '${domain}' ordered successfully!`) || alert(`Certificate ordered!`);
                await this.loadData();
            } else {
                const err = await res.json();
                alert(`Error ordering certificate: ${err.detail || "Request failed."}`);
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.textContent = "Request";
                }
            }
        } catch (e) {
            alert(`Network error: ${e.message}`);
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = "Request";
            }
        }
    }

    async renewCert(domain) {
        if (!confirm(`Force renewal of SSL certificate for '${domain}' now?`)) return;

        try {
            const res = await apiFetch(`/api/v1/system/certificates/domains/${encodeURIComponent(domain)}/renew`, {
                method: "POST",
            });
            if (res.ok) {
                window.toastService?.success?.(`Certificate for '${domain}' renewed!`) || alert("Certificate renewed!");
                await this.loadData();
            } else {
                const err = await res.json();
                alert(`Renewal error: ${err.detail || "Failed to renew certificate."}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    }

    async deleteCert(domain) {
        if (!confirm(`Are you sure you want to delete certificate for '${domain}'?`)) return;

        try {
            const res = await apiFetch(`/api/v1/system/certificates/domains/${encodeURIComponent(domain)}`, {
                method: "DELETE",
            });
            if (res.ok) {
                await this.loadData();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail || "Failed to delete certificate."}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    }
}

if (!customElements.get("certificates-management")) {
    customElements.define("certificates-management", CertificatesManagementComponent);
}
