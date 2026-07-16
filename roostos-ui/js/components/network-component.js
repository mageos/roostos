const NETWORK_TEMPLATE = `
    <div id="networks-view" class="view-pane">
        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('networks', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('networks', 'advanced')">Advanced</button>
            <button class="tab-btn" onclick="switchSubTab('networks', 'qos')">QoS Shaping</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="card">
                <h2>Unified Networks & Interface Mappings</h2>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddNetworkForm('top')">+ Add Network</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Network (Zone)</th>
                                <th>Type</th>
                                <th>Gateway / IP Config</th>
                                <th>Bound Adapters</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="networks-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">Loading networks configuration...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
                    <button class="btn btn-primary" onclick="showAddNetworkForm('bottom')">+ Add Network</button>
                </div>
            </div>

            <div class="card">
                <h2>WiFi Access Points & Mesh</h2>
                <form id="wifi-config-form" onsubmit="saveWifiSettings(event)">
                    <div id="wifi-aps-container"></div>
                    
                    <hr style="margin: 20px 0; border: none; border-top: 1px solid var(--card-border);">
                    
                    <div class="form-row-multi flex-align-center" style="margin-bottom: 20px;">
                        <label class="checkbox-container">
                            <input type="checkbox" id="wifi-mesh-enabled">
                            <span>Enable Mesh Backhaul Network</span>
                        </label>
                    </div>
                    <div class="form-row-multi">
                        <div class="form-group" style="flex: 1;">
                            <label>Mesh SSID</label>
                            <input type="text" id="wifi-mesh-ssid" placeholder="MeshSSID">
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label>Mesh Passphrase</label>
                            <input type="password" id="wifi-mesh-pass" placeholder="••••••••">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Save WiFi Settings</button>
                </form>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Advanced Interface Configuration</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Manage the physical network adapters, their zones (WAN vs LAN), and bridge bindings.
                </p>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <button class="btn btn-primary" onclick="showAddInterfaceForm()">+ Add Interface</button>
                </div>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Adapter Name</th>
                                <th>Zone</th>
                                <th>DHCP Client</th>
                                <th>Bound Bridge</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="interfaces-table-body">
                            <tr>
                                <td colspan="5" class="empty-state">Loading interfaces...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="tab-pane qos-pane">
            <div class="card">
                <h2>QoS Bandwidth & Traffic Shaping</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Limit overall upload/download speeds on your WAN interface and prioritize network tags.
                </p>
                <form id="qos-config-form" onsubmit="saveQosSettings(event)">
                    <div class="form-row-multi flex-align-center" style="margin-bottom: 20px;">
                        <label class="checkbox-container">
                            <input type="checkbox" id="qos-enabled">
                            <span>Enable QoS / Bandwidth Shaping</span>
                        </label>
                    </div>
                    <div class="form-row-multi">
                        <div class="form-group" style="flex: 1;">
                            <label>WAN Upload Limit (kbps)</label>
                            <input type="number" id="qos-upload" placeholder="e.g. 50000">
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label>WAN Download Limit (kbps)</label>
                            <input type="number" id="qos-download" placeholder="e.g. 100000">
                        </div>
                    </div>
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label>Prioritized Tags (comma-separated)</label>
                        <input type="text" id="qos-prioritize-tags" placeholder="e.g. gaming, voip, streaming">
                        <p style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">
                            Devices matching these tags will automatically receive prioritized queues.
                        </p>
                    </div>
                    <button type="submit" class="btn btn-primary">Save QoS Settings</button>
                </form>
            </div>
        </div>
    </div>
`;

class NetworkComponent {
    constructor() {
        this.template = NETWORK_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderNetworks = () => this.renderNetworks();
        window.saveWifiSettings = (e) => this.saveWifiSettings(e);
        window.saveQosSettings = (e) => this.saveQosSettings(e);
        window.showAddInterfaceForm = () => this.showAddInterfaceForm();
        window.saveNewInterface = (e) => this.saveNewInterface(e);
        window.editInterfaceInline = (n) => this.editInterfaceInline(n);
        window.saveInterfaceInline = (n, e) => this.saveInterfaceInline(n, e);
        window.deleteInterface = (n) => this.deleteInterface(n);
        window.showAddNetworkForm = (pos) => this.showAddNetworkForm(pos);
        window.saveNewNetwork = (e) => this.saveNewNetwork(e);
        window.editNetworkInline = (t, n) => this.editNetworkInline(t, n);
        window.saveNetworkInline = (t, n, e) => this.saveNetworkInline(t, n, e);
        window.deleteNetwork = (t, n) => this.deleteNetwork(t, n);
        window.toggleWanIpInput = (cb) => this.toggleWanIpInput(cb);
        window.toggleInterfaceBridgeSelect = (s) => this.toggleInterfaceBridgeSelect(s);
    }

