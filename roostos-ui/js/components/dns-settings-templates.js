/**
 * Template helpers for DnsSettingsComponent
 */

export const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export function renderDnsTemplate(state) {
    const { subsystem, forwarders, adBlocking, dependencies, isSaving, isInstalling, statusMsg } = state;
    const isTech = subsystem === "technitium";
    const hasMissing = dependencies && !dependencies.satisfied;
    const missingPkgs = dependencies ? (dependencies.packages || []).filter(p => !p.installed).map(p => p.name) : [];
    const fwdStr = Array.isArray(forwarders) ? forwarders.join(", ") : (forwarders || "");

    return html`
        <div class="dns-settings-container">
            ${statusMsg ? html`
                <div class="card" style="border-left: 4px solid var(--accent-${statusMsg.type === 'success' ? 'green' : 'red'}); padding: 12px 16px; margin-bottom: 16px;">
                    <span>${statusMsg.text}</span>
                </div>
            ` : ""}

            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header">
                    <h3>DNS Service Subsystem</h3>
                    <span class="badge ${isTech ? 'badge-info' : 'badge-success'}">${isTech ? 'Technitium DNS' : 'Local Resolver'}</span>
                </div>
                <p class="text-secondary" style="font-size: 13px; margin: 8px 0 16px 0;">
                    Choose the DNS resolution engine for this gateway router.
                </p>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
                    <div id="select-local-card" style="border: 2px solid ${!isTech ? 'var(--accent-blue)' : 'var(--card-border)'}; border-radius: 12px; padding: 16px; cursor: pointer; background: ${!isTech ? 'rgba(59, 130, 246, 0.05)' : 'transparent'};">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                            <strong style="font-size: 15px;">Local Resolver (Native)</strong>
                            <input type="radio" name="dns-subsystem" value="local" ${!isTech ? 'checked' : ''} style="cursor: pointer;">
                        </div>
                        <p class="text-secondary" style="font-size: 12px; line-height: 1.4;">
                            Lightweight DNS caching via nftables and Kea DHCP integration. Minimal CPU and RAM footprint.
                        </p>
                        <span class="badge badge-outline" style="margin-top: 8px;">Zero container overhead</span>
                    </div>

                    <div id="select-tech-card" style="border: 2px solid ${isTech ? 'var(--accent-blue)' : 'var(--card-border)'}; border-radius: 12px; padding: 16px; cursor: pointer; background: ${isTech ? 'rgba(59, 130, 246, 0.05)' : 'transparent'};">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                            <strong style="font-size: 15px;">Technitium DNS Server</strong>
                            <input type="radio" name="dns-subsystem" value="technitium" ${isTech ? 'checked' : ''} style="cursor: pointer;">
                        </div>
                        <p class="text-secondary" style="font-size: 12px; line-height: 1.4;">
                            Full-featured DNS server with built-in ad/malware blocking, DNS-over-HTTPS (DoH), and Web Console.
                        </p>
                        <span class="badge badge-outline" style="margin-top: 8px;">Containerized (Docker)</span>
                    </div>
                </div>

                ${isTech ? html`
                    <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(6, 182, 212, 0.08); padding: 12px 16px; border-radius: 10px; border: 1px solid rgba(6, 182, 212, 0.25);">
                        <div>
                            <strong style="font-size: 13px;">Technitium Web Console</strong>
                            <div style="font-size: 12px; color: var(--text-secondary);">Direct admin portal available on port 5380</div>
                        </div>
                        <a href="http://${window.location.hostname}:5380" target="_blank" class="btn btn-secondary btn-sm" style="text-decoration: none;">
                            Open Console ↗
                        </a>
                    </div>
                ` : ""}
            </div>

            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header">
                    <h3>Forwarding & Filter Rules</h3>
                </div>
                <div style="margin-top: 12px;">
                    <label style="font-size: 13px; font-weight: 600; display: block; margin-bottom: 6px;">Upstream DNS Servers (comma-separated)</label>
                    <input type="text" id="dns-forwarders-input" class="inline-input" value="${fwdStr}" placeholder="1.1.1.1, 8.8.8.8, 9.9.9.9" style="margin-bottom: 16px;">

                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
                        <input type="checkbox" id="dns-adblock-input" ${adBlocking || isTech ? 'checked' : ''} ${isTech ? 'disabled' : ''} style="cursor: pointer; width: 16px; height: 16px;">
                        <label for="dns-adblock-input" style="font-size: 13px; cursor: pointer;">
                            Enable Ad & Malware Domain Blocking ${isTech ? '<span class="text-secondary">(Built-in with Technitium)</span>' : ''}
                        </label>
                    </div>

                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
                        <input type="checkbox" id="dns-autoinstall-input" checked style="cursor: pointer; width: 16px; height: 16px;">
                        <label for="dns-autoinstall-input" style="font-size: 13px; cursor: pointer;">
                            Automatically install missing OS dependencies if required
                        </label>
                    </div>

                    <button id="save-dns-btn" class="btn btn-primary" ${isSaving ? 'disabled' : ''}>
                        ${isSaving ? "Applying Configuration..." : "Save & Apply DNS Settings"}
                    </button>
                </div>
            </div>

            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header table-action-bar">
                    <div>
                        <h3>Subsystem Dependencies</h3>
                        <p class="text-secondary" style="font-size: 12px;">
                            OS package requirements for feature: <code>${isTech ? "dns_technitium" : "dns_local"}</code>
                        </p>
                    </div>
                    <span class="badge ${hasMissing ? 'badge-danger' : 'badge-success'}">
                        ${hasMissing ? 'Missing Packages' : 'All Satisfied'}
                    </span>
                </div>

                ${hasMissing ? html`
                    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 10px; padding: 12px 16px; margin: 12px 0; display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <strong style="color: var(--accent-red); font-size: 13px;">Missing required packages:</strong>
                            <span style="font-size: 13px; margin-left: 6px;"><code>${missingPkgs.join(", ")}</code></span>
                        </div>
                        <button id="install-subsystem-deps-btn" class="btn btn-danger btn-sm" ${isInstalling ? 'disabled' : ''}>
                            ${isInstalling ? 'Installing...' : 'Install Missing Dependencies'}
                        </button>
                    </div>
                ` : ""}

                <div class="table-responsive" style="margin-top: 12px;">
                    <table class="data-table">
                        <thead>
                            <tr><th>Package Name</th><th>Status</th><th>Version / Detection</th></tr>
                        </thead>
                        <tbody>
                            ${(dependencies && dependencies.packages) ? dependencies.packages.map(p => html`
                                <tr>
                                    <td><strong><code>${p.name}</code></strong></td>
                                    <td>
                                        <span class="badge ${p.installed ? 'badge-success' : 'badge-danger'}">
                                            ${p.installed ? 'Installed' : 'Missing'}
                                        </span>
                                    </td>
                                    <td><code>${p.version || (p.installed ? 'detected' : 'not found')}</code></td>
                                </tr>
                            `).join("") : html`<tr><td colspan="3" class="empty-state">No dependency data available.</td></tr>`}
                        </tbody>
                    </table>
                </div>
            </div>

            ${renderSystemDepsCard(state.systemDeps)}
        </div>
    `;
}

