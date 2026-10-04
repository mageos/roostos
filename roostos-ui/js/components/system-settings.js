const SYSTEM_TEMPLATE = /* html */ `
    <div id="system-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('system', 'basic')">Updates & System</button>
            <button class="tab-btn" onclick="switchSubTab('system', 'advanced')">Backup & Recovery</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card" style="margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
                    <div>
                        <h2 style="margin: 0 0 4px 0;">OS & Security Updates</h2>
                        <p style="font-size: 13px; color: var(--text-secondary); margin: 0;">
                            Centralized operating system packages, unattended upgrades, and reboot windows.
                        </p>
                    </div>
                    <div id="update-status-badges" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                        <span id="badge-os-type" class="badge badge-outline" style="font-size: 12px;">OS: Detecting...</span>
                        <span id="badge-update-status" class="badge" style="font-size: 12px;">Checking...</span>
                        <span id="badge-security-status" class="badge" style="display: none; font-size: 12px; background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);">0 Security</span>
                    </div>
                </div>

                <div id="reboot-warning-banner" style="display: none; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); color: #f59e0b; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px;">
                    ⚠️ <strong>Reboot Required:</strong> A kernel or core system update was applied. A reboot is pending.
                </div>

                <div id="update-action-banner" style="display: none; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px;"></div>

                <div style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;">
                    <button class="btn btn-primary" id="btn-check-updates" onclick="systemComponent.checkUpdates()">Check for Updates</button>
                    <button class="btn btn-success" id="btn-install-updates" onclick="systemComponent.installUpdates(false)" disabled>Install All Updates</button>
                    <button class="btn btn-secondary" id="btn-install-security" onclick="systemComponent.installUpdates(true)" disabled>Install Security Only</button>
                </div>

                <div id="packages-container" style="display: none; margin-bottom: 20px;">
                    <h3 style="font-size: 13px; color: var(--text-secondary); margin-bottom: 8px;">Available Package Updates:</h3>
                    <div id="packages-list" style="background: rgba(0,0,0,0.2); border: 1px solid var(--card-border); border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; max-height: 160px; overflow-y: auto;"></div>
                </div>

                <hr style="border: 0; border-top: 1px solid var(--card-border); margin: 20px 0;">

                <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Automatic Updates & Maintenance Schedule</h3>
                <form id="updates-config-form" onsubmit="event.preventDefault(); systemComponent.saveUpdatesConfig();" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; align-items: end;">
                    <div class="form-group" style="margin: 0;">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                            <input type="checkbox" id="cfg-auto-update"> <span>Enable Auto Updates</span>
                        </label>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                            <input type="checkbox" id="cfg-auto-security"> <span>Security Updates Only</span>
                        </label>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                            <input type="checkbox" id="cfg-auto-reboot"> <span>Auto-Reboot in Window</span>
                        </label>
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label for="cfg-reboot-window" style="font-size: 12px; color: var(--text-secondary);">Reboot Window</label>
                        <input type="text" id="cfg-reboot-window" placeholder="Sun 03:00" style="margin-top: 4px; padding: 6px 10px; font-size: 13px;">
                    </div>
                    <div>
                        <button type="submit" class="btn btn-primary" id="btn-save-update-config" style="width: 100%;">Save Schedule</button>
                    </div>
                </form>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>System Backup & Recovery</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Create encrypted configuration snapshots prior to kernel or package updates.
                </p>
                <div style="display: flex; gap: 12px; align-items: flex-end; max-width: 480px; flex-wrap: wrap;">
                    <div class="form-group" style="flex: 1; min-width: 200px; margin: 0;">
                        <label for="backup-passphrase">Backup Passphrase (Optional)</label>
                        <input type="password" id="backup-passphrase" placeholder="Encryption passphrase" style="margin-top: 6px; padding: 6px 10px;">
                    </div>
                    <button class="btn btn-primary" onclick="systemComponent.triggerBackup()" style="height: 36px;">Create Backup</button>
                </div>
                <div id="backup-result" style="margin-top: 12px; font-size: 13px; display: none;"></div>
            </div>
        </div>
    </div>
`;

class SystemComponent {
    constructor() {
        this.template = SYSTEM_TEMPLATE;
    }

    mount(container) {
        if (!container) return;
        container.insertAdjacentHTML("beforeend", this.template);
    }

    async render(sysData) {
        await Promise.all([this.loadUpdatesStatus(), this.loadUpdatesConfig()]);
    }