    render(netData) {
        this.renderNetworks();
        this.renderWifiSettings(window.wifiSettings);
    }

    toggleWanIpInput(cb) {
        const ipGroup = document.getElementById("wan-ip-group");
        if (ipGroup) {
            ipGroup.style.display = cb.checked ? "none" : "block";
        }
    }

    toggleInterfaceBridgeSelect(select) {
        const form = select.closest("form");
        const bridgeGroup = form.querySelector("#if-bridge-group") || form.querySelector("#if-bridge-group-new");
        if (bridgeGroup) {
            bridgeGroup.style.display = select.value === 'wan' ? 'none' : 'block';
        }
    }

    renderNetworks() {
        const tableBody = document.getElementById("networks-table-body");
        if (!tableBody || !window.networkSettings) return;

        // Populate QoS Configuration fields
        const qos = window.networkSettings.qos || { enabled: false, wan_upload_kbps: null, wan_download_kbps: null, prioritize_tags: [] };
        const qosEnabledEl = document.getElementById("qos-enabled");
        if (qosEnabledEl) {
            qosEnabledEl.checked = qos.enabled;
            document.getElementById("qos-upload").value = qos.wan_upload_kbps !== null ? qos.wan_upload_kbps : "";
            document.getElementById("qos-download").value = qos.wan_download_kbps !== null ? qos.wan_download_kbps : "";
            document.getElementById("qos-prioritize-tags").value = (qos.prioritize_tags || []).join(", ");
        }

        const interfaces = window.networkSettings.interfaces || [];
        const bridges = window.networkSettings.bridges || [];
        const vlans = window.networkSettings.vlans || [];

        let rows = [];

        // 1. WAN Interface(s)
        interfaces.filter(i => i.role === "wan").forEach(wan => {
            rows.push({
                id: `wan-${wan.name}`,
                role: "Internet (WAN)",
                name: wan.name,
                type: "Internet",
                gateway: wan.dhcp ? "DHCP Client" : (wan.ip || "Static IP"),
                adapters: `<span class="badge badge-online">${escapeHtml(wan.name)}</span>`,
                actions: `<button class="btn btn-secondary btn-sm" onclick="editNetworkInline('wan', '${escapeJs(wan.name)}')">Edit</button>`,
                rawData: wan
            });
        });

        // 2. Bridges
        bridges.forEach(br => {
            const bound = interfaces.filter(i => i.bridge === br.name).map(i => i.name);
            const boundBadges = bound.length > 0 
                ? bound.map(n => `<span class="badge badge-outline">${escapeHtml(n)}</span>`).join(" ") 
                : `<span style="color: var(--text-secondary); font-size: 12px;">None</span>`;

            rows.push({
                id: `bridge-${br.name}`,
                role: `Local Bridge (${escapeHtml(br.name)})`,
                name: br.name,
                type: "Bridge",
                gateway: escapeHtml(br.ip),
                adapters: boundBadges,
                actions: `
                    <button class="btn btn-secondary btn-sm" onclick="editNetworkInline('bridge', '${escapeJs(br.name)}')">Edit</button>
                    ${br.name !== 'br0' ? `<button class="btn btn-secondary btn-sm" style="color: var(--accent-red);" onclick="deleteNetwork('bridge', '${escapeJs(br.name)}')">Delete</button>` : ''}
                `,
                rawData: br
            });
        });

        // 3. VLANs
        vlans.forEach(vl => {
            const isolateLabel = vl.isolate ? '<span style="color: var(--accent-red); font-size: 11px; margin-left: 6px;">(Isolated)</span>' : '';
            rows.push({
                id: `vlan-${vl.name}`,
                role: `VLAN (${escapeHtml(vl.name)})`,
                name: vl.name,
                type: `VLAN ${isolateLabel}`,
                gateway: escapeHtml(vl.ip),
                adapters: `<span class="badge badge-outline">${escapeHtml(vl.interface)} (VLAN ${vl.id})</span>`,
                actions: `
                    <button class="btn btn-secondary btn-sm" onclick="editNetworkInline('vlan', '${escapeJs(vl.name)}')">Edit</button>
                    <button class="btn btn-secondary btn-sm" style="color: var(--accent-red);" onclick="deleteNetwork('vlan', '${escapeJs(vl.name)}')">Delete</button>
                `,
                rawData: vl
            });
        });

        if (rows.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No networks configured.</td></tr>';
            return;
        }

        tableBody.innerHTML = rows.map(r => `
            <tr id="row-${r.id}">
                <td><strong>${r.role}</strong></td>
                <td>${r.type}</td>
                <td><code>${r.gateway}</code></td>
                <td>${r.adapters}</td>
                <td class="table-actions">${r.actions}</td>
            </tr>
        `).join("");
    }

