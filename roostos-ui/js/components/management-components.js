// DHCP Component
const DHCP_TEMPLATE = `
    <div id="dhcp-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('dhcp', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('dhcp', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Active Dynamic DHCP Leases</h2>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>IP Address</th>
                                <th>MAC Address</th>
                                <th>Client Hostname</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="dhcp-active-leases-body">
                            <tr>
                                <td colspan="5" class="empty-state">No active dynamic leases found.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <h2>Static IP Reservations</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddStaticDhcpForm('top')">+ Add Static Reservation</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>MAC Address</th>
                                <th>Friendly Name</th>
                                <th>Static IP Address</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="dhcp-static-reservations-body">
                            <tr>
                                <td colspan="4" class="empty-state">No static reservations configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddStaticDhcpForm('bottom')">+ Add Static Reservation</button>
                </div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>DHCP Server Status</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Optimal dynamic address ranges are auto-configured (.100 to .250 pool ranges).
                </p>
                <div class="metrics-row" style="margin-bottom: 20px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                    <div class="metric-card" style="padding: 16px;">
                        <span class="metric-value" id="dhcp-lease-count">0</span>
                        <span class="metric-label">Active DHCP Leases</span>
                    </div>
                    <div class="metric-card" style="padding: 16px;">
                        <span class="metric-value" id="dhcp-static-count">0</span>
                        <span class="metric-label">Static Allocations</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>DHCP Address Pools & Scopes</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Bind customized DHCP scopes and pool address ranges to your bridges and VLAN subnets.
                </p>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Network / Interface</th>
                                <th>Subnet / Gateway</th>
                                <th>DHCP Service</th>
                                <th>Dynamic Pool Range</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="dhcp-scopes-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">Loading scopes configuration...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
`;

class DhcpComponent {
    constructor() {
        this.template = DHCP_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderDhcpView = () => this.render();
        window.showAddStaticDhcpForm = (pos) => this.showAddStaticDhcpForm(pos);
        window.saveNewStaticDhcpInline = () => this.saveNewStaticDhcpInline();
        window.editStaticDhcpInline = (mac) => this.editStaticDhcpInline(mac);
        window.saveStaticDhcpInline = (mac) => this.saveStaticDhcpInline(mac);
        window.deleteStaticDhcp = (mac) => this.deleteStaticDhcp(mac);
    }

    render() {
        const leasesBody = document.getElementById("dhcp-active-leases-body");
        if (leasesBody) {
            const leases = window.activeLeases || [];
            if (leases.length === 0) {
                leasesBody.innerHTML = '<tr><td colspan="5" class="empty-state">No active dynamic leases found.</td></tr>';
            } else {
                leasesBody.innerHTML = leases.map(l => `
                    <tr>
                        <td><code>${escapeHtml(l.ip)}</code></td>
                        <td><code>${escapeHtml(l.mac.toUpperCase())}</code></td>
                        <td>${escapeHtml(l.hostname || "Unknown")}</td>
                        <td><span class="badge badge-online">ACTIVE</span></td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="showAddStaticDhcpForm('top'); document.getElementById('add-static-mac').value='${l.mac}'; document.getElementById('add-static-ip').value='${l.ip}'; document.getElementById('add-static-name').value='${escapeJs(l.hostname || "")}';">Make Static</button>
                        </td>
                    </tr>
                `).join("");
            }
        }

        const staticBody = document.getElementById("dhcp-static-reservations-body");
        if (staticBody) {
            const statics = (window.allDevices || []).filter(d => d.static_ip);
            if (statics.length === 0) {
                staticBody.innerHTML = '<tr><td colspan="4" class="empty-state">No static reservations configured.</td></tr>';
            } else {
                staticBody.innerHTML = statics.map(s => `
                    <tr id="static-dhcp-row-${s.mac}">
                        <td><code>${escapeHtml(s.mac.toUpperCase())}</code></td>
                        <td><strong>${escapeHtml(s.name)}</strong></td>
                        <td><code>${escapeHtml(s.static_ip)}</code></td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="editStaticDhcpInline('${s.mac}')">Edit</button>
                            <button class="btn btn-danger btn-sm" onclick="deleteStaticDhcp('${s.mac}')">Delete</button>
                        </td>
                    </tr>
                `).join("");
            }
        }

        const leaseCountEl = document.getElementById("dhcp-lease-count");
        if (leaseCountEl) leaseCountEl.textContent = (window.activeLeases || []).length;

        const staticCountEl = document.getElementById("dhcp-static-count");
        if (staticCountEl) staticCountEl.textContent = (window.allDevices || []).filter(d => d.static_ip).length;

        const scopesBody = document.getElementById("dhcp-scopes-table-body");
        if (scopesBody && window.networkSettings) {
            const bridges = window.networkSettings.bridges || [];
            const vlans = window.networkSettings.vlans || [];
            const scopes = [...bridges.map(b => ({ name: b.name, ip: b.ip, type: 'Bridge' })), ...vlans.map(v => ({ name: v.name, ip: v.ip, type: 'VLAN' }))];

            if (scopes.length === 0) {
                scopesBody.innerHTML = '<tr><td colspan="5" class="empty-state">No interfaces to assign DHCP scopes.</td></tr>';
            } else {
                scopesBody.innerHTML = scopes.map(s => {
                    const prefix = s.ip.substring(0, s.ip.lastIndexOf('.'));
                    return `
                        <tr>
                            <td><strong>${escapeHtml(s.name)} (${s.type})</strong></td>
                            <td><code>${escapeHtml(s.ip)}</code></td>
                            <td><span class="badge badge-online">ENABLED</span></td>
                            <td><code>${prefix}.100 - ${prefix}.250</code></td>
                            <td><button class="btn btn-secondary btn-sm" disabled>Configure Scope</button></td>
                        </tr>
                    `;
                }).join("");
            }
        }
    }

