const FIREWALL_TEMPLATE = /* html */ `
    <div id="firewall-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('firewall', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('firewall', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Firewall Input Rules</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Allow or block inbound traffic on specific interfaces and ports (e.g. SSH on WAN, HTTP on eth0).
                </p>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddFirewallRuleForm('top')">+ Add Rule</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Rule Name</th>
                                <th>Interface</th>
                                <th>Protocol</th>
                                <th>Port</th>
                                <th>Source</th>
                                <th>Action</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="firewall-rules-table-body">
                            <tr>
                                <td colspan="8" class="empty-state">No firewall input rules configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddFirewallRuleForm('bottom')">+ Add Rule</button>
                </div>
            </div>

            <div class="card">
                <h2>Port Forwarding Rules (NAT)</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="alert('Demo: port forwards can be configured via REST API.')">+ Add Port Forward</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Rule Name</th>
                                <th>Protocol</th>
                                <th>External Port</th>
                                <th>Internal Destination</th>
                                <th>Internal Port</th>
                            </tr>
                        </thead>
                        <tbody id="nat-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">No port forwarding rules defined.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Global IP Blocking Rules</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Block outbound or inbound traffic for specific IP subnets or external servers.
                </p>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="alert('Demo: IP block rules are managed dynamically.')">+ Add Block Rule</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Rule Name</th>
                                <th>Direction</th>
                                <th>Target IP / Subnet</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="ip-blocks-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">No custom IP blocking rules configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card" style="margin-top: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h2>Firewall Block Logs</h2>
                    <button class="btn btn-secondary btn-sm" onclick="refreshFirewallBlocks()">Refresh Logs</button>
                </div>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Real-time log of packets blocked/dropped by firewall rules and policies.
                </p>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Blocked by Rule</th>
                                <th>Protocol</th>
                                <th>Source Connection</th>
                                <th>Destination Connection</th>
                                <th>In/Out</th>
                            </tr>
                        </thead>
                        <tbody id="firewall-blocks-table-body">
                            <tr>
                                <td colspan="6" class="empty-state">Loading firewall block logs...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
`;

class FirewallComponent {
    constructor() {
        this.template = FIREWALL_TEMPLATE;
        this.inputRules = [];
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderFirewallView = () => this.render();
        window.showAddFirewallRuleForm = (pos) => this.showAddFirewallRuleForm(pos);
        window.saveNewFirewallRule = () => this.saveNewFirewallRule();
        window.editFirewallRuleInline = (idx) => this.editFirewallRuleInline(idx);
        window.saveFirewallRuleInline = (idx) => this.saveFirewallRuleInline(idx);
        window.deleteFirewallRule = (idx) => this.deleteFirewallRule(idx);
        window.toggleFirewallRule = (idx) => this.toggleFirewallRule(idx);
        window.cancelFirewallRuleForm = () => this.renderInputRules();
        window.refreshFirewallBlocks = () => this.refreshFirewallBlocks();
    }

    render(portForwards = []) {
        // Port forwards table
        const natBody = document.getElementById("nat-table-body");
        if (natBody) {
            if (portForwards.length === 0) {
                natBody.innerHTML = '<tr><td colspan="5" class="empty-state">No port forwarding rules defined.</td></tr>';
            } else {
                natBody.innerHTML = portForwards.map(r => `
                    <tr>
                        <td><strong>${escapeHtml(r.name)}</strong></td>
                        <td><code>${escapeHtml(r.protocol.toUpperCase())}</code></td>
                        <td>${r.external_port}</td>
                        <td>${escapeHtml(r.internal_ip)}</td>
                        <td>${r.internal_port}</td>
                    </tr>
                `).join("");
            }
        }

        // Input rules table
        this.renderInputRules();

        // Advanced tab placeholder
        const blockBody = document.getElementById("ip-blocks-table-body");
        if (blockBody) {
            blockBody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-state">No custom IP blocking rules configured.</td>
                </tr>
            `;
        }

        // Trigger blocked packets logs refresh
        this.refreshFirewallBlocks();
    }

    async refreshFirewallBlocks() {
        const tbody = document.getElementById("firewall-blocks-table-body");
        if (!tbody) return;

        try {
            const data = await window.securityService.fetchFirewallBlocks();
            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No firewall blocks logged recently.</td></tr>';
            } else {
                tbody.innerHTML = data.map(b => {
                    const src = b.src_port ? `${b.src_ip}:${b.src_port}` : b.src_ip;
                    const dst = b.dst_port ? `${b.dst_ip}:${b.dst_port}` : b.dst_ip;
                    const in_out = `${b.in_face || '-'}/${b.out_face || '-'}`;
                    return `
                        <tr>
                            <td><code style="font-size: 11px;">${escapeHtml(b.timestamp)}</code></td>
                            <td><span class="badge badge-offline" style="font-weight: 500;">${escapeHtml(b.rule)}</span></td>
                            <td><code>${escapeHtml(b.proto)}</code></td>
                            <td>${escapeHtml(src)}</td>
                            <td>${escapeHtml(dst)}</td>
                            <td><code style="font-size: 11px;">${escapeHtml(in_out)}</code></td>
                        </tr>
                    `;
                }).join("");
            }
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: var(--accent-red);">Failed to load logs: ${escapeHtml(e.message)}</td></tr>`;
        }
    }