    renderWifiSettings(wifi) {
        const apsContainer = document.getElementById("wifi-aps-container");
        if (!apsContainer) return;
        const aps = wifi.access_points || [];
        
        apsContainer.innerHTML = aps.map((ap, index) => `
            <div class="wifi-ap-row" style="margin-bottom: 24px;">
                <h4 style="font-size: 13px; margin-bottom: 12px; font-weight: 600; color: var(--text-secondary);">Access Point #${index + 1} (${escapeHtml(ap.interface)})</h4>
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1;">
                        <label>SSID (Network Name)</label>
                        <input type="text" class="wifi-ap-ssid" data-index="${index}" value="${escapeHtml(ap.ssid)}" required>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>WiFi Passphrase</label>
                        <input type="password" class="wifi-ap-pass" data-index="${index}" value="${escapeHtml(ap.passphrase)}" required>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Security Protocol</label>
                        <select class="wifi-ap-sec" data-index="${index}">
                            <option value="wpa3" ${ap.security === 'wpa3' ? 'selected' : ''}>WPA3 Personal</option>
                            <option value="wpa2" ${ap.security === 'wpa2' ? 'selected' : ''}>WPA2 Personal</option>
                        </select>
                    </div>
                </div>
            </div>
        `).join("");
        
        const mesh = wifi.mesh || {};
        const meshEnabledEl = document.getElementById("wifi-mesh-enabled");
        if (meshEnabledEl) meshEnabledEl.checked = mesh.enabled || false;
        const meshSsidEl = document.getElementById("wifi-mesh-ssid");
        if (meshSsidEl) meshSsidEl.value = mesh.ssid || "";
        const meshPassEl = document.getElementById("wifi-mesh-pass");
        if (meshPassEl) meshPassEl.value = mesh.passphrase || "";
    }