    showAddStaticDhcpForm(position) {
        const tableBody = document.getElementById("dhcp-static-reservations-body");
        if (!tableBody) return;
        const existing = document.getElementById("static-dhcp-add-row");
        if (existing) existing.remove();

        const addRow = document.createElement("tr");
        addRow.id = "static-dhcp-add-row";
        addRow.innerHTML = `
            <td><input type="text" id="add-static-mac" placeholder="aa:bb:cc:dd:ee:ff" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="add-static-name" placeholder="Desktop-PC" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="add-static-ip" placeholder="192.168.1.50" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveNewStaticDhcpInline()">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('static-dhcp-add-row').remove()">Cancel</button>
            </td>
        `;

        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    async saveNewStaticDhcpInline() {
        const mac = document.getElementById("add-static-mac").value.trim();
        const name = document.getElementById("add-static-name").value.trim();
        const ip = document.getElementById("add-static-ip").value.trim();

        if (!mac || !name || !ip) {
            alert("All fields are required.");
            return;
        }

        try {
            const res = await window.deviceService.saveDevice({
                mac, name, static_ip: ip, upnp_trusted: false, tags: [], owner: "", location: ""
            });
            if (res.ok) {
                document.getElementById('static-dhcp-add-row').remove();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save static reservation.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    editStaticDhcpInline(mac) {
        const row = document.getElementById(`static-dhcp-row-${mac}`);
        if (!row) return;
        const dev = window.allDevices.find(d => d.mac === mac);
        if (!dev) return;

        row.innerHTML = `
            <td><code>${escapeHtml(mac.toUpperCase())}</code></td>
            <td><input type="text" id="edit-static-name-${mac}" value="${escapeHtml(dev.name)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="edit-static-ip-${mac}" value="${escapeHtml(dev.static_ip)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveStaticDhcpInline('${mac}')">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="renderDhcpView()">Cancel</button>
            </td>
        `;
    }

    async saveStaticDhcpInline(mac) {
        const name = document.getElementById(`edit-static-name-${mac}`).value.trim();
        const ip = document.getElementById(`edit-static-ip-${mac}`).value.trim();

        if (!name || !ip) {
            alert("All fields are required.");
            return;
        }

        try {
            const dev = window.allDevices.find(d => d.mac === mac) || {};
            const res = await window.deviceService.saveDevice({
                ...dev, mac, name, static_ip: ip
            });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save static reservation.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deleteStaticDhcp(mac) {
        if (confirm("Remove this static reservation?")) {
            try {
                const dev = window.allDevices.find(d => d.mac === mac);
                if (dev) {
                    const res = await window.deviceService.saveDevice({
                        ...dev, static_ip: null
                    });
                    if (res.ok) {
                        if (window.loadDashboard) window.loadDashboard();
                    } else {
                        alert("Failed to delete static reservation.");
                    }
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }
}

// VPN Component
const VPN_TEMPLATE = `
    <div id="vpn-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('vpn', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('vpn', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>VPN Connections</h2>
                <div class="device-table-container" style="margin-bottom: 24px;">
                    <table>
                        <thead>
                            <tr>
                                <th>Profile Name</th>
                                <th>Protocol</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="vpns-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">No VPN tunnels configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Add VPN Profile</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 16px;">
                    <button id="add-vpn-btn" class="btn btn-primary" onclick="showAddVpnForm()">+ Add VPN Profile</button>
                </div>

                <div id="vpn-add-container" style="display: none; border-top: 1px solid var(--card-border); padding-top: 20px;">
                    <h3>Add VPN Profile Details</h3>
                    <form id="vpn-add-form" onsubmit="addVpnProfile(event)">
                        <div class="form-row-multi">
                            <div class="form-group" style="flex: 1;">
                                <label>Tunnel ID (Unique)</label>
                                <input type="text" id="vpn-id" placeholder="wg_client_eu" required>
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label>Profile Name</label>
                                <input type="text" id="vpn-name" placeholder="Europe WireGuard Client" required>
                            </div>
                        </div>
                        <div class="form-row-multi">
                            <div class="form-group" style="flex: 1;">
                                <label>VPN Protocol</label>
                                <select id="vpn-type" onchange="updateVpnProtocolFields()">
                                    <!-- Dynamically populated -->
                                </select>
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label>Tunnelling Role</label>
                                <select id="vpn-role">
                                    <option value="client">Client (Tunnel router traffic outbound)</option>
                                    <option value="server">Server (Accept incoming peer connections)</option>
                                </select>
                            </div>
                        </div>
                        <div id="vpn-protocol-fields" style="margin-top: 15px; margin-bottom: 15px;"></div>
                        <button type="submit" class="btn btn-success">Add VPN Tunnel</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
`;

class VpnComponent {
    constructor() {
        this.template = VPN_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderVPNView = () => this.render();
        window.showAddVpnForm = () => this.showAddVpnForm();
        window.updateVpnProtocolFields = () => this.updateVpnProtocolFields();
        window.addVpnProfile = (e) => this.addVpnProfile(e);
        window.toggleVpnEnabled = (id) => this.toggleVpnEnabled(id);
        window.deleteVpnProfile = (id) => this.deleteVpnProfile(id);
    }

    render() {
        const tableBody = document.getElementById("vpns-table-body");
        if (!tableBody) return;
        const vpns = window.vpnSettings || [];

        if (vpns.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No VPN tunnels configured.</td></tr>';
        } else {
            tableBody.innerHTML = vpns.map(v => `
                <tr id="vpn-row-${v.id}">
                    <td><strong>${escapeHtml(v.name)}</strong></td>
                    <td><code>${escapeHtml(v.type.toUpperCase())}</code></td>
                    <td>${escapeHtml(v.role.toUpperCase())}</td>
                    <td><span class="badge ${v.enabled ? 'badge-online' : 'badge-offline'}">${v.enabled ? 'ENABLED' : 'DISABLED'}</span></td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="toggleVpnEnabled('${escapeJs(v.id)}')">${v.enabled ? 'Disable' : 'Enable'}</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteVpnProfile('${escapeJs(v.id)}')">Delete</button>
                    </td>
                </tr>
            `).join("");
        }

        // Populate VPN Type Options
        const typeSelect = document.getElementById("vpn-type");
        if (typeSelect && window.RoostOS) {
            const types = window.RoostOS.getVpnTypes() || [];
            typeSelect.innerHTML = types.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t.toUpperCase())}</option>`).join("");
            this.updateVpnProtocolFields();
        }
    }

    showAddVpnForm() {
        const container = document.getElementById("vpn-add-container");
        const btn = document.getElementById("add-vpn-btn");
        if (container.style.display === "none") {
            container.style.display = "block";
            btn.textContent = "Cancel";
            btn.classList.replace("btn-primary", "btn-secondary");
            this.updateVpnProtocolFields();
        } else {
            container.style.display = "none";
            btn.textContent = "+ Add VPN Profile";
            btn.classList.replace("btn-secondary", "btn-primary");
        }
    }

    updateVpnProtocolFields() {
        const typeSelect = document.getElementById("vpn-type");
        if (!typeSelect) return;
        const type = typeSelect.value;
        const container = document.getElementById("vpn-protocol-fields");
        if (!container) return;

        if (window.RoostOS) {
            const handler = window.RoostOS.getVpnFormHandler(type);
            if (handler) {
                handler.renderConfigFields(container, {});
            } else {
                container.innerHTML = `<p style="font-size: 13px; color: var(--text-secondary);">No configuration fields registered for type: ${type}</p>`;
            }
        }
    }

    async addVpnProfile(e) {
        e.preventDefault();
        const id = document.getElementById("vpn-id").value.trim();
        const name = document.getElementById("vpn-name").value.trim();
        const type = document.getElementById("vpn-type").value;
        const role = document.getElementById("vpn-role").value;

        let config = {};
        if (window.RoostOS) {
            const handler = window.RoostOS.getVpnFormHandler(type);
            if (handler) {
                try {
                    config = handler.readConfigForm(document.getElementById("vpn-protocol-fields"));
                } catch (err) {
                    alert(err.message);
                    return;
                }
            }
        }

        const newProfile = { id, name, type, role, enabled: true, config };
        window.vpnSettings.push(newProfile);

        try {
            const res = await window.networkService.saveConfig(window.networkSettings, window.wifiSettings, window.vpnSettings);
            if (res.ok) {
                alert("VPN profile added successfully!");
                document.getElementById("vpn-add-form").reset();
                this.showAddVpnForm();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to add VPN profile.");
                window.vpnSettings.pop();
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
            window.vpnSettings.pop();
        }
    }

    async toggleVpnEnabled(id) {
        const profile = window.vpnSettings.find(v => v.id === id);
        if (profile) {
            profile.enabled = !profile.enabled;
            try {
                const res = await window.networkService.saveConfig(window.networkSettings, window.wifiSettings, window.vpnSettings);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to update VPN profile status.");
                    profile.enabled = !profile.enabled;
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
                profile.enabled = !profile.enabled;
            }
        }
    }

    async deleteVpnProfile(id) {
        if (confirm(`Delete VPN profile "${id}"?`)) {
            const filtered = window.vpnSettings.filter(v => v.id !== id);
            try {
                const res = await window.networkService.saveConfig(window.networkSettings, window.wifiSettings, filtered);
                if (res.ok) {
                    window.vpnSettings = filtered;
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete VPN profile.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }
}

// People Component
const PEOPLE_TEMPLATE = `
    <div id="people-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('people', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('people', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Family Profiles (People)</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddPersonForm('top')">+ Add Person</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Person ID</th>
                                <th>Display Name</th>
                                <th>DNS Filter Profile</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="people-table-body">
                            <tr>
                                <td colspan="4" class="empty-state">No family member profiles configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddPersonForm('bottom')">+ Add Person</button>
                </div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Operator Users</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Configure access controls and web console administrative accounts.
                </p>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddUserForm('top')">+ Add User Account</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Username</th>
                                <th>Console Access Role</th>
                                <th>Linked Family Profile</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="users-table-body">
                            <tr>
                                <td colspan="4" class="empty-state">No operator user accounts configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddUserForm('bottom')">+ Add User Account</button>
                </div>
            </div>
        </div>
    </div>
`;

class PeopleComponent {
    constructor() {
        this.template = PEOPLE_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderPeopleView = () => this.render();
        window.showAddPersonForm = (pos) => this.showAddPersonForm(pos);
        window.saveNewPersonInline = () => this.saveNewPersonInline();
        window.editPersonInline = (id) => this.editPersonInline(id);
        window.savePersonInline = (id) => this.savePersonInline(id);
        window.deletePerson = (id) => this.deletePerson(id);

        window.renderUsersList = (u) => this.renderUsersList(u);
        window.showAddUserForm = (pos) => this.showAddUserForm(pos);
        window.saveNewUserInline = () => this.saveNewUserInline();
        window.editUserInline = (u) => this.editUserInline(u);
        window.saveUserInline = (u) => this.saveUserInline(u);
        window.deleteUser = (u) => this.deleteUser(u);
    }

    render(people = []) {
        const tableBody = document.getElementById("people-table-body");
        if (!tableBody) return;

        if (people.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No family member profiles configured.</td></tr>';
            return;
        }

        tableBody.innerHTML = people.map(p => `
            <tr id="person-row-${p.id}">
                <td><code>${escapeHtml(p.id)}</code></td>
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td><span class="badge badge-outline">${escapeHtml(p.dns_profile || "Default")}</span></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editPersonInline('${escapeJs(p.id)}')">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deletePerson('${escapeJs(p.id)}')">Delete</button>
                </td>
            </tr>
        `).join("");
    }

    showAddPersonForm(position) {
        const tableBody = document.getElementById("people-table-body");
        if (!tableBody) return;
        const existing = document.getElementById("person-add-row");
        if (existing) existing.remove();

        const addRow = document.createElement("tr");
        addRow.id = "person-add-row";
        addRow.innerHTML = `
            <td><input type="text" id="add-person-id" placeholder="mom" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="add-person-name" placeholder="Mom" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="add-person-dns" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="default">Default</option>
                    <option value="child-safe">Child Safe Filters</option>
                    <option value="work-focused">Work Focus Mode</option>
                </select>
            </td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveNewPersonInline()">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('person-add-row').remove()">Cancel</button>
            </td>
        `;

        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    async saveNewPersonInline() {
        const id = document.getElementById("add-person-id").value.trim();
        const name = document.getElementById("add-person-name").value.trim();
        const dns_profile = document.getElementById("add-person-dns").value;

        if (!id || !name) {
            alert("All fields are required.");
            return;
        }

        try {
            const res = await window.systemService.savePerson({ id, name, dns_profile });
            if (res.ok) {
                document.getElementById('person-add-row').remove();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to add person profile.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    editPersonInline(id) {
        const row = document.getElementById(`person-row-${id}`);
        if (!row) return;
        const p = window.allOwners.find(o => o.id === id);
        if (!p) return;

        row.innerHTML = `
            <td><code>${escapeHtml(id)}</code></td>
            <td><input type="text" id="edit-person-name-${id}" value="${escapeHtml(p.name)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="edit-person-dns-${id}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="default" ${p.dns_profile === 'default' ? 'selected' : ''}>Default</option>
                    <option value="child-safe" ${p.dns_profile === 'child-safe' ? 'selected' : ''}>Child Safe Filters</option>
                    <option value="work-focused" ${p.dns_profile === 'work-focused' ? 'selected' : ''}>Work Focus Mode</option>
                </select>
            </td>
            <td>
                <button class="btn btn-success btn-sm" onclick="savePersonInline('${id}')">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="window.peopleComponent.render(window.allOwners)">Cancel</button>
            </td>
        `;
    }

    async savePersonInline(id) {
        const name = document.getElementById(`edit-person-name-${id}`).value.trim();
        const dns_profile = document.getElementById(`edit-person-dns-${id}`).value;

        if (!name) {
            alert("Name is required.");
            return;
        }

        try {
            const res = await window.systemService.savePerson({ id, name, dns_profile });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save person profile.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deletePerson(id) {
        if (confirm("Remove this family profile?")) {
            try {
                const res = await window.systemService.deletePerson(id);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete person.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }

    renderUsersList(users = []) {
        const tableBody = document.getElementById("users-table-body");
        if (!tableBody) return;

        if (users.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No operator user accounts configured.</td></tr>';
            return;
        }

        tableBody.innerHTML = users.map(u => `
            <tr id="user-row-${u.username}">
                <td><strong>${escapeHtml(u.username)}</strong></td>
                <td><span class="badge ${u.role === 'admin' ? 'badge-online' : 'badge-offline'}">${escapeHtml(u.role.toUpperCase())}</span></td>
                <td>${escapeHtml(u.person || "None Linked")}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editUserInline('${escapeJs(u.username)}')">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteUser('${escapeJs(u.username)}')">Delete</button>
                </td>
            </tr>
        `).join("");
    }

    showAddUserForm(position) {
        const tableBody = document.getElementById("users-table-body");
        if (!tableBody) return;
        const existing = document.getElementById("user-add-row");
        if (existing) existing.remove();

        const addRow = document.createElement("tr");
        addRow.id = "user-add-row";
        addRow.innerHTML = `
            <td><input type="text" id="add-user-username" placeholder="admin" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="add-user-role" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                </select>
            </td>
            <td>
                <select id="add-user-person" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="">None</option>
                    ${window.allOwners.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`).join("")}
                </select>
            </td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveNewUserInline()">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('user-add-row').remove()">Cancel</button>
            </td>
        `;

        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    async saveNewUserInline() {
        const username = document.getElementById("add-user-username").value.trim();
        const role = document.getElementById("add-user-role").value;
        const person = document.getElementById("add-user-person").value || null;

        if (!username) {
            alert("Username is required.");
            return;
        }

        try {
            const res = await window.securityService.saveUser({ username, role, person });
            if (res.ok) {
                document.getElementById('user-add-row').remove();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to add user account.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    editUserInline(username) {
        const row = document.getElementById(`user-row-${username}`);
        if (!row) return;
        const u = allUsers.find(user => user.username === username);
        if (!u) return;

        row.innerHTML = `
            <td><strong>${escapeHtml(username)}</strong></td>
            <td>
                <select id="edit-user-role-${username}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
                    <option value="member" ${u.role === 'member' ? 'selected' : ''}>Member</option>
                </select>
            </td>
            <td>
                <select id="edit-user-person-${username}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    <option value="">None</option>
                    ${window.allOwners.map(p => `<option value="${escapeHtml(p.id)}" ${p.id === u.person ? 'selected' : ''}>${escapeHtml(p.name)}</option>`).join("")}
                </select>
            </td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveUserInline('${username}')">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="window.peopleComponent.renderUsersList(allUsers)">Cancel</button>
            </td>
        `;
    }

    async saveUserInline(username) {
        const role = document.getElementById(`edit-user-role-${username}`).value;
        const person = document.getElementById(`edit-user-person-${username}`).value || null;

        try {
            const res = await window.securityService.saveUser({ username, role, person });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save user account.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deleteUser(username) {
        if (confirm(`Remove operator user account "${username}"?`)) {
            try {
                const res = await window.securityService.deleteUser(username);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete user account.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }
}

// Locations Component
const LOCATIONS_TEMPLATE = `
    <div id="locations-view" class="view-pane">
        <div class="card-grid">
            <div class="card">
                <h2>Buildings & Structures</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddBuildingForm('top')">+ Add Building</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Building ID</th>
                                <th>Friendly Name</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="buildings-table-body">
                            <tr>
                                <td colspan="3" class="empty-state">No buildings configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddBuildingForm('bottom')">+ Add Building</button>
                </div>
            </div>

            <div class="card">
                <h2>Rooms & Areas</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddRoomForm('top')">+ Add Room</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Room ID</th>
                                <th>Room Name</th>
                                <th>Building</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="rooms-table-body">
                            <tr>
                                <td colspan="4" class="empty-state">No rooms configured.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddRoomForm('bottom')">+ Add Room</button>
                </div>
            </div>
        </div>
    </div>
`;

class LocationsComponent {
    constructor() {
        this.template = LOCATIONS_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderLocationsView = () => this.render();
        window.showAddBuildingForm = (pos) => this.showAddBuildingForm(pos);
        window.saveNewBuildingInline = () => this.saveNewBuildingInline();
        window.editBuildingInline = (id) => this.editBuildingInline(id);
        window.saveBuildingInline = (id) => this.saveBuildingInline(id);
        window.deleteBuilding = (id) => this.deleteBuilding(id);

        window.showAddRoomForm = (pos) => this.showAddRoomForm(pos);
        window.saveNewRoomInline = () => this.saveNewRoomInline();
        window.editRoomInline = (id) => this.editRoomInline(id);
        window.saveRoomInline = (id) => this.saveRoomInline(id);
        window.deleteRoom = (id) => this.deleteRoom(id);
    }

    render(buildings = [], rooms = []) {
        this.renderBuildings(buildings);
        this.renderRooms(rooms, buildings);
    }

    renderBuildings(buildings = []) {
        const tableBody = document.getElementById("buildings-table-body");
        if (!tableBody) return;

        if (buildings.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="3" class="empty-state">No buildings configured.</td></tr>';
            return;
        }

        tableBody.innerHTML = buildings.map(b => `
            <tr id="building-row-${b.id}">
                <td><code>${escapeHtml(b.id)}</code></td>
                <td><strong>${escapeHtml(b.name)}</strong></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editBuildingInline('${escapeJs(b.id)}')">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteBuilding('${escapeJs(b.id)}')">Delete</button>
                </td>
            </tr>
        `).join("");
    }

    showAddBuildingForm(position) {
        const tableBody = document.getElementById("buildings-table-body");
        if (!tableBody) return;
        const existing = document.getElementById("building-add-row");
        if (existing) existing.remove();

        const addRow = document.createElement("tr");
        addRow.id = "building-add-row";
        addRow.innerHTML = `
            <td><input type="text" id="add-building-id" placeholder="main-house" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="add-building-name" placeholder="Main House" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveNewBuildingInline()">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('building-add-row').remove()">Cancel</button>
            </td>
        `;

        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    async saveNewBuildingInline() {
        const id = document.getElementById("add-building-id").value.trim();
        const name = document.getElementById("add-building-name").value.trim();

        if (!id || !name) {
            alert("All fields are required.");
            return;
        }

        try {
            const res = await window.systemService.saveBuilding({ id, name });
            if (res.ok) {
                document.getElementById('building-add-row').remove();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to add building.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    editBuildingInline(id) {
        const row = document.getElementById(`building-row-${id}`);
        if (!row) return;
        const b = window.allBuildingsList.find(item => item.id === id);
        if (!b) return;

        row.innerHTML = `
            <td><code>${escapeHtml(id)}</code></td>
            <td><input type="text" id="edit-building-name-${id}" value="${escapeHtml(b.name)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveBuildingInline('${id}')">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="window.locationsComponent.renderBuildings(window.allBuildingsList)">Cancel</button>
            </td>
        `;
    }

    async saveBuildingInline(id) {
        const name = document.getElementById(`edit-building-name-${id}`).value.trim();

        if (!name) {
            alert("Name is required.");
            return;
        }

        try {
            const res = await window.systemService.saveBuilding({ id, name });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save building.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deleteBuilding(id) {
        if (confirm("Remove this building and structure profile?")) {
            try {
                const res = await window.systemService.deleteBuilding(id);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete building.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }

    renderRooms(rooms = [], buildings = []) {
        const tableBody = document.getElementById("rooms-table-body");
        if (!tableBody) return;

        if (rooms.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No rooms configured.</td></tr>';
            return;
        }

        tableBody.innerHTML = rooms.map(r => {
            const b = buildings.find(item => item.id === r.building_id);
            const bName = b ? b.name : r.building_id;
            return `
                <tr id="room-row-${r.id}">
                    <td><code>${escapeHtml(r.id)}</code></td>
                    <td><strong>${escapeHtml(r.name)}</strong></td>
                    <td>${escapeHtml(bName)}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="editRoomInline('${escapeJs(r.id)}')">Edit</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteRoom('${escapeJs(r.id)}')">Delete</button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    showAddRoomForm(position) {
        const tableBody = document.getElementById("rooms-table-body");
        if (!tableBody) return;
        const existing = document.getElementById("room-add-row");
        if (existing) existing.remove();

        const addRow = document.createElement("tr");
        addRow.id = "room-add-row";
        addRow.innerHTML = `
            <td><input type="text" id="add-room-id" placeholder="living-room" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td><input type="text" id="add-room-name" placeholder="Living Room" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="add-room-building" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    ${window.allBuildingsList.map(b => `<option value="${escapeHtml(b.id)}">${escapeHtml(b.name)}</option>`).join("")}
                </select>
            </td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveNewRoomInline()">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('room-add-row').remove()">Cancel</button>
            </td>
        `;

        if (position === "top") {
            tableBody.insertBefore(addRow, tableBody.firstChild);
        } else {
            tableBody.appendChild(addRow);
        }
    }

    async saveNewRoomInline() {
        const id = document.getElementById("add-room-id").value.trim();
        const name = document.getElementById("add-room-name").value.trim();
        const building_id = document.getElementById("add-room-building").value;

        if (!id || !name || !building_id) {
            alert("All fields are required.");
            return;
        }

        try {
            const res = await window.systemService.saveRoom({ id, name, building_id });
            if (res.ok) {
                document.getElementById('room-add-row').remove();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to add room.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    editRoomInline(id) {
        const row = document.getElementById(`room-row-${id}`);
        if (!row) return;
        const r = window.allLocations.find(item => item.id === id);
        if (!r) return;

        row.innerHTML = `
            <td><code>${escapeHtml(id)}</code></td>
            <td><input type="text" id="edit-room-name-${id}" value="${escapeHtml(r.name)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
            <td>
                <select id="edit-room-building-${id}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                    ${window.allBuildingsList.map(b => `<option value="${escapeHtml(b.id)}" ${b.id === r.building_id ? 'selected' : ''}>${escapeHtml(b.name)}</option>`).join("")}
                </select>
            </td>
            <td>
                <button class="btn btn-success btn-sm" onclick="saveRoomInline('${id}')">Save</button>
                <button class="btn btn-secondary btn-sm" onclick="window.locationsComponent.renderRooms(window.allLocations, window.allBuildingsList)">Cancel</button>
            </td>
        `;
    }

    async saveRoomInline(id) {
        const name = document.getElementById(`edit-room-name-${id}`).value.trim();
        const building_id = document.getElementById(`edit-room-building-${id}`).value;

        if (!name || !building_id) {
            alert("All fields are required.");
            return;
        }

        try {
            const res = await window.systemService.saveRoom({ id, name, building_id });
            if (res.ok) {
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save room.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deleteRoom(id) {
        if (confirm("Remove this room area?")) {
            try {
                const res = await window.systemService.deleteRoom(id);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete room.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }
}

// System Component
const SYSTEM_TEMPLATE = `
    <div id="system-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('system', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('system', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Global Router Configuration</h2>
                <form id="system-config-form">
                    <div class="form-row-multi">
                        <div class="form-group" style="flex: 1;">
                            <label>Hostname</label>
                            <input type="text" id="sys-hostname" placeholder="roost-router" required>
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label>Local Domain</label>
                            <input type="text" id="sys-domain" placeholder="lan" required>
                        </div>
                    </div>
                    <div class="form-group" style="margin-top: 16px;">
                        <label>Local Docker Registry (Optional)</label>
                        <input type="text" id="sys-registry" placeholder="e.g. localhost:5000">
                    </div>
                    <button type="submit" class="btn btn-primary" style="margin-top: 16px;">Apply Settings</button>
                </form>
            </div>

            <div class="card">
                <h2>System Controls & Updates</h2>
                <div class="stat-item">
                    <span class="stat-label">Software Version:</span>
                    <span class="stat-value">RoostOS Core v0.1.0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Update Channel:</span>
                    <span class="stat-value">Stable Release</span>
                </div>
                
                <div style="margin-top: 24px; display: flex; gap: 12px;">
                    <button id="reboot-btn" class="btn btn-danger" style="flex: 1;" onclick="rebootRouter()">Reboot Router</button>
                    <button id="check-updates-btn" class="btn btn-secondary" style="flex: 1;" onclick="alert('System software is up to date!')">Check Updates</button>
                </div>
            </div>

            <div class="card" id="system-health-card">
                <h2>System Health & Diagnostics</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Run diagnostic checks to verify routing, firewall, and daemon integrity.
                </p>
                <button id="run-health-btn" class="btn btn-secondary" onclick="runSystemHealthCheck()">Run Diagnostics</button>
                <div id="health-results" style="margin-top: 16px; display: none;"></div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Configuration Backup & Restore</h2>
                <form id="backup-form">
                    <div class="form-group">
                        <label>Passphrase (used to encrypt backup)</label>
                        <input type="password" id="backup-passphrase" placeholder="••••••••" required>
                    </div>
                    <button type="submit" class="btn btn-success">Download Backup</button>
                </form>
                
                <hr style="margin: 20px 0; border: none; border-top: 1px solid var(--card-border);">
                
                <form id="restore-form">
                    <div class="form-group">
                        <label>Restore Archive Server Path</label>
                        <input type="text" id="restore-path" placeholder="/tmp/backups/backup.tar.gpg" required>
                    </div>
                    <div class="form-group">
                        <label>Passphrase</label>
                        <input type="password" id="restore-passphrase" placeholder="••••••••" required>
                    </div>
                    <button type="submit" class="btn btn-danger">Restore Configuration</button>
                </form>
            </div>
        </div>
    </div>
`;

class SystemComponent {
    constructor() {
        this.template = SYSTEM_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderSystemView = () => this.render();
        window.rebootRouter = () => this.rebootRouter();
        window.runSystemHealthCheck = () => this.runSystemHealthCheck();
    }

    render(sysData) {
        if (!sysData) return;
        const hostEl = document.getElementById("sys-hostname");
        if (hostEl) hostEl.value = sysData.hostname || "";
        const domEl = document.getElementById("sys-domain");
        if (domEl) domEl.value = sysData.domain || "";
        const regEl = document.getElementById("sys-registry");
        if (regEl) regEl.value = sysData.docker_registry || "";

        this.setupForms();
    }

    setupForms() {
        const sysForm = document.getElementById("system-config-form");
        if (sysForm && !sysForm.dataset.bound) {
            sysForm.dataset.bound = "true";
            sysForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const hostname = document.getElementById("sys-hostname").value.trim();
                const domain = document.getElementById("sys-domain").value.trim();
                const docker_registry = document.getElementById("sys-registry").value.trim() || null;
                
                try {
                    const res = await window.systemService.saveSystemSettings({ hostname, domain, timezone: "UTC", docker_registry });
                    if (res.ok) {
                        alert("System configurations applied successfully!");
                        if (window.loadDashboard) window.loadDashboard();
                    } else {
                        alert("Failed to apply settings.");
                    }
                } catch (err) {
                    alert(`Error: ${err.message}`);
                }
            });
        }

        const backupForm = document.getElementById("backup-form");
        if (backupForm && !backupForm.dataset.bound) {
            backupForm.dataset.bound = "true";
            backupForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                const passphrase = document.getElementById("backup-passphrase").value;
                try {
                    const res = await window.systemService.triggerBackup(passphrase);
                    if (res.ok) {
                        const blob = await res.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `roostos_backup_${Date.now()}.tar.gpg`;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        alert("Backup archive downloaded successfully!");
                    } else {
                        alert("Failed to create system backup archive.");
                    }
                } catch (err) {
                    alert(`Error: ${err.message}`);
                }
            });
        }
    }

    async rebootRouter() {
        if (confirm("Are you sure you want to reboot the router?")) {
            try {
                const res = await window.authService.apiFetch("/api/system/reboot", { method: "POST" });
                if (res.ok) {
                    alert("Reboot instruction sent. Router is restarting...");
                } else {
                    alert("Failed to send reboot instruction.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }

    async runSystemHealthCheck() {
        const btn = document.getElementById("run-health-btn");
        const results = document.getElementById("health-results");
        if (!btn || !results) return;

        btn.disabled = true;
        btn.textContent = "Checking...";
        results.style.display = "none";

        try {
            const data = await window.systemService.fetchHealth();
            results.style.display = "block";
            results.innerHTML = `
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid var(--card-border); padding: 16px; border-radius: 8px; font-family: monospace; font-size: 13px;">
                    <div style="margin-bottom: 8px;"><strong>Daemon Status Check:</strong></div>
                    <div style="color: ${data.kea_status === 'active' ? '#10b981' : '#ef4444'}; margin-bottom: 6px;">Kea DHCP: ${data.kea_status.toUpperCase()}</div>
                    <div style="color: ${data.systemd_resolved === 'active' ? '#10b981' : '#ef4444'}; margin-bottom: 6px;">Resolved: ${data.systemd_resolved.toUpperCase()}</div>
                    <div style="color: ${data.dbus_client === 'connected' ? '#10b981' : '#ef4444'}; margin-bottom: 6px;">D-Bus Bus: ${data.dbus_client.toUpperCase()}</div>
                    <div style="color: ${data.iwd_service === 'active' ? '#10b981' : '#ef4444'};">IWD WiFi: ${data.iwd_service.toUpperCase()}</div>
                </div>
            `;
        } catch (err) {
            results.style.display = "block";
            results.innerHTML = `<div style="color: #ef4444;">Failed to run health check: ${err.message}</div>`;
        } finally {
            btn.disabled = false;
            btn.textContent = "Run Diagnostics";
        }
    }
}

// Plugins Component
const PLUGINS_TEMPLATE = `
    <div id="plugins-view" class="view-pane">
        <div class="card">
            <h2>Core Router Services</h2>
            <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                Standard networking and system plugins providing primary router features (DNS, VPN, etc.).
            </p>
            <div class="device-table-container" style="margin-bottom: 24px;">
                <table>
                    <thead>
                        <tr>
                            <th>Plugin ID</th>
                            <th>Friendly Name</th>
                            <th>Network Mode</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="plugins-core-table-body">
                        <tr>
                            <td colspan="5" class="empty-state">No core services currently active.</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <h2 style="margin-top: 24px;">Extra Hosted Applications</h2>
            <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                Additional services hosted inside RoostOS that do not affect core network behavior.
            </p>
            <div class="device-table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Plugin ID</th>
                            <th>Friendly Name</th>
                            <th>Network Mode</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="plugins-extra-table-body">
                        <tr>
                            <td colspan="5" class="empty-state">No extra hosted applications.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <h2>Install Custom Plugin Pod</h2>
            <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                <button id="btn-tab-zip" class="btn btn-primary" onclick="switchPluginInstallTab('zip')">Upload ZIP Package</button>
                <button id="btn-tab-yaml" class="btn btn-secondary" onclick="switchPluginInstallTab('yaml')">Paste YAML Manifest</button>
                <button id="btn-tab-manual" class="btn btn-secondary" onclick="switchPluginInstallTab('manual')">Manual Form Fields</button>
            </div>

            <!-- ZIP Package Form -->
            <form id="plugin-zip-form" onsubmit="installPluginViaZip(event)">
                <div class="form-group" style="margin-bottom: 20px;">
                    <label>Select Plugin ZIP Package (.zip)</label>
                    <input type="file" id="plug-zip-file" accept=".zip" required style="display: block; margin-top: 8px;">
                    <span style="font-size: 11px; color: var(--text-secondary);">Archive must contain roostos-pod.yaml and optionally ui.js.</span>
                </div>
                <button type="submit" class="btn btn-success">Upload and Install ZIP</button>
            </form>

            <!-- YAML Manifest Form -->
            <form id="plugin-manifest-form" onsubmit="installPluginViaManifest(event)" style="display: none;">
                <div class="form-group" style="margin-bottom: 20px;">
                    <label>roostos-pod.yaml Manifest Content</label>
                    <textarea id="plug-yaml" placeholder="id: my-plugin&#10;name: My Plugin&#10;network_mode: bridge&#10;ui_entrypoint: /app/ui/ui.js&#10;containers:&#10;  - name: my-container&#10;    image: my-image:latest" required style="width: 100%; height: 200px; font-family: monospace; padding: 12px; border: 1px solid var(--card-border); border-radius: 8px; background: rgba(0,0,0,0.02); color: var(--text-primary); outline: none;"></textarea>
                </div>
                <button type="submit" class="btn btn-success">Upload and Install Manifest</button>
            </form>

            <!-- Manual Form -->
            <form id="plugin-install-form" onsubmit="installCustomPlugin(event)" style="display: none;">
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1;">
                        <label>Plugin ID (Unique Name)</label>
                        <input type="text" id="plug-id" placeholder="technitium-dns">
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Display Name</label>
                        <input type="text" id="plug-name" placeholder="Technitium DNS Resolver">
                    </div>
                </div>
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 2;">
                        <label>Primary Container Docker Image</label>
                        <input type="text" id="plug-image" placeholder="technitium/dns-server:latest">
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Network Mode</label>
                        <select id="plug-netmode">
                            <option value="bridge">Bridge Network</option>
                            <option value="host">Host Network</option>
                        </select>
                    </div>
                </div>
                <div class="form-row-multi" style="margin-bottom: 20px;">
                    <div class="form-group" style="flex: 1;">
                        <label>UI Script Entrypoint Path (Optional)</label>
                        <input type="text" id="plug-ui-entrypoint" placeholder="e.g. /app/ui/ui.js">
                        <span style="font-size: 11px; color: var(--text-secondary);">Extracts and serves compiled dynamic JS from container filesystem.</span>
                    </div>
                </div>
                <button type="submit" class="btn btn-success">Install and Pull Image</button>
            </form>
        </div>
    </div>
`;

class PluginsComponent {
    constructor() {
        this.template = PLUGINS_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderPluginsView = () => this.render();
        window.switchPluginInstallTab = (t) => this.switchPluginInstallTab(t);
        window.installPluginViaZip = (e) => this.installPluginViaZip(e);
        window.installPluginViaManifest = (e) => this.installPluginViaManifest(e);
        window.installCustomPlugin = (e) => this.installCustomPlugin(e);
        window.deletePlugin = (id) => this.deletePlugin(id);
    }

    render(plugins = []) {
        const coreBody = document.getElementById("plugins-core-table-body");
        const extraBody = document.getElementById("plugins-extra-table-body");
        if (!coreBody || !extraBody) return;

        const coreList = plugins.filter(p => p.core);
        const extraList = plugins.filter(p => !p.core);

        if (coreList.length === 0) {
            coreBody.innerHTML = '<tr><td colspan="5" class="empty-state">No core services active.</td></tr>';
        } else {
            coreBody.innerHTML = coreList.map(p => this.getPluginRowHtml(p)).join("");
        }

        if (extraList.length === 0) {
            extraBody.innerHTML = '<tr><td colspan="5" class="empty-state">No extra hosted applications.</td></tr>';
        } else {
            extraBody.innerHTML = extraList.map(p => this.getPluginRowHtml(p)).join("");
        }
    }

    getPluginRowHtml(p) {
        return `
            <tr>
                <td><strong>${escapeHtml(p.id)}</strong></td>
                <td>${escapeHtml(p.name)}</td>
                <td><code>${escapeHtml(p.network_mode)}</code></td>
                <td><span class="badge badge-online">ACTIVE</span></td>
                <td>
                    <button class="btn btn-danger btn-sm" onclick="deletePlugin('${escapeJs(p.id)}')">Delete</button>
                </td>
            </tr>
        `;
    }

    switchPluginInstallTab(tab) {
        const zipForm = document.getElementById("plugin-zip-form");
        const yamlForm = document.getElementById("plugin-manifest-form");
        const manualForm = document.getElementById("plugin-install-form");
        const btnZip = document.getElementById("btn-tab-zip");
        const btnYaml = document.getElementById("btn-tab-yaml");
        const btnManual = document.getElementById("btn-tab-manual");

        if (zipForm && yamlForm && manualForm) {
            zipForm.style.display = tab === 'zip' ? 'block' : 'none';
            yamlForm.style.display = tab === 'yaml' ? 'block' : 'none';
            manualForm.style.display = tab === 'manual' ? 'block' : 'none';

            btnZip.className = `btn ${tab === 'zip' ? 'btn-primary' : 'btn-secondary'}`;
            btnYaml.className = `btn ${tab === 'yaml' ? 'btn-primary' : 'btn-secondary'}`;
            btnManual.className = `btn ${tab === 'manual' ? 'btn-primary' : 'btn-secondary'}`;
        }
    }

    async installPluginViaZip(e) {
        e.preventDefault();
        const fileInput = document.getElementById("plug-zip-file");
        if (!fileInput || fileInput.files.length === 0) return;

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await window.systemService.uploadPlugin(formData);
            if (res.ok) {
                alert("Plugin package uploaded and installed successfully!");
                fileInput.value = "";
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to install plugin ZIP package.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async installPluginViaManifest(e) {
        e.preventDefault();
        const yamlText = document.getElementById("plug-yaml").value;

        try {
            const res = await window.systemService.updatePluginManifest("custom-yaml", yamlText);
            if (res.ok) {
                alert("Plugin manifest applied successfully!");
                document.getElementById("plug-yaml").value = "";
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to apply plugin manifest.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async installCustomPlugin(e) {
        e.preventDefault();
        const id = document.getElementById("plug-id").value.trim();
        const name = document.getElementById("plug-name").value.trim();
        const image = document.getElementById("plug-image").value.trim();
        const network_mode = document.getElementById("plug-netmode").value;
        const ui_entrypoint = document.getElementById("plug-ui-entrypoint").value.trim() || null;

        if (!id || !name || !image) {
            alert("Required form fields are empty.");
            return;
        }

        try {
            const res = await window.systemService.savePlugin({ id, name, image, network_mode, ui_entrypoint });
            if (res.ok) {
                alert("Plugin pulled and registered successfully!");
                document.getElementById("plugin-install-form").reset();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to pull docker container plugin.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async deletePlugin(id) {
        if (confirm(`Are you sure you want to remove service plugin "${id}"?`)) {
            try {
                const res = await window.systemService.deletePlugin(id);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete plugin.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }
}

window.dhcpComponent = new DhcpComponent();
window.vpnComponent = new VpnComponent();
window.peopleComponent = new PeopleComponent();
window.locationsComponent = new LocationsComponent();
window.systemComponent = new SystemComponent();
window.pluginsComponent = new PluginsComponent();