    renderWithRules(portForwards, inputRules) {
        this.inputRules = inputRules || [];
        this.render(portForwards);
    }

    renderInputRules() {
        const tableBody = document.getElementById("firewall-rules-table-body");
        if (!tableBody) return;

        if (!this.inputRules || this.inputRules.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" class="empty-state">No firewall input rules configured.</td></tr>';
            return;
        }

        tableBody.innerHTML = this.inputRules.map((r, index) => `
            <tr id="fw-rule-row-${index}">
                <td><strong>${escapeHtml(r.name)}</strong></td>
                <td><code>${escapeHtml(r.interface === "*" ? "All" : r.interface)}</code></td>
                <td><code>${escapeHtml(r.protocol.toUpperCase())}</code></td>
                <td>${r.port}</td>
                <td><code>${escapeHtml(r.source || "any")}</code></td>
                <td><span class="badge ${r.action === 'accept' ? 'badge-online' : 'badge-offline'}">${r.action.toUpperCase()}</span></td>
                <td>
                    <span class="badge ${r.enabled ? 'badge-online' : 'badge-offline'}" style="cursor: pointer;" onclick="toggleFirewallRule(${index})">
                        ${r.enabled ? "ENABLED" : "DISABLED"}
                    </span>
                </td>
                <td>
                    <button class="btn btn-secondary" onclick="editFirewallRuleInline(${index})">Edit</button>
                    <button class="btn btn-danger" onclick="deleteFirewallRule(${index})">Delete</button>
                </td>
            </tr>
        `).join("");
    }

    _buildInlineFormRow(id, defaults = {}) {
        const name = defaults.name || "";
        const iface = defaults.interface || "*";
        const protocol = defaults.protocol || "tcp";
        const port = defaults.port || "";
        const source = defaults.source || "";
        const action = defaults.action || "accept";
        const enabled = defaults.enabled !== undefined ? defaults.enabled : true;
        const isEdit = !!defaults.name;
        const saveFn = isEdit ? `saveFirewallRuleInline(${defaults._index})` : "saveNewFirewallRule()";

        return `
            <td><input type="text" id="${id}-name" value="${escapeHtml(name)}" placeholder="Allow SSH" ${isEdit ? 'readonly style="opacity: 0.6; padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"' : 'style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"'}></td>
            <td><input type="text" id="${id}-interface" value="${escapeHtml(iface)}" placeholder="eth0 or *" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="${id}-protocol" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="tcp" ${protocol === 'tcp' ? 'selected' : ''}>TCP</option>
                    <option value="udp" ${protocol === 'udp' ? 'selected' : ''}>UDP</option>
                    <option value="tcp/udp" ${protocol === 'tcp/udp' ? 'selected' : ''}>TCP/UDP</option>
                </select>
            </td>
            <td><input type="number" id="${id}-port" value="${port}" placeholder="22" min="1" max="65535" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="${id}-source" value="${escapeHtml(source)}" placeholder="any" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="${id}-action" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="accept" ${action === 'accept' ? 'selected' : ''}>ACCEPT</option>
                    <option value="drop" ${action === 'drop' ? 'selected' : ''}>DROP</option>
                </select>
            </td>
            <td>
                <label class="checkbox-container" style="margin: 0;">
                    <input type="checkbox" id="${id}-enabled" ${enabled ? 'checked' : ''}>
                    <span style="font-size: 12px;">Enabled</span>
                </label>
            </td>
            <td>
                <button class="btn btn-success" onclick="${saveFn}">Save</button>
                <button class="btn btn-secondary" onclick="cancelFirewallRuleForm()">Cancel</button>
            </td>
        `;
    }