    editNetworkInline(type, name) {
        const rowEl = document.getElementById(`row-${type}-${name}`);
        if (!rowEl) return;

        const interfaces = window.networkSettings.interfaces || [];
        const bridges = window.networkSettings.bridges || [];
        const vlans = window.networkSettings.vlans || [];

        if (type === 'wan') {
            const rawData = interfaces.find(i => i.name === name) || {};
            rowEl.innerHTML = `
                <td colspan="5">
                    <form onsubmit="saveNetworkInline('wan', '${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%;">
                        <div class="form-group" style="margin: 0; flex: 1;">
                            <label style="margin: 0; font-size: 11px;">Physical Adapter</label>
                            <select name="wan_interface" class="theme-select" style="padding: 4px 8px; width: 100%;">
                                ${interfaces.map(i => `<option value="${i.name}" ${i.name === name ? 'selected' : ''}>${i.name}</option>`).join("")}
                            </select>
                        </div>
                        <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                            <input type="checkbox" name="wan_dhcp" ${rawData.dhcp ? 'checked' : ''} onchange="toggleWanIpInput(this)">
                            <label style="margin: 0; font-size: 11px;">DHCP Client</label>
                        </div>
                        <div class="form-group" id="wan-ip-group" style="margin: 0; flex: 1; display: ${rawData.dhcp ? 'none' : 'block'};">
                            <label style="margin: 0; font-size: 11px;">Static IP / CIDR</label>
                            <input type="text" name="wan_ip" value="${escapeHtml(rawData.ip || '')}" placeholder="192.168.100.2/24" style="padding: 4px 8px; width: 100%;">
                        </div>
                        <div style="display: flex; gap: 8px; margin-top: 14px;">
                            <button type="submit" class="btn btn-primary btn-sm">Save</button>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="renderNetworks()">Cancel</button>
                        </div>
                    </form>
                </td>
            `;
        } else if (type === 'bridge') {
            const rawData = bridges.find(b => b.name === name) || {};
            rowEl.innerHTML = `
                <td colspan="5">
                    <form onsubmit="saveNetworkInline('bridge', '${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
                        <div style="display: flex; gap: 16px; align-items: center;">
                            <div class="form-group" style="margin: 0; flex: 1;">
                                <label style="margin: 0; font-size: 11px;">Gateway IP / Subnet</label>
                                <input type="text" name="bridge_ip" value="${escapeHtml(rawData.ip || '')}" required style="padding: 4px 8px; width: 100%;">
                            </div>
                            <div style="display: flex; gap: 8px; margin-top: 14px;">
                                <button type="submit" class="btn btn-primary btn-sm">Save</button>
                                <button type="button" class="btn btn-secondary btn-sm" onclick="renderNetworks()">Cancel</button>
                            </div>
                        </div>
                        <div>
                            <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 6px;">Attach Physical Adapters:</label>
                            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                                ${interfaces.map(i => {
                                    const isBoundToThis = i.bridge === name;
                                    return `
                                        <label class="checkbox-container" style="font-size: 12px;">
                                            <input type="checkbox" name="bound_adapters" value="${i.name}" ${isBoundToThis ? 'checked' : ''}>
                                            <span>${i.name}</span>
                                        </label>
                                    `;
                                }).join("")}
                            </div>
                        </div>
                    </form>
                </td>
            `;
        } else if (type === 'vlan') {
            const rawData = vlans.find(v => v.name === name) || {};
            rowEl.innerHTML = `
                <td colspan="5">
                    <form onsubmit="saveNetworkInline('vlan', '${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap;">
                        <div class="form-group" style="margin: 0; flex: 1; min-width: 150px;">
                            <label style="margin: 0; font-size: 11px;">Gateway IP / Subnet</label>
                            <input type="text" name="vlan_ip" value="${escapeHtml(rawData.ip || '')}" required style="padding: 4px 8px; width: 100%;">
                        </div>
                        <div class="form-group" style="margin: 0; width: 80px;">
                            <label style="margin: 0; font-size: 11px;">VLAN ID</label>
                            <input type="number" name="vlan_id" value="${rawData.id || 10}" required style="padding: 4px 8px; width: 100%;">
                        </div>
                        <div class="form-group" style="margin: 0; flex: 1; min-width: 120px;">
                            <label style="margin: 0; font-size: 11px;">Parent Interface</label>
                            <select name="vlan_parent" class="theme-select" style="padding: 4px 8px; width: 100%;">
                                ${interfaces.map(i => `<option value="${i.name}" ${i.name === rawData.interface ? 'selected' : ''}>${i.name}</option>`).join("")}
                            </select>
                        </div>
                        <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                            <input type="checkbox" name="vlan_isolate" ${rawData.isolate ? 'checked' : ''}>
                            <label style="margin: 0; font-size: 11px;">Isolate Network</label>
                        </div>
                        <div style="display: flex; gap: 8px; margin-top: 14px;">
                            <button type="submit" class="btn btn-primary btn-sm">Save</button>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="renderNetworks()">Cancel</button>
                        </div>
                    </form>
                </td>
            `;
        }
    }

