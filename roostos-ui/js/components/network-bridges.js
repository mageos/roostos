/**
 * NetworkBridgesComponent - Web Component for Virtual Bridges and VLAN Segmentation
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderBridgesTemplate = (bridgeCount, bridgeRowsHtml, vlanCount, vlanRowsHtml) => html`
    <div class="network-bridges-container">
        <!-- Bridges Section -->
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Virtual Bridge Interfaces (${bridgeCount})</h3>
                    <p class="text-secondary" style="font-size:12px;">Layer 2 software bridges aggregating ports and Wi-Fi</p>
                </div>
                <button class="btn btn-primary btn-sm" id="top-add-bridge-btn">+ Add Bridge</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="bridges-table">
                    <thead>
                        <tr>
                            <th>Bridge Name</th>
                            <th>Gateway IP / CIDR</th>
                            <th>Member Interfaces</th>
                            <th>DHCP Server</th>
                            <th>Client Isolation</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="bridges-tbody">
                        ${bridgeRowsHtml}
                    </tbody>
                </table>
            </div>

            <div class="card-footer table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm" id="bottom-add-bridge-btn">+ Add Bridge</button>
            </div>
        </div>

        <!-- VLANs Section -->
        <div class="card">
            <div class="card-header table-action-bar">
                <div>
                    <h3>802.1Q VLAN Tags (${vlanCount})</h3>
                    <p class="text-secondary" style="font-size:12px;">Virtual LAN segmentation on physical trunk links</p>
                </div>
                <button class="btn btn-primary btn-sm" id="top-add-vlan-btn">+ Add VLAN</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="vlans-table">
                    <thead>
                        <tr>
                            <th>VLAN ID</th>
                            <th>Interface Name</th>
                            <th>Parent Link</th>
                            <th>IP / Subnet</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="vlans-tbody">
                        ${vlanRowsHtml}
                    </tbody>
                </table>
            </div>

            <div class="card-footer table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm" id="bottom-add-vlan-btn">+ Add VLAN</button>
            </div>
        </div>
    </div>
`;

const renderBridgeRowTemplate = (b) => html`
    <tr id="bridge-row-${b.name}">
        <td><strong><code>${b.name}</code></strong></td>
        <td><code>${b.ip || "192.168.1.1/24"}</code></td>
        <td>${(b.interfaces || []).map(i => html`<span class="badge badge-secondary">${i}</span>`).join(" ")}</td>
        <td><span class="badge ${b.dhcp_enabled !== false ? "badge-success" : "badge-secondary"}">${b.dhcp_enabled !== false ? "Enabled" : "Disabled"}</span></td>
        <td><span class="badge ${b.isolate ? "badge-danger" : "badge-outline"}">${b.isolate ? "Isolated" : "Open"}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-bridge-btn" data-name="${b.name}">Edit</button>
            <button class="btn btn-danger btn-sm delete-bridge-btn" data-name="${b.name}">Delete</button>
        </td>
    </tr>
`;

const renderInlineAddBridgeRowTemplate = () => html`
    <tr class="inline-add-row" id="inline-add-bridge-row">
        <td><input type="text" class="inline-input" id="add-br-name" placeholder="br1"></td>
        <td><input type="text" class="inline-input" id="add-br-ip" placeholder="192.168.20.1/24"></td>
        <td><input type="text" class="inline-input" id="add-br-ifaces" placeholder="eth2, wlan1"></td>
        <td>
            <label class="checkbox-container"><input type="checkbox" id="add-br-dhcp" checked> DHCP</label>
        </td>
        <td>
            <label class="checkbox-container"><input type="checkbox" id="add-br-isolate"> Isolate</label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-bridge-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-bridge-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

const renderVlanRowTemplate = (v) => html`
    <tr id="vlan-row-${v.id || v.name}">
        <td><span class="badge badge-info">VLAN ${v.id || v.tag}</span></td>
        <td><strong><code>${v.name || `vlan${v.id}`}</code></strong></td>
        <td><code>${v.parent || v.interface || "eth0"}</code></td>
        <td><code>${v.ip || "10.10." + (v.id || "10") + ".1/24"}</code></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-vlan-btn" data-id="${v.id || v.name}">Edit</button>
            <button class="btn btn-danger btn-sm delete-vlan-btn" data-id="${v.id || v.name}">Delete</button>
        </td>
    </tr>
`;

const renderInlineAddVlanRowTemplate = () => html`
    <tr class="inline-add-row" id="inline-add-vlan-row">
        <td><input type="number" class="inline-input" id="add-vlan-id" placeholder="10"></td>
        <td><input type="text" class="inline-input" id="add-vlan-name" placeholder="vlan10"></td>
        <td><input type="text" class="inline-input" id="add-vlan-parent" placeholder="eth0"></td>
        <td><input type="text" class="inline-input" id="add-vlan-ip" placeholder="10.10.10.1/24"></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-vlan-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-vlan-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class NetworkBridgesComponent extends HTMLElement {
    constructor() {
        super();
        this.bridges = [
            { name: "br0", ip: "192.168.1.1/24", interfaces: ["eth1"], dhcp_enabled: true, isolate: false },
            { name: "br-guest", ip: "192.168.10.1/24", interfaces: ["vlan-guest"], dhcp_enabled: true, isolate: true }
        ];
        this.vlans = [
            { id: 10, name: "vlan10", parent: "eth1", ip: "10.10.10.1/24" },
            { id: 20, name: "vlan-guest", parent: "eth1", ip: "192.168.10.1/24" }
        ];
    }

    setData(bridges, vlans) {
        if (bridges && Array.isArray(bridges)) this.bridges = bridges;
        if (vlans && Array.isArray(vlans)) this.vlans = vlans;
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const bridgeRowsHtml = this.bridges.map(b => renderBridgeRowTemplate(b)).join("");
        const vlanRowsHtml = this.vlans.map(v => renderVlanRowTemplate(v)).join("");
        this.innerHTML = renderBridgesTemplate(this.bridges.length, bridgeRowsHtml, this.vlans.length, vlanRowsHtml);

        this.querySelectorAll("#top-add-bridge-btn, #bottom-add-bridge-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddBridge();
        });

        this.querySelectorAll("#top-add-vlan-btn, #bottom-add-vlan-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddVlan();
        });

        this.querySelectorAll(".delete-bridge-btn").forEach(btn => {
            btn.onclick = () => {
                const name = btn.dataset.name;
                this.bridges = this.bridges.filter(b => b.name !== name);
                this.render();
                if (this.onSave) this.onSave(this.bridges, this.vlans);
            };
        });

        this.querySelectorAll(".delete-vlan-btn").forEach(btn => {
            btn.onclick = () => {
                const id = btn.dataset.id;
                this.vlans = this.vlans.filter(v => (v.id || v.name) != id);
                this.render();
                if (this.onSave) this.onSave(this.bridges, this.vlans);
            };
        });
    }

    showInlineAddBridge() {
        const tbody = this.querySelector("#bridges-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;
        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineAddBridgeRowTemplate();
        const row = temp.firstElementChild;
        tbody.insertBefore(row, tbody.firstChild);

        row.querySelector("#save-inline-bridge-btn").onclick = () => {
            const name = row.querySelector("#add-br-name").value.trim();
            const ip = row.querySelector("#add-br-ip").value.trim();
            const ifacesStr = row.querySelector("#add-br-ifaces").value.trim();
            const dhcp_enabled = row.querySelector("#add-br-dhcp").checked;
            const isolate = row.querySelector("#add-br-isolate").checked;

            if (!name) { alert("Bridge name is required."); return; }
            const interfaces = ifacesStr ? ifacesStr.split(",").map(s => s.trim()) : [];
            this.bridges.push({ name, ip, interfaces, dhcp_enabled, isolate });
            this.render();
            if (this.onSave) this.onSave(this.bridges, this.vlans);
        };

        row.querySelector("#cancel-inline-bridge-btn").onclick = () => row.remove();
    }

    showInlineAddVlan() {
        const tbody = this.querySelector("#vlans-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;
        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineAddVlanRowTemplate();
        const row = temp.firstElementChild;
        tbody.insertBefore(row, tbody.firstChild);

        row.querySelector("#save-inline-vlan-btn").onclick = () => {
            const id = parseInt(row.querySelector("#add-vlan-id").value, 10);
            const name = row.querySelector("#add-vlan-name").value.trim();
            const parent = row.querySelector("#add-vlan-parent").value.trim();
            const ip = row.querySelector("#add-vlan-ip").value.trim();

            if (!id || !name) { alert("VLAN ID and Name are required."); return; }
            this.vlans.push({ id, name, parent, ip });
            this.render();
            if (this.onSave) this.onSave(this.bridges, this.vlans);
        };

        row.querySelector("#cancel-inline-vlan-btn").onclick = () => row.remove();
    }
}

if (!customElements.get("roost-network-bridges")) {
    customElements.define("roost-network-bridges", NetworkBridgesComponent);
}