    showBanner(msg, isError = false) {
        const b = document.getElementById("update-action-banner");
        if (!b) return;
        b.style.display = "block";
        b.style.background = isError ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)";
        b.style.border = isError ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid rgba(16, 185, 129, 0.3)";
        b.style.color = isError ? "#ef4444" : "#10b981";
        b.innerHTML = msg;
    }

    async loadUpdatesStatus() {
        if (!window.systemService) return;
        try {
            const data = await window.systemService.fetchUpdatesStatus();
            const osBadge = document.getElementById("badge-os-type");
            if (osBadge) osBadge.textContent = `OS: ${data.os_type || "Linux"}`;

            const statusBadge = document.getElementById("badge-update-status");
            const secBadge = document.getElementById("badge-security-status");
            const rebootBanner = document.getElementById("reboot-warning-banner");
            const btnInstall = document.getElementById("btn-install-updates");
            const btnSec = document.getElementById("btn-install-security");
            const count = data.updates_available || 0;
            const secCount = data.security_updates_available || 0;

            if (statusBadge) {
                statusBadge.textContent = count === 0 ? "Up to Date" : `${count} Update${count > 1 ? "s" : ""} Available`;
                statusBadge.style.background = count === 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.15)";
                statusBadge.style.color = count === 0 ? "#10b981" : "#3b82f6";
            }
            if (secBadge) {
                secBadge.style.display = secCount > 0 ? "inline-block" : "none";
                secBadge.textContent = `${secCount} Security Update${secCount > 1 ? "s" : ""}`;
            }
            if (rebootBanner) rebootBanner.style.display = data.reboot_required ? "block" : "none";
            if (btnInstall) btnInstall.disabled = count === 0;
            if (btnSec) btnSec.disabled = secCount === 0;

            const pkgContainer = document.getElementById("packages-container");
            const pkgList = document.getElementById("packages-list");
            if (pkgContainer && pkgList) {
                const esc = window.escapeHtml || (s => s);
                pkgContainer.style.display = data.packages && data.packages.length > 0 ? "block" : "none";
                pkgList.innerHTML = (data.packages || []).map(p => `<div>• ${esc(p)}</div>`).join("");
            }
        } catch (e) {
            console.error("Failed to load updates status:", e);
        }
    }

    async checkUpdates() {
        const btn = document.getElementById("btn-check-updates");
        if (btn) { btn.disabled = true; btn.textContent = "Checking..."; }
        try {
            const res = await window.systemService.checkUpdates();
            this.showBanner(res.updates_available > 0
                ? `Found ${res.updates_available} updates (${res.security_updates_available} security).`
                : "System is fully up to date!");
            await this.loadUpdatesStatus();
        } catch (e) {
            this.showBanner(`Check failed: ${e.message}`, true);
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = "Check for Updates"; }
        }
    }

    async installUpdates(securityOnly = false) {
        const btn = document.getElementById(securityOnly ? "btn-install-security" : "btn-install-updates");
        if (btn) { btn.disabled = true; btn.textContent = "Installing..."; }
        try {
            const res = await window.systemService.installUpdates(securityOnly);
            let msg = `Successfully updated ${res.packages_updated} packages.`;
            if (res.reboot_required) {
                msg += res.scheduled_reboot_time ? ` Reboot scheduled for ${res.scheduled_reboot_time}.` : " Reboot pending.";
            }
            this.showBanner(msg);
            await this.loadUpdatesStatus();
        } catch (e) {
            this.showBanner(`Installation failed: ${e.message}`, true);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = securityOnly ? "Install Security Only" : "Install All Updates";
            }
        }
    }

    async loadUpdatesConfig() {
        if (!window.systemService) return;
        try {
            const cfg = await window.systemService.fetchUpdatesConfig();
            const autoUp = document.getElementById("cfg-auto-update");
            const autoSec = document.getElementById("cfg-auto-security");
            const autoReboot = document.getElementById("cfg-auto-reboot");
            const rebootWin = document.getElementById("cfg-reboot-window");
            if (autoUp) autoUp.checked = !!cfg.auto_update_enabled;
            if (autoSec) autoSec.checked = !!cfg.security_only;
            if (autoReboot) autoReboot.checked = !!cfg.auto_reboot;
            if (rebootWin) rebootWin.value = cfg.reboot_window || "Sun 03:00";
        } catch (e) {
            console.error("Failed to load updates config:", e);
        }
    }

    async saveUpdatesConfig() {
        const autoUp = document.getElementById("cfg-auto-update");
        const autoSec = document.getElementById("cfg-auto-security");
        const autoReboot = document.getElementById("cfg-auto-reboot");
        const rebootWin = document.getElementById("cfg-reboot-window");
        const payload = {
            auto_update_enabled: autoUp ? autoUp.checked : false,
            security_only: autoSec ? autoSec.checked : false,
            auto_reboot: autoReboot ? autoReboot.checked : true,
            reboot_window: rebootWin ? rebootWin.value : "Sun 03:00"
        };
        try {
            await window.systemService.saveUpdatesConfig(payload);
            this.showBanner("Update schedule and preferences saved.");
        } catch (e) {
            this.showBanner(`Failed to save preferences: ${e.message}`, true);
        }
    }

    async triggerBackup() {
        const passEl = document.getElementById("backup-passphrase");
        const resEl = document.getElementById("backup-result");
        const pass = passEl ? passEl.value : "";
        try {
            await window.systemService.triggerBackup(pass);
            if (resEl) {
                resEl.style.display = "block";
                resEl.style.color = "#10b981";
                resEl.textContent = "Backup snapshot created successfully.";
            }
        } catch (e) {
            if (resEl) {
                resEl.style.display = "block";
                resEl.style.color = "#ef4444";
                resEl.textContent = `Backup failed: ${e.message}`;
            }
        }
    }
}

window.SystemComponent = SystemComponent;
window.systemComponent = new SystemComponent();