    async saveNetworkInline(type, name, event) {
        event.preventDefault();
        const form = event.target;
        
        let interfaces = JSON.parse(JSON.stringify(window.networkSettings.interfaces || []));
        let bridges = JSON.parse(JSON.stringify(window.networkSettings.bridges || []));
        let vlans = JSON.parse(JSON.stringify(window.networkSettings.vlans || []));
        
        if (type === 'wan') {
            const selectedIf = form.elements['wan_interface'].value;
            const isDhcp = form.elements['wan_dhcp'].checked;
            const staticIp = form.elements['wan_ip'] ? form.elements['wan_ip'].value : "";
            
            interfaces.forEach(i => {
                if (i.name === name) {
                    i.role = "lan";
                    i.dhcp = false;
                    i.ip = null;
                }
            });
            
            const targetIf = interfaces.find(i => i.name === selectedIf);
            if (targetIf) {
                targetIf.role = "wan";
                targetIf.dhcp = isDhcp;
                targetIf.ip = isDhcp ? null : staticIp;
                targetIf.bridge = null;
            } else {
                interfaces.push({
                    name: selectedIf,
                    role: "wan",
                    dhcp: isDhcp,
                    ip: isDhcp ? null : staticIp
                });
            }
        } else if (type === 'bridge') {
            const newIp = form.elements['bridge_ip'].value;
            let checkedAdapters = [];
            if (form.elements['bound_adapters']) {
                if (form.elements['bound_adapters'].value && !form.elements['bound_adapters'].length) {
                    if (form.elements['bound_adapters'].checked) checkedAdapters.push(form.elements['bound_adapters'].value);
                } else {
                    checkedAdapters = Array.from(form.elements['bound_adapters'])
                        .filter(cb => cb.checked)
                        .map(cb => cb.value);
                }
            }
                
            const targetBr = bridges.find(b => b.name === name);
            if (targetBr) {
                targetBr.ip = newIp;
            }
            
            interfaces.forEach(i => {
                if (checkedAdapters.includes(i.name)) {
                    i.bridge = name;
                    i.role = "lan";
                } else if (i.bridge === name) {
                    i.bridge = null;
                }
            });
        } else if (type === 'vlan') {
            const newIp = form.elements['vlan_ip'].value;
            const newId = parseInt(form.elements['vlan_id'].value, 10);
            const parentIf = form.elements['vlan_parent'].value;
            const isolate = form.elements['vlan_isolate'].checked;
            
            const targetVl = vlans.find(v => v.name === name);
            if (targetVl) {
                targetVl.ip = newIp;
                targetVl.id = newId;
                targetVl.interface = parentIf;
                targetVl.isolate = isolate;
            }
        }
        
        await window.networkService.sendNetworkConfigUpdate(interfaces, bridges, vlans);
    }

    showAddNetworkForm(position) {
        const tableBody = document.getElementById("networks-table-body");
        const interfaces = window.networkSettings.interfaces || [];

        const addRowHtml = `
            <tr id="temp-add-network-row">
                <td colspan="5">
                    <form id="add-network-form" onsubmit="saveNewNetwork(event)" class="inline-edit-form" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
                        <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
                            <div class="form-group" style="margin: 0; width: 120px;">
                                <label style="margin: 0; font-size: 11px;">Network Type</label>
                                <select id="new_net_type" onchange="toggleNewNetworkFields(this.value)" class="theme-select" style="padding: 4px 8px; width: 100%;">
                                    <option value="bridge">Bridge</option>
                                    <option value="vlan">VLAN</option>
                                </select>
                            </div>
                            <div class="form-group" style="margin: 0; flex: 1;">
                                <label style="margin: 0; font-size: 11px;">Network Name / ID</label>
                                <input type="text" id="new_net_name" required placeholder="e.g. br1 or vlan-guest" style="padding: 4px 8px; width: 100%;">
                            </div>
                            <div class="form-group" style="margin: 0; flex: 1;">
                                <label style="margin: 0; font-size: 11px;">Gateway IP / Subnet</label>
                                <input type="text" id="new_net_ip" required placeholder="e.g. 192.168.2.1/24" style="padding: 4px 8px; width: 100%;">
                            </div>
                            
                            <div class="form-group vlan-only-field" style="margin: 0; width: 80px; display: none;">
                                <label style="margin: 0; font-size: 11px;">VLAN ID</label>
                                <input type="number" id="new_vlan_id" placeholder="10" style="padding: 4px 8px; width: 100%;">
                            </div>
                            <div class="form-group vlan-only-field" style="margin: 0; flex: 1; min-width: 120px; display: none;">
                                <label style="margin: 0; font-size: 11px;">Parent Interface</label>
                                <select id="new_vlan_parent" class="theme-select" style="padding: 4px 8px; width: 100%;">
                                    ${interfaces.map(i => `<option value="${i.name}">${i.name}</option>`).join("")}
                                </select>
                            </div>
                            <div class="form-group vlan-only-field" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px; display: none;">
                                <input type="checkbox" id="new_vlan_isolate" checked>
                                <label style="margin: 0; font-size: 11px;">Isolate Network</label>
                            </div>

                            <div style="display: flex; gap: 8px; margin-top: 14px;">
                                <button type="submit" class="btn btn-primary btn-sm">Save</button>
                                <button type="button" class="btn btn-secondary btn-sm" onclick="cancelAddNetwork()">Cancel</button>
                            </div>
                        </div>

                        <div id="bridge-adapters-section">
                            <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 6px;">Attach Physical Adapters:</label>
                            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                                ${interfaces.map(i => `
                                    <label class="checkbox-container" style="font-size: 12px;">
                                        <input type="checkbox" name="new_bound_adapters" value="${i.name}">
                                        <span>${i.name}</span>
                                    </label>
                                `).join("")}
                            </div>
                        </div>
                    </form>
                </td>
            </tr>
        `;

        const existing = document.getElementById("temp-add-network-row");
        if (existing) existing.remove();

        if (position === "top") {
            tableBody.insertAdjacentHTML("afterbegin", addRowHtml);
        } else {
            tableBody.insertAdjacentHTML("beforeend", addRowHtml);
        }
    }

