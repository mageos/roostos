/**
 * NetworkZonesComponent - Web Component for Network Zone Management
 * Uses top-of-file module-scoped HTML template helpers tagged with html\`...\`
 * for full IDE syntax highlighting, auto-completion, and separation of UI templates from class logic.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderNetworkZonesTemplate = (count, rowsHtml) => html`
    <div class="card">
        <div class="card-header table-action-bar">
            <div>
                <h3>Network Zones (${count})</h3>
                <p class="text-secondary" style="font-size:12px;">Logical zone groupings and stateful conntrack routing rules</p>
            </div>
            <button class="btn btn-primary btn-sm" id="top-add-zone-btn">+ Add Zone</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="zones-table">
                <thead>
                    <tr>
                        <th>Zone ID</th>
                        <th>Name</th>
                        <th>Constituent Interfaces</th>
                        <th>Permitted Outgoing Zones (allow_zones)</th>
                        <th>Isolate</th>
                        <th>NAT Egress</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="zones-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-zone-btn">+ Add Zone</button>
        </div>
    </div>
`;

const renderZoneRowTemplate = (z) => html`
    <tr id="zone-row-${z.id}">
        <td><code>${z.id}</code></td>
        <td><strong>${z.name}</strong></td>
        <td>${(z.interfaces || []).map(i => html`<span class="badge badge-secondary">${i}</span>`).join(" ")}</td>
        <td>${(z.allow_zones || []).map(az => html`<span class="badge badge-info">${az}</span>`).join(" ") || "<em>None (Drop)</em>"}</td>
        <td><span class="badge ${z.isolate ? "badge-danger" : "badge-success"}">${z.isolate ? "Isolated" : "Open"}</span></td>
        <td><span class="badge">${z.masquerade ? "MASQUERADE" : "No NAT"}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-zone-btn" data-id="${z.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-zone-btn" data-id="${z.id}">Delete</button>
        </td>
    </tr>
`;

const renderInlineAddZoneRowTemplate = () => html`
    <tr class="inline-add-row">
        <td><input type="text" class="inline-input" id="add-zone-id" placeholder="e.g. dmz"></td>
        <td><input type="text" class="inline-input" id="add-zone-name" placeholder="e.g. Public DMZ"></td>
        <td><input type="text" class="inline-input" id="add-zone-interfaces" placeholder="e.g. eth2, vlan-dmz"></td>
        <td><input type="text" class="inline-input" id="add-zone-allows" placeholder="e.g. wan"></td>
        <td>
            <label class="checkbox-container">
                <input type="checkbox" id="add-zone-isolate" checked> Isolate
            </label>
        </td>
        <td>
            <label class="checkbox-container">
                <input type="checkbox" id="add-zone-masq"> NAT
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-zone-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-zone-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class NetworkZonesComponent extends HTMLElement {
    constructor() {
        super();
        this.zones = [
            { id: "lan", name: "Household LAN", interfaces: ["br0"], isolate: false, allow_zones: ["wan", "iot", "guest"], masquerade: false },
            { id: "wan", name: "Internet WAN", interfaces: ["eth0"], isolate: false, allow_zones: [], masquerade: true },
            { id: "iot", name: "Smart Home IoT Zone", interfaces: ["vlan-iot"], isolate: true, allow_zones: ["wan"], masquerade: false },
            { id: "guest", name: "Guest Wi-Fi Zone", interfaces: ["vlan-guest"], isolate: true, allow_zones: ["wan"], masquerade: false }
        ];
    }

    setZones(zoneList) {
        if (zoneList && zoneList.length > 0) {
            this.zones = zoneList;
        }
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const rowsHtml = this.zones.map(z => renderZoneRowTemplate(z)).join("");
        this.innerHTML = renderNetworkZonesTemplate(this.zones.length, rowsHtml);

        this.querySelectorAll("#top-add-zone-btn, #bottom-add-zone-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#zones-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineAddZoneRowTemplate();
        const addTr = tempContainer.firstElementChild;

        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-inline-zone-btn").onclick = () => {
            const id = addTr.querySelector("#add-zone-id").value.trim();
            const name = addTr.querySelector("#add-zone-name").value.trim();
            const ifacesStr = addTr.querySelector("#add-zone-interfaces").value.trim();
            const allowsStr = addTr.querySelector("#add-zone-allows").value.trim();
            const isolate = addTr.querySelector("#add-zone-isolate").checked;
            const masquerade = addTr.querySelector("#add-zone-masq").checked;

            if (!id || !name) {
                alert("Zone ID and Name are required.");
                return;
            }

            const interfaces = ifacesStr ? ifacesStr.split(",").map(s => s.trim()) : [];
            const allow_zones = allowsStr ? allowsStr.split(",").map(s => s.trim()) : [];

            const newZone = { id, name, interfaces, isolate, allow_zones, masquerade };
            this.zones.push(newZone);
            this.render();
            if (this.onSave) this.onSave(this.zones);
        };

        addTr.querySelector("#cancel-inline-zone-btn").onclick = () => addTr.remove();
    }
}

if (!customElements.get("roost-network-zones")) {
    customElements.define("roost-network-zones", NetworkZonesComponent);
}