export function renderSystemDepsCard(systemDeps) {
    if (!systemDeps || !systemDeps.reports) return "";
    const reports = systemDeps.reports || [];
    return html`
        <div class="card">
            <div class="card-header table-action-bar">
                <div>
                    <h3>System Dependencies Overview</h3>
                    <p class="text-secondary" style="font-size: 12px;">
                        Package Manager: <code>${systemDeps.manager_name || "apt"} (${systemDeps.os_family || "linux"})</code>
                    </p>
                </div>
                <span class="badge ${systemDeps.all_satisfied ? 'badge-success' : 'badge-warning'}">
                    ${systemDeps.all_satisfied ? 'System Ready' : 'Incomplete Dependencies'}
                </span>
            </div>

            <div class="table-responsive" style="margin-top: 12px;">
                <table class="data-table">
                    <thead>
                        <tr><th>Feature</th><th>Required Packages</th><th>Status</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                        ${reports.map(rep => {
                            const missing = (rep.packages || []).filter(p => !p.installed).map(p => p.name);
                            return html`
                                <tr>
                                    <td><strong>${rep.feature}</strong></td>
                                    <td>${(rep.packages || []).map(p => `<code>${p.name}</code>`).join(", ")}</td>
                                    <td>
                                        ${rep.satisfied
                                            ? html`<span class="badge badge-success">Satisfied</span>`
                                            : html`<span class="badge badge-danger">Missing: ${missing.join(", ")}</span>`}
                                    </td>
                                    <td>
                                        ${!rep.satisfied ? html`
                                            <button class="btn btn-secondary btn-sm install-feat-btn" data-feature="${rep.feature}">
                                                Install
                                            </button>
                                        ` : "-"}
                                    </td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}