    async saveNewNetwork(event) {
        event.preventDefault();
        const type = document.getElementById("new_net_type").value;
        const name = document.getElementById("new_net_name").value.trim();
        const ip = document.getElementById("new_net_ip").value.trim();
        
        let interfaces = JSON.parse(JSON.stringify(window.networkSettings.interfaces || []));
        let bridges = JSON.parse(JSON.stringify(window.networkSettings.bridges || []));
        let vlans = JSON.parse(JSON.stringify(window.networkSettings.vlans || []));
        
        if (type === 'bridge') {
            if (bridges.some(b => b.name === name)) {
                alert("A bridge with this name already exists.");
                return;
            }
            
            bridges.push({ name, ip });
            
            const boundAdaptersEls = document.getElementsByName("new_bound_adapters");
            let checkedAdapters = [];
            if (boundAdaptersEls) {
                checkedAdapters = Array.from(boundAdaptersEls)
                    .filter(cb => cb.checked)
                    .map(cb => cb.value);
            }
                
            interfaces.forEach(i => {
                if (checkedAdapters.includes(i.name)) {
                    i.bridge = name;
                    i.role = "lan";
                }
            });
        } else if (type === 'vlan') {
            if (vlans.some(v => v.name === name)) {
                alert("A VLAN with this name already exists.");
                return;
            }
            const vlanId = parseInt(document.getElementById("new_vlan_id").value || "10", 10);
            const parentIf = document.getElementById("new_vlan_parent").value;
            const isolate = document.getElementById("new_vlan_isolate").checked;
            
            vlans.push({
                name,
                id: vlanId,
                interface: parentIf,
                ip,
                isolate
            });
        }
        
        await window.networkService.sendNetworkConfigUpdate(interfaces, bridges, vlans);
    }

    async deleteNetwork(type, name) {
        if (!confirm(`Are you sure you want to delete the network "${name}"?`)) {
            return;
        }
        
        let interfaces = JSON.parse(JSON.stringify(window.networkSettings.interfaces || []));
        let bridges = JSON.parse(JSON.stringify(window.networkSettings.bridges || []));
        let vlans = JSON.parse(JSON.stringify(window.networkSettings.vlans || []));
        
        if (type === 'bridge') {
            bridges = bridges.filter(b => b.name !== name);
            interfaces.forEach(i => {
                if (i.bridge === name) {
                    i.bridge = null;
                }
            });
        } else if (type === 'vlan') {
            vlans = vlans.filter(v => v.name !== name);
        }
        
        await window.networkService.sendNetworkConfigUpdate(interfaces, bridges, vlans);
    }