    showAddFirewallRuleForm(position) {
        const tableBody = document.getElementById("firewall-rules-table-body");
        if (!tableBody) return;

        const existing = document.getElementById("fw-rule-add-row");
        if (existing) existing.remove();

        const addRow = document.createElement("tr");
        addRow.id = "fw-rule-add-row";
        addRow.innerHTML = this._buildInlineFormRow("add-fw-rule", {});

        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    async saveNewFirewallRule() {
        const name = document.getElementById("add-fw-rule-name").value.trim();
        const iface = document.getElementById("add-fw-rule-interface").value.trim() || "*";
        const protocol = document.getElementById("add-fw-rule-protocol").value;
        const port = parseInt(document.getElementById("add-fw-rule-port").value, 10);
        const source = document.getElementById("add-fw-rule-source").value.trim() || null;
        const action = document.getElementById("add-fw-rule-action").value;
        const enabled = document.getElementById("add-fw-rule-enabled").checked;

        if (!name || !port || isNaN(port)) {
            alert("Rule name and port are required.");
            return;
        }

        try {
            const res = await window.securityService.saveFirewallRule({
                name, interface: iface, protocol, port, source, action, enabled
            });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save firewall rule.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    editFirewallRuleInline(index) {
        const row = document.getElementById(`fw-rule-row-${index}`);
        if (!row) return;
        const r = this.inputRules[index];

        row.innerHTML = this._buildInlineFormRow(`edit-fw-rule-${index}`, {
            ...r,
            _index: index
        });
    }

    async saveFirewallRuleInline(index) {
        const r = this.inputRules[index];
        const prefix = `edit-fw-rule-${index}`;
        const iface = document.getElementById(`${prefix}-interface`).value.trim() || "*";
        const protocol = document.getElementById(`${prefix}-protocol`).value;
        const port = parseInt(document.getElementById(`${prefix}-port`).value, 10);
        const source = document.getElementById(`${prefix}-source`).value.trim() || null;
        const action = document.getElementById(`${prefix}-action`).value;
        const enabled = document.getElementById(`${prefix}-enabled`).checked;

        if (!port || isNaN(port)) {
            alert("Port is required.");
            return;
        }

        try {
            const res = await window.securityService.saveFirewallRule({
                name: r.name, interface: iface, protocol, port, source, action, enabled
            });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to update firewall rule.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deleteFirewallRule(index) {
        const r = this.inputRules[index];
        if (!confirm(`Delete firewall rule "${r.name}"?`)) return;

        try {
            const res = await window.securityService.deleteFirewallRule(r.name);
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to delete firewall rule.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async toggleFirewallRule(index) {
        const r = this.inputRules[index];
        try {
            const res = await window.securityService.saveFirewallRule({
                ...r,
                enabled: !r.enabled
            });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to toggle firewall rule.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
}

const PARENTAL_TEMPLATE = /* html */ `
    <div id="parental-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('parental', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('parental', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Access Schedules & Bedtimes</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="alert('Demo: schedules can be configured via REST API.')">+ Add Access Schedule</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Schedule Name</th>
                                <th>Targets (People/Rooms)</th>
                                <th>Active Days / Times</th>
                                <th>Daily Limit</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="schedules-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">No schedule rules configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Quick Access Override (Grant Temporary Bypass)</h2>
                <form id="bypass-form" class="form-row">
                    <input type="text" id="bypass-mac" placeholder="MAC Address" required style="max-width: 250px;">
                    <select id="bypass-duration" required style="max-width: 180px;">
                        <option value="15">15 Minutes</option>
                        <option value="30">30 Minutes</option>
                        <option value="60" selected>1 Hour</option>
                        <option value="120">2 Hours</option>
                        <option value="360">6 Hours</option>
                    </select>
                    <button type="submit" class="btn btn-primary">Grant Bypass</button>
                </form>
            </div>
        </div>
    </div>
`;

class ParentalComponent {
    constructor() {
        this.template = PARENTAL_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderParentalView = () => this.render();
        window.renderSchedules = (s) => this.renderSchedules(s);
    }

    render(schedules = []) {
        this.renderSchedules(schedules);
        
        const form = document.getElementById("bypass-form");
        if (form && !form.dataset.bound) {
            form.dataset.bound = "true";
            form.addEventListener("submit", async (e) => {
                e.preventDefault();
                const mac = document.getElementById("bypass-mac").value.trim();
                const duration = parseInt(document.getElementById("bypass-duration").value, 10);
                
                try {
                    const res = await window.securityService.triggerBypass(mac, duration);
                    if (res.ok) {
                        alert("Bypass granted successfully!");
                        if (window.loadDashboard) window.loadDashboard();
                    } else {
                        alert("Failed to grant temporary bypass.");
                    }
                } catch (err) {
                    alert(`Error: ${err.message}`);
                }
            });
        }
    }

    renderSchedules(schedules) {
        const tableBody = document.getElementById("schedules-table-body");
        if (!tableBody) return;
        if (!schedules || schedules.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No schedule rules configured.</td></tr>';
            return;
        }
        tableBody.innerHTML = schedules.map(s => `
            <tr>
                <td><strong>${escapeHtml(s.name)}</strong></td>
                <td>${s.targets.map(t => escapeHtml(t.person || t.location || t.mac || "")).join(", ")}</td>
                <td>${(s.days || []).join(", ")} <br> <span style="font-size: 11px; color: var(--text-secondary);">${s.start_time || ""} - ${s.end_time || ""}</span></td>
                <td>${s.daily_limit ? `${s.daily_limit} mins` : "None"}</td>
                <td><span class="badge badge-online">ACTIVE</span></td>
            </tr>
        `).join("");
    }
}

const DNS_TEMPLATE = /* html */ `
    <div id="dns-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('dns', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('dns', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Basic DNS Configurations</h2>
                <form id="dns-config-form" onsubmit="saveDnsConfig(event)">
                    <div class="form-group">
                        <label>Upstream DNS Forwarders (comma-separated list)</label>
                        <input type="text" id="dns-forwarders" placeholder="e.g. 1.1.1.1, 8.8.8.8" required>
                    </div>
                    <div class="form-row-multi flex-align-center" style="margin-bottom: 20px;">
                        <label class="checkbox-container">
                            <input type="checkbox" id="dns-adblock-enabled">
                            <span>Enable Whole-Network Ad & Tracker Blocking</span>
                        </label>
                    </div>
                    <button type="submit" class="btn btn-primary">Save DNS Settings</button>
                </form>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Native Advanced Settings (Local DNS Records)</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Define custom local hostnames resolved natively by the router.
                </p>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddDnsRecordForm('top')">+ Add DNS Record</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Domain Name</th>
                                <th>IP Address</th>
                                <th>Type</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="dns-records-table-body">
                            <tr>
                                <td colspan="4" class="empty-state">No custom local DNS records configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddDnsRecordForm('bottom')">+ Add DNS Record</button>
                </div>
            </div>

            <div class="card">
                <h2>Advanced Service Console</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    To configure advanced filters, blocklists, and check DNS query metrics, open the Technitium console interface.
                </p>
                <button class="btn btn-secondary" onclick="window.open('/api/services/technitium-dns/', '_blank')">Open Technitium Admin Console</button>
            </div>
        </div>
    </div>
`;

class DnsComponent {
    constructor() {
        this.template = DNS_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderDNSView = () => this.render();
        window.saveDnsConfig = (e) => this.saveDnsConfig(e);
        window.renderLocalDnsRecords = () => this.renderLocalDnsRecords();
        window.editLocalDnsInline = (idx) => this.editLocalDnsInline(idx);
        window.saveLocalDnsInline = (idx) => this.saveLocalDnsInline(idx);
        window.showAddDnsRecordForm = (pos) => this.showAddDnsRecordForm(pos);
        window.saveNewLocalDnsInline = () => this.saveNewLocalDnsInline();
        window.deleteLocalDnsRecord = (idx) => this.deleteLocalDnsRecord(idx);
    }

    render(dnsData) {
        const forwarders = dnsData?.forwarders || [];
        const adblock = dnsData?.ad_blocking_enabled || false;
        
        const forwardersInput = document.getElementById("dns-forwarders");
        if (forwardersInput) forwardersInput.value = forwarders.join(", ");
        
        const adblockEl = document.getElementById("dns-adblock-enabled");
        if (adblockEl) adblockEl.checked = adblock;

        this.renderLocalDnsRecords();
    }

    async saveDnsConfig(e) {
        e.preventDefault();
        const forwardersVal = document.getElementById("dns-forwarders").value.trim();
        const adblock = document.getElementById("dns-adblock-enabled").checked;
        
        const forwarders = forwardersVal.split(",")
                                         .map(s => s.trim())
                                         .filter(s => s.length > 0);
                                         
        try {
            const res = await window.securityService.saveDnsConfig({
                forwarders,
                ad_blocking_enabled: adblock,
                local_records: window.localDnsRecords
            });
            if (res.ok) {
                alert("DNS Resolver settings saved successfully!");
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save DNS settings.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    renderLocalDnsRecords() {
        const tableBody = document.getElementById("dns-records-table-body");
        if (!tableBody) return;
        
        if (!window.localDnsRecords || window.localDnsRecords.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No custom local DNS records configured.</td></tr>';
            return;
        }
        
        tableBody.innerHTML = window.localDnsRecords.map((r, index) => `
            <tr id="dns-record-row-${index}">
                <td><code>${escapeHtml(r.domain)}</code></td>
                <td><code>${escapeHtml(r.ip)}</code></td>
                <td><span class="badge badge-online">${escapeHtml(r.type)}</span></td>
                <td>
                    <button class="btn btn-secondary" onclick="editLocalDnsInline(${index})">Edit</button>
                    <button class="btn btn-danger" onclick="deleteLocalDnsRecord(${index})">Delete</button>
                </td>
            </tr>
        `).join("");
    }

    editLocalDnsInline(index) {
        const row = document.getElementById(`dns-record-row-${index}`);
        if (!row) return;
        const r = window.localDnsRecords[index];
        
        row.innerHTML = `
            <td><input type="text" id="edit-dns-domain-${index}" value="${escapeHtml(r.domain)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="edit-dns-ip-${index}" value="${escapeHtml(r.ip)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="edit-dns-type-${index}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px;">
                    <option value="A" ${r.type === 'A' ? 'selected' : ''}>A</option>
                    <option value="AAAA" ${r.type === 'AAAA' ? 'selected' : ''}>AAAA</option>
                    <option value="CNAME" ${r.type === 'CNAME' ? 'selected' : ''}>CNAME</option>
                </select>
            </td>
            <td>
                <button class="btn btn-success" onclick="saveLocalDnsInline(${index})">Save</button>
                <button class="btn btn-secondary" onclick="renderLocalDnsRecords()">Cancel</button>
            </td>
        `;
    }

    saveLocalDnsInline(index) {
        const domain = document.getElementById(`edit-dns-domain-${index}`).value.trim();
        const ip = document.getElementById(`edit-dns-ip-${index}`).value.trim();
        const type = document.getElementById(`edit-dns-type-${index}`).value;
        
        if (!domain || !ip) {
            alert("Domain Name and IP Address are required.");
            return;
        }
        
        window.localDnsRecords[index] = { domain, ip, type };
        this.renderLocalDnsRecords();
    }

    showAddDnsRecordForm(position) {
        const tableBody = document.getElementById("dns-records-table-body");
        if (!tableBody) return;
        
        const existing = document.getElementById("dns-record-add-row");
        if (existing) existing.remove();
        
        const addRow = document.createElement("tr");
        addRow.id = "dns-record-add-row";
        addRow.innerHTML = `
            <td><input type="text" id="add-dns-domain" placeholder="server.lan" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="add-dns-ip" placeholder="192.168.1.20" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="add-dns-type" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="A">A</option>
                    <option value="AAAA">AAAA</option>
                    <option value="CNAME">CNAME</option>
                </select>
            </td>
            <td>
                <button class="btn btn-success" onclick="saveNewLocalDnsInline()">Save</button>
                <button class="btn btn-secondary" onclick="document.getElementById('dns-record-add-row').remove()">Cancel</button>
            </td>
        `;
        
        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    saveNewLocalDnsInline() {
        const domain = document.getElementById("add-dns-domain").value.trim();
        const ip = document.getElementById("add-dns-ip").value.trim();
        const type = document.getElementById("add-dns-type").value;
        
        if (!domain || !ip) {
            alert("All fields are required.");
            return;
        }
        
        window.localDnsRecords.push({ domain, ip, type });
        this.renderLocalDnsRecords();
    }

    deleteLocalDnsRecord(index) {
        if (confirm("Remove this local DNS record?")) {
            window.localDnsRecords.splice(index, 1);
            this.renderLocalDnsRecords();
        }
    }
}

window.firewallComponent = new FirewallComponent();
window.parentalComponent = new ParentalComponent();
window.dnsComponent = new DnsComponent();
