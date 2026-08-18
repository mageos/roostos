/**
 * WifiManagementComponent - Web Component for Wi-Fi Access Points, Radios & Mesh Configuration
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderWifiTemplate = (apCount, apRowsHtml) => html`
    <div class="wifi-management-container">
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Wi-Fi Access Points & SSIDs (${apCount})</h3>
                    <p class="text-secondary" style="font-size:12px;">Wireless broadcast profiles and radio frequency assignments</p>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-primary btn-sm" id="top-add-ap-btn">+ Add Wi-Fi AP</button>
                </div>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="wifi-ap-table">
                    <thead>
                        <tr>
                            <th>SSID</th>
                            <th>Radio / Band</th>
                            <th>Security</th>
                            <th>Channel / Width</th>
                            <th>Bridge Target</th>
                            <th>Isolation</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="wifi-ap-tbody">
                        ${apRowsHtml}
                    </tbody>
                </table>
            </div>

            <div class="card-footer table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm" id="bottom-add-ap-btn">+ Add Wi-Fi AP</button>
            </div>
        </div>
    </div>
`;

const renderApRowTemplate = (ap) => html`
    <tr id="ap-row-${ap.ssid}">
        <td><strong>${ap.ssid}</strong></td>
        <td><span class="badge badge-info">${ap.radio || "wlan0 (5GHz)"}</span></td>
        <td><code>${(ap.security || "wpa2-psk").toUpperCase()}</code></td>
        <td>${ap.channel || "Auto"} (${ap.channel_width || "80MHz"})</td>
        <td><code>${ap.bridge || "br0"}</code></td>
        <td><span class="badge ${ap.isolate ? "badge-danger" : "badge-outline"}">${ap.isolate ? "Isolated" : "Bridged"}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-ap-btn" data-ssid="${ap.ssid}">Edit</button>
            <button class="btn btn-danger btn-sm delete-ap-btn" data-ssid="${ap.ssid}">Delete</button>
        </td>
    </tr>
`;

const renderInlineApFormTemplate = (ap = {}, isEdit = false) => html`
    <tr class="${isEdit ? "inline-edit-row" : "inline-add-row"}" id="${isEdit ? `edit-ap-row-${ap.ssid}` : "inline-add-ap-row"}">
        <td><input type="text" class="inline-input" id="ap-form-ssid" value="${ap.ssid || ""}" placeholder="SSID Name"></td>
        <td>
            <select class="inline-input" id="ap-form-radio">
                <option value="wlan0 (5GHz)" ${ap.radio && ap.radio.includes("5GHz") ? "selected" : ""}>wlan0 (5 GHz AX)</option>
                <option value="wlan1 (2.4GHz)" ${ap.radio && ap.radio.includes("2.4GHz") ? "selected" : ""}>wlan1 (2.4 GHz N/AX)</option>
                <option value="wlan2 (6GHz)" ${ap.radio && ap.radio.includes("6GHz") ? "selected" : ""}>wlan2 (6 GHz Wi-Fi 6E)</option>
            </select>
        </td>
        <td>
            <select class="inline-input" id="ap-form-security">
                <option value="wpa2-psk" ${ap.security === "wpa2-psk" ? "selected" : ""}>WPA2-PSK</option>
                <option value="wpa3-sae" ${ap.security === "wpa3-sae" ? "selected" : ""}>WPA3-SAE</option>
                <option value="wpa2/wpa3" ${ap.security === "wpa2/wpa3" ? "selected" : ""}>WPA2/WPA3 Mixed</option>
                <option value="open" ${ap.security === "open" ? "selected" : ""}>Open (No password)</option>
            </select>
        </td>
        <td>
            <input type="text" class="inline-input" id="ap-form-channel" value="${ap.channel || "Auto"}" placeholder="Channel (e.g. 36)">
        </td>
        <td>
            <input type="text" class="inline-input" id="ap-form-bridge" value="${ap.bridge || "br0"}" placeholder="br0">
        </td>
        <td>
            <label class="checkbox-container">
                <input type="checkbox" id="ap-form-isolate" ${ap.isolate ? "checked" : ""}> Isolate
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-ap-form-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-ap-form-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class WifiManagementComponent extends HTMLElement {
    constructor() {
        super();
        this.accessPoints = [
            { ssid: "Roost-Home", radio: "wlan0 (5GHz)", security: "wpa3-sae", passphrase: "", channel: "36", channel_width: "80MHz", bridge: "br0", isolate: false },
            { ssid: "Roost-IoT", radio: "wlan1 (2.4GHz)", security: "wpa2-psk", passphrase: "", channel: "6", channel_width: "20MHz", bridge: "br0", isolate: true },
            { ssid: "Roost-Guest", radio: "wlan0 (5GHz)", security: "wpa2-psk", passphrase: "", channel: "149", channel_width: "80MHz", bridge: "br-guest", isolate: true }
        ];
    }

    setAccessPoints(aps) {
        if (aps && Array.isArray(aps)) this.accessPoints = aps;
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const rowsHtml = this.accessPoints.map(ap => renderApRowTemplate(ap)).join("");
        this.innerHTML = renderWifiTemplate(this.accessPoints.length, rowsHtml);

        this.querySelectorAll("#top-add-ap-btn, #bottom-add-ap-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });

        this.querySelectorAll(".edit-ap-btn").forEach(btn => {
            btn.onclick = () => this.showInlineEditRow(btn.dataset.ssid);
        });

        this.querySelectorAll(".delete-ap-btn").forEach(btn => {
            btn.onclick = () => {
                const ssid = btn.dataset.ssid;
                this.accessPoints = this.accessPoints.filter(a => a.ssid !== ssid);
                this.render();
                if (this.onSave) this.onSave(this.accessPoints);
            };
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#wifi-ap-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineApFormTemplate({}, false);
        const addTr = temp.firstElementChild;
        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-ap-form-btn").onclick = () => {
            const ssid = addTr.querySelector("#ap-form-ssid").value.trim();
            const radio = addTr.querySelector("#ap-form-radio").value;
            const security = addTr.querySelector("#ap-form-security").value;
            const channel = addTr.querySelector("#ap-form-channel").value.trim() || "Auto";
            const bridge = addTr.querySelector("#ap-form-bridge").value.trim() || "br0";
            const isolate = addTr.querySelector("#ap-form-isolate").checked;

            if (!ssid) { alert("SSID name is required."); return; }

            this.accessPoints.push({ ssid, radio, security, channel, channel_width: "80MHz", bridge, isolate });
            this.render();
            if (this.onSave) this.onSave(this.accessPoints);
        };

        addTr.querySelector("#cancel-ap-form-btn").onclick = () => addTr.remove();
    }

    showInlineEditRow(ssid) {
        const targetRow = this.querySelector(`#ap-row-${ssid}`);
        const ap = this.accessPoints.find(a => a.ssid === ssid);
        if (!targetRow || !ap) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineApFormTemplate(ap, true);
        const editTr = temp.firstElementChild;

        targetRow.style.display = "none";
        targetRow.parentNode.insertBefore(editTr, targetRow.nextSibling);

        editTr.querySelector("#save-ap-form-btn").onclick = () => {
            const newSsid = editTr.querySelector("#ap-form-ssid").value.trim();
            if (!newSsid) { alert("SSID name is required."); return; }

            ap.ssid = newSsid;
            ap.radio = editTr.querySelector("#ap-form-radio").value;
            ap.security = editTr.querySelector("#ap-form-security").value;
            ap.channel = editTr.querySelector("#ap-form-channel").value.trim() || "Auto";
            ap.bridge = editTr.querySelector("#ap-form-bridge").value.trim() || "br0";
            ap.isolate = editTr.querySelector("#ap-form-isolate").checked;

            this.render();
            if (this.onSave) this.onSave(this.accessPoints);
        };

        editTr.querySelector("#cancel-ap-form-btn").onclick = () => {
            editTr.remove();
            targetRow.style.display = "";
        };
    }
}

if (!customElements.get("roost-wifi-management")) {
    customElements.define("roost-wifi-management", WifiManagementComponent);
}
