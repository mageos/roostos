/**
 * DeviceListComponent - Web Component for Network Device Management
 * Uses top-of-file module-scoped HTML template helpers tagged with html\`...\`
 * for full IDE syntax highlighting, auto-completion, and separation of UI templates from class logic.
 */

// Tagged template literal helper enabling IDE HTML syntax highlighting & formatting
const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

// Top-of-file module-scoped HTML template generator
const renderDeviceListTemplate = (devicesCount, rowsHtml) => html`
    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Registered Devices (${devicesCount})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-device-btn">+ Register Device</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="devices-table">
                <thead>
                    <tr>
                        <th>MAC Address</th>
                        <th>Name</th>
                        <th>Owner</th>
                        <th>Location</th>
                        <th>Static IP</th>
                        <th>Tags</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="devices-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-device-btn">+ Register Device</button>
        </div>
    </div>
`;

const renderDeviceRowTemplate = (d) => html`
    <tr id="device-row-${d.mac}">
        <td><code>${d.mac}</code></td>
        <td><strong>${d.name}</strong></td>
        <td>${d.owner ? html`<code>${d.owner}</code>` : "<em>Unassigned</em>"}</td>
        <td>${d.location || "<em>Unset</em>"}</td>
        <td>${d.static_ip ? html`<code>${d.static_ip}</code>` : "<em>DHCP Dynamic</em>"}</td>
        <td>${(d.tags || []).map(t => html`<span class="badge badge-secondary">${t}</span>`).join(" ")}</td>
        <td>
            <button class="btn btn-secondary btn-sm edit-device-btn" data-mac="${d.mac}">Edit</button>
            <button class="btn btn-danger btn-sm delete-device-btn" data-mac="${d.mac}">Delete</button>
        </td>
    </tr>
`;

const renderInlineAddDeviceRowTemplate = () => html`
    <tr class="inline-add-row">
        <td><input type="text" class="inline-input" id="add-device-mac" placeholder="a4:83:e7:12:34:56"></td>
        <td><input type="text" class="inline-input" id="add-device-name" placeholder="Device Name"></td>
        <td><input type="text" class="inline-input" id="add-device-owner" placeholder="Owner ID"></td>
        <td><input type="text" class="inline-input" id="add-device-location" placeholder="Location ID"></td>
        <td><input type="text" class="inline-input" id="add-device-ip" placeholder="Static IP (Optional)"></td>
        <td><input type="text" class="inline-input" id="add-device-tags" placeholder="personal, work"></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-device-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-device-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class DeviceListComponent extends HTMLElement {
    constructor() {
        super();
        this.devices = [];
    }

    setDevices(deviceList) {
        this.devices = deviceList || [];
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const rowsHtml = this.devices.length === 0
            ? html`<tr><td colspan="7" class="empty-state">No devices registered. Click "+ Register Device" to add one.</td></tr>`
            : this.devices.map(d => renderDeviceRowTemplate(d)).join("");

        this.innerHTML = renderDeviceListTemplate(this.devices.length, rowsHtml);

        this.querySelectorAll("#top-add-device-btn, #bottom-add-device-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#devices-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineAddDeviceRowTemplate();
        const addTr = tempContainer.firstElementChild;

        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-inline-device-btn").onclick = () => {
            const mac = addTr.querySelector("#add-device-mac").value.trim();
            const name = addTr.querySelector("#add-device-name").value.trim();
            const owner = addTr.querySelector("#add-device-owner").value.trim() || null;
            const location = addTr.querySelector("#add-device-location").value.trim() || null;
            const static_ip = addTr.querySelector("#add-device-ip").value.trim() || null;
            const tagsStr = addTr.querySelector("#add-device-tags").value.trim();

            if (!mac || !name) {
                alert("MAC Address and Name are required.");
                return;
            }

            const tags = tagsStr ? tagsStr.split(",").map(t => t.trim()) : [];
            const newDev = { mac, name, owner, location, static_ip, tags };
            this.devices.push(newDev);
            this.render();
            if (this.onSave) this.onSave(this.devices);
        };

        addTr.querySelector("#cancel-inline-device-btn").onclick = () => addTr.remove();
    }
}

if (!customElements.get("roost-device-list")) {
    customElements.define("roost-device-list", DeviceListComponent);
}
