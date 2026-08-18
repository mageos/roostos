/**
 * NetworkZonesComponent - Web Component for Network Zone Management
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
        <td>${(z.interfaces || []).map(i => html`<span class="badge badge-secondary">${i}</span>`).join(" ") || "<em>None</em>"}</td>
        <td>${(z.allow_zones || []).map(az => html`<span class="badge badge-info">${az}</span>`).join(" ") || "<em>None (Drop)</em>"}</td>
        <td><span class="badge ${z.isolate ? "badge-danger" : "badge-success"}">${z.isolate ? "Isolated" : "Open"}</span></td>
        <td><span class="badge ${z.masquerade ? "badge-warning" : "badge-outline"}">${z.masquerade ? "MASQUERADE" : "No NAT"}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-zone-btn" data-id="${z.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-zone-btn" data-id="${z.id}">Delete</button>
        </td>
    </tr>
`;

const renderInlineZoneFormTemplate = (z = {}, isEdit = false) => html`
    <tr class="${isEdit ? "inline-edit-row" : "inline-add-row"}" id="${isEdit ? `edit-zone-row-${z.id}` : "inline-add-zone-row"}">
        <td><input type="text" class="inline-input" id="zone-form-id" value="${z.id || ""}" ${isEdit ? "disabled" : ""} placeholder="e.g. dmz"></td>
        <td><input type="text" class="inline-input" id="zone-form-name" value="${z.name || ""}" placeholder="e.g. Public DMZ"></td>
        <td><input type="text" class="inline-input" id="zone-form-interfaces" value="${(z.interfaces || []).join(", ")}" placeholder="eth2, vlan-dmz"></td>
        <td><input type="text" class="inline-input" id="zone-form-allows" value="${(z.allow_zones || []).join(", ")}" placeholder="wan"></td>
        <td>
            <label class="checkbox-container">
                <input type="checkbox" id="zone-form-isolate" ${z.isolate ? "checked" : ""}> Isolate
            </label>
        </td>
        <td>
            <label class="checkbox-container">
                <input type="checkbox" id="zone-form-masq" ${z.masquerade ? "checked" : ""}> NAT
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-zone-form-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-zone-form-btn">Cancel</button>
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
        if (zoneList && zoneList.length > 0) this.zones = zoneList;
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

        this.querySelectorAll(".edit-zone-btn").forEach(btn => {
            btn.onclick = () => this.showInlineEditRow(btn.dataset.id);
        });

        this.querySelectorAll(".delete-zone-btn").forEach(btn => {
            btn.onclick = () => {
                const id = btn.dataset.id;
                this.zones = this.zones.filter(z => z.id !== id);
                this.render();
                if (this.onSave) this.onSave(this.zones);
            };
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#zones-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineZoneFormTemplate({}, false);
        const addTr = temp.firstElementChild;
        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-zone-form-btn").onclick = () => {
            const id = addTr.querySelector("#zone-form-id").value.trim();
            const name = addTr.querySelector("#zone-form-name").value.trim();
            const ifacesStr = addTr.querySelector("#zone-form-interfaces").value.trim();
            const allowsStr = addTr.querySelector("#zone-form-allows").value.trim();
            const isolate = addTr.querySelector("#zone-form-isolate").checked;
            const masquerade = addTr.querySelector("#zone-form-masq").checked;

            if (!id || !name) { alert("Zone ID and Name are required."); return; }

            const interfaces = ifacesStr ? ifacesStr.split(",").map(s => s.trim()) : [];
            const allow_zones = allowsStr ? allowsStr.split(",").map(s => s.trim()) : [];

            this.zones.push({ id, name, interfaces, isolate, allow_zones, masquerade });
            this.render();
            if (this.onSave) this.onSave(this.zones);
        };

        addTr.querySelector("#cancel-zone-form-btn").onclick = () => addTr.remove();
    }

    showInlineEditRow(zoneId) {
        const targetRow = this.querySelector(`#zone-row-${zoneId}`);
        const zone = this.zones.find(z => z.id === zoneId);
        if (!targetRow || !zone) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineZoneFormTemplate(zone, true);
        const editTr = temp.firstElementChild;

        targetRow.style.display = "none";
        targetRow.parentNode.insertBefore(editTr, targetRow.nextSibling);

        editTr.querySelector("#save-zone-form-btn").onclick = () => {
            zone.name = editTr.querySelector("#zone-form-name").value.trim();
            const ifacesStr = editTr.querySelector("#zone-form-interfaces").value.trim();
            const allowsStr = editTr.querySelector("#zone-form-allows").value.trim();
            zone.isolate = editTr.querySelector("#zone-form-isolate").checked;
            zone.masquerade = editTr.querySelector("#zone-form-masq").checked;

            if (!zone.name) { alert("Zone Name is required."); return; }

            zone.interfaces = ifacesStr ? ifacesStr.split(",").map(s => s.trim()) : [];
            zone.allow_zones = allowsStr ? allowsStr.split(",").map(s => s.trim()) : [];

            this.render();
            if (this.onSave) this.onSave(this.zones);
        };

        editTr.querySelector("#cancel-zone-form-btn").onclick = () => {
            editTr.remove();
            targetRow.style.display = "";
        };
    }
}

if (!customElements.get("roost-network-zones")) {
    customElements.define("roost-network-zones", NetworkZonesComponent);
}