    async saveWifiSettings(e) {
        e.preventDefault();
        const aps = window.wifiSettings.access_points || [];
        
        document.querySelectorAll(".wifi-ap-ssid").forEach(input => {
            const idx = parseInt(input.dataset.index, 10);
            aps[idx].ssid = input.value.trim();
        });
        document.querySelectorAll(".wifi-ap-pass").forEach(input => {
            const idx = parseInt(input.dataset.index, 10);
            aps[idx].passphrase = input.value;
        });
        document.querySelectorAll(".wifi-ap-sec").forEach(select => {
            const idx = parseInt(select.dataset.index, 10);
            aps[idx].security = select.value;
        });
        
        const mesh = {
            enabled: document.getElementById("wifi-mesh-enabled").checked,
            interface: window.wifiSettings.mesh?.interface || "wlan1",
            ssid: document.getElementById("wifi-mesh-ssid").value.trim(),
            passphrase: document.getElementById("wifi-mesh-pass").value,
            frequency: window.wifiSettings.mesh?.frequency || 5180
        };
        
        const updatedWifi = {
            access_points: aps,
            mesh: mesh
        };
        
        try {
            const res = await window.networkService.saveConfig(window.networkSettings, updatedWifi, window.vpnSettings);
            if (res.ok) {
                alert("WiFi and Mesh configurations saved successfully!");
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save WiFi settings.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    async saveQosSettings(event) {
        event.preventDefault();
        const qosEnabled = document.getElementById("qos-enabled").checked;
        const uploadLimitVal = document.getElementById("qos-upload").value;
        const downloadLimitVal = document.getElementById("qos-download").value;
        const uploadLimit = uploadLimitVal ? parseInt(uploadLimitVal, 10) : null;
        const downloadLimit = downloadLimitVal ? parseInt(downloadLimitVal, 10) : null;
        const prioritizeTagsStr = document.getElementById("qos-prioritize-tags").value || "";
        const prioritizeTags = prioritizeTagsStr.split(",").map(t => t.trim()).filter(t => t.length > 0);

        window.networkSettings.qos = {
            enabled: qosEnabled,
            wan_upload_kbps: uploadLimit,
            wan_download_kbps: downloadLimit,
            prioritize_tags: prioritizeTags
        };

        try {
            const res = await window.networkService.saveConfig(window.networkSettings, window.wifiSettings, window.vpnSettings);
            if (res.ok) {
                alert("Traffic shaping settings saved successfully!");
                if (window.loadDashboard) window.loadDashboard();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail || 'Failed to save traffic shaping settings'}`);
            }
        } catch (e) {
            console.error(e);
            alert("Failed to propagate traffic shaping settings.");
        }
    }

    showAddInterfaceForm() {
        const tableBody = document.getElementById("interfaces-table-body");
        if (!tableBody) return;
        
        const existing = document.getElementById("interface-add-row");
        if (existing) existing.remove();
        
        const bridges = window.networkSettings.bridges || [];
        
        const addRow = document.createElement("tr");
        addRow.id = "interface-add-row";
        addRow.innerHTML = `
            <td colspan="5">
                <form onsubmit="saveNewInterface(event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap;">
                    <div class="form-group" style="margin: 0; flex: 1; min-width: 120px;">
                        <label style="margin: 0; font-size: 11px;">Interface Name</label>
                        <input type="text" name="if_name" required placeholder="e.g. eth3" style="padding: 4px 8px; width: 100%;">
                    </div>
                    <div class="form-group" style="margin: 0; flex: 1; min-width: 100px;">
                        <label style="margin: 0; font-size: 11px;">Zone</label>
                        <select name="if_role" class="theme-select" style="padding: 4px 8px; width: 100%;" onchange="toggleInterfaceBridgeSelect(this)">
                            <option value="lan">LAN</option>
                            <option value="wan">WAN</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                        <input type="checkbox" name="if_dhcp">
                        <label style="margin: 0; font-size: 11px;">DHCP Client</label>
                    </div>
                    <div class="form-group" id="if-bridge-group-new" style="margin: 0; flex: 1; min-width: 120px;">
                        <label style="margin: 0; font-size: 11px;">Bridge Binding</label>
                        <select name="if_bridge" class="theme-select" style="padding: 4px 8px; width: 100%;">
                            <option value="">None</option>
                            ${bridges.map(br => `<option value="${br.name}">${br.name}</option>`).join("")}
                        </select>
                    </div>
                    <div style="display: flex; gap: 8px; margin-top: 14px;">
                        <button type="submit" class="btn btn-primary btn-sm">Add</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('tr').remove()">Cancel</button>
                    </div>
                </form>
            </td>
        `;
        
        tableBody.insertBefore(addRow, tableBody.firstChild);
    }

    async saveNewInterface(event) {
        event.preventDefault();
        const form = event.target;
        const name = form.if_name.value.trim();
        const role = form.if_role.value;
        const dhcp = form.if_dhcp.checked;
        const bridge = role === 'wan' ? null : (form.if_bridge.value || null);
        
        if (!window.networkSettings.interfaces) {
            window.networkSettings.interfaces = [];
        }
        
        if (window.networkSettings.interfaces.some(i => i.name === name)) {
            alert("An interface with this name already exists.");
            return;
        }
        
        window.networkSettings.interfaces.push({
            name,
            role,
            dhcp,
            bridge
        });
        
        await window.networkService.sendNetworkConfigUpdate(
            window.networkSettings.interfaces,
            window.networkSettings.bridges,
            window.networkSettings.vlans
        );
        this.renderInterfaces();
    }

    editInterfaceInline(name) {
        const rowEl = document.getElementById(`row-interface-${name}`);
        if (!rowEl) return;
        
        const interfaces = window.networkSettings.interfaces || [];
        const bridges = window.networkSettings.bridges || [];
        const i = interfaces.find(item => item.name === name);
        if (!i) return;
        
        rowEl.innerHTML = `
            <td colspan="5">
                <form onsubmit="saveInterfaceInline('${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap;">
                    <div class="form-group" style="margin: 0; flex: 1; min-width: 120px;">
                        <label style="margin: 0; font-size: 11px;">Interface Name</label>
                        <input type="text" name="if_name" value="${escapeHtml(i.name)}" disabled style="padding: 4px 8px; width: 100%;">
                    </div>
                    <div class="form-group" style="margin: 0; flex: 1; min-width: 100px;">
                        <label style="margin: 0; font-size: 11px;">Zone</label>
                        <select name="if_role" class="theme-select" style="padding: 4px 8px; width: 100%;" onchange="toggleInterfaceBridgeSelect(this)">
                            <option value="wan" ${i.role === 'wan' ? 'selected' : ''}>WAN</option>
                            <option value="lan" ${i.role === 'lan' ? 'selected' : ''}>LAN</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                        <input type="checkbox" name="if_dhcp" ${i.dhcp ? 'checked' : ''}>
                        <label style="margin: 0; font-size: 11px;">DHCP Client</label>
                    </div>
                    <div class="form-group" id="if-bridge-group" style="margin: 0; flex: 1; min-width: 120px; display: ${i.role === 'wan' ? 'none' : 'block'};">
                        <label style="margin: 0; font-size: 11px;">Bridge Binding</label>
                        <select name="if_bridge" class="theme-select" style="padding: 4px 8px; width: 100%;">
                            <option value="">None</option>
                            ${bridges.map(br => `<option value="${br.name}" ${i.bridge === br.name ? 'selected' : ''}>${br.name}</option>`).join("")}
                        </select>
                    </div>
                    <div style="display: flex; gap: 8px; margin-top: 14px;">
                        <button type="submit" class="btn btn-primary btn-sm">Save</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="window.networkComponent.renderInterfaces()">Cancel</button>
                    </div>
                </form>
            </td>
        `;
    }

    async saveInterfaceInline(name, event) {
        event.preventDefault();
        const form = event.target;
        const role = form.if_role.value;
        const dhcp = form.if_dhcp.checked;
        const bridge = role === 'wan' ? null : (form.if_bridge.value || null);
        
        const i = window.networkSettings.interfaces.find(item => item.name === name);
        if (i) {
            i.role = role;
            i.dhcp = dhcp;
            i.bridge = bridge;
        }
        
        await window.networkService.sendNetworkConfigUpdate(
            window.networkSettings.interfaces,
            window.networkSettings.bridges,
            window.networkSettings.vlans
        );
        this.renderInterfaces();
        this.renderNetworks();
    }

    async deleteInterface(name) {
        if (!confirm(`Are you sure you want to delete physical interface "${name}"?`)) return;
        window.networkSettings.interfaces = (window.networkSettings.interfaces || []).filter(i => i.name !== name);
        await window.networkService.sendNetworkConfigUpdate(
            window.networkSettings.interfaces,
            window.networkSettings.bridges,
            window.networkSettings.vlans
        );
        this.renderInterfaces();
        this.renderNetworks();
    }

    renderInterfaces() {
        const tableBody = document.getElementById("interfaces-table-body");
        if (!tableBody || !window.networkSettings) return;
        
        const interfaces = window.networkSettings.interfaces || [];
        if (interfaces.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No interfaces configured.</td></tr>';
            return;
        }
        
        tableBody.innerHTML = interfaces.map(i => `
            <tr id="row-interface-${i.name}">
                <td><strong>${escapeHtml(i.name)}</strong></td>
                <td><span class="badge ${i.role === 'wan' ? 'badge-online' : 'badge-outline'}">${i.role === 'wan' ? 'WAN' : 'LAN'}</span></td>
                <td>${i.dhcp ? 'Enabled' : 'Disabled'}</td>
                <td><code>${escapeHtml(i.bridge || 'None')}</code></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editInterfaceInline('${escapeJs(i.name)}')">Edit</button>
                    <button class="btn btn-secondary btn-sm" style="color: var(--accent-red);" onclick="deleteInterface('${escapeJs(i.name)}')">Delete</button>
                </td>
            </tr>
        `).join("");
    }
}

window.networkComponent = new NetworkComponent();
