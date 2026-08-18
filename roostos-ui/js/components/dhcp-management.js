/**
 * DhcpManagementComponent - Web Component for DHCP Server, Static Reservations and Active Leases
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderDhcpTemplate = (resCount, resRowsHtml, leaseCount, leaseRowsHtml, dhcpConfig) => html`
    <div class="dhcp-management-container">
        <!-- DHCP Settings Summary Card -->
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header table-action-bar">
                <div>
                    <h3>DHCP Server Scope & Pool</h3>
                    <p class="text-secondary" style="font-size:12px;">Dynamic host allocation range and lease lifecycle</p>
                </div>
            </div>
            <div class="grid-3-col" style="padding: 6px 0;">
                <div class="stat-item">
                    <span class="stat-label">Subnet Gateway:</span>
                    <span class="stat-value"><code>${dhcpConfig.gateway || "192.168.1.1"}</code></span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Pool Range:</span>
                    <span class="stat-value"><code>${dhcpConfig.pool_start || "192.168.1.100"} - ${dhcpConfig.pool_end || "192.168.1.250"}</code></span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Lease Duration:</span>
                    <span class="stat-value"><code>${dhcpConfig.lease_time || "86400s (24h)"}</code></span>
                </div>
            </div>
        </div>

        <!-- Static Reservations Table -->
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Static DHCP Reservations (${resCount})</h3>
                    <p class="text-secondary" style="font-size:12px;">Fixed IP bindings by device MAC address</p>
                </div>
                <button class="btn btn-primary btn-sm" id="top-add-res-btn">+ Add Reservation</button>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="reservations-table">
                    <thead>
                        <tr>
                            <th>MAC Address</th>
                            <th>Reserved IP</th>
                            <th>Hostname</th>
                            <th>Description</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="reservations-tbody">
                        ${resRowsHtml}
                    </tbody>
                </table>
            </div>

            <div class="card-footer table-action-bar" style="margin-top: 12px;">
                <span></span>
                <button class="btn btn-primary btn-sm" id="bottom-add-res-btn">+ Add Reservation</button>
            </div>
        </div>

        <!-- Active Leases Table -->
        <div class="card">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Active Dynamic Leases (${leaseCount})</h3>
                    <p class="text-secondary" style="font-size:12px;">Currently allocated client IP addresses</p>
                </div>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="leases-table">
                    <thead>
                        <tr>
                            <th>IP Address</th>
                            <th>MAC Address</th>
                            <th>Hostname</th>
                            <th>Expires In</th>
                        </tr>
                    </thead>
                    <tbody id="leases-tbody">
                        ${leaseRowsHtml}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
`;

const renderReservationRowTemplate = (r) => html`
    <tr id="res-row-${r.mac.replace(/:/g, '')}">
        <td><code>${r.mac}</code></td>
        <td><strong><code>${r.ip}</code></strong></td>
        <td>${r.hostname || "<em>Unset</em>"}</td>
        <td>${r.description || "-"}</td>
        <td>
            <button class="btn btn-secondary btn-sm edit-res-btn" data-mac="${r.mac}">Edit</button>
            <button class="btn btn-danger btn-sm delete-res-btn" data-mac="${r.mac}">Delete</button>
        </td>
    </tr>
`;

const renderInlineReservationFormTemplate = (r = {}, isEdit = false) => html`
    <tr class="${isEdit ? "inline-edit-row" : "inline-add-row"}" id="${isEdit ? `edit-res-row-${r.mac.replace(/:/g, '')}` : "inline-add-res-row"}">
        <td><input type="text" class="inline-input" id="res-form-mac" value="${r.mac || ""}" ${isEdit ? "disabled" : ""} placeholder="a4:83:e7:12:34:56"></td>
        <td><input type="text" class="inline-input" id="res-form-ip" value="${r.ip || ""}" placeholder="192.168.1.50"></td>
        <td><input type="text" class="inline-input" id="res-form-host" value="${r.hostname || ""}" placeholder="living-room-tv"></td>
        <td><input type="text" class="inline-input" id="res-form-desc" value="${r.description || ""}" placeholder="Smart TV"></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-res-form-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-res-form-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

const renderLeaseRowTemplate = (l) => html`
    <tr>
        <td><strong><code>${l.ip}</code></strong></td>
        <td><code>${l.mac}</code></td>
        <td>${l.hostname || "<em>Unknown</em>"}</td>
        <td><span class="badge badge-info">${l.expires || "23h 12m"}</span></td>
    </tr>
`;

export class DhcpManagementComponent extends HTMLElement {
    constructor() {
        super();
        this.dhcpConfig = { gateway: "192.168.1.1", pool_start: "192.168.1.100", pool_end: "192.168.1.250", lease_time: "86400s (24h)" };
        this.reservations = [
            { mac: "52:54:00:11:22:33", ip: "192.168.1.10", hostname: "server-nas", description: "Home NAS Storage" },
            { mac: "52:54:00:44:55:66", ip: "192.168.1.20", hostname: "living-room-apple-tv", description: "Apple TV" }
        ];
        this.leases = [
            { ip: "192.168.1.105", mac: "a4:83:e7:99:88:77", hostname: "iphone-matt", expires: "18h 45m" },
            { ip: "192.168.1.142", mac: "b2:c3:d4:ee:ff:01", hostname: "kindle-paperwhite", expires: "22h 10m" }
        ];
    }

    setData(reservations, leases, config) {
        if (reservations) this.reservations = reservations;
        if (leases) this.leases = leases;
        if (config) this.dhcpConfig = config;
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const resRowsHtml = this.reservations.length === 0
            ? html`<tr><td colspan="5" class="empty-state">No static reservations registered.</td></tr>`
            : this.reservations.map(r => renderReservationRowTemplate(r)).join("");

        const leaseRowsHtml = this.leases.length === 0
            ? html`<tr><td colspan="4" class="empty-state">No active DHCP leases currently allocated.</td></tr>`
            : this.leases.map(l => renderLeaseRowTemplate(l)).join("");

        this.innerHTML = renderDhcpTemplate(this.reservations.length, resRowsHtml, this.leases.length, leaseRowsHtml, this.dhcpConfig);

        this.querySelectorAll("#top-add-res-btn, #bottom-add-res-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });

        this.querySelectorAll(".edit-res-btn").forEach(btn => {
            btn.onclick = () => this.showInlineEditRow(btn.dataset.mac);
        });

        this.querySelectorAll(".delete-res-btn").forEach(btn => {
            btn.onclick = () => {
                const mac = btn.dataset.mac;
                this.reservations = this.reservations.filter(r => r.mac !== mac);
                this.render();
                if (this.onSave) this.onSave(this.reservations);
            };
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#reservations-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineReservationFormTemplate({}, false);
        const addTr = temp.firstElementChild;
        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-res-form-btn").onclick = () => {
            const mac = addTr.querySelector("#res-form-mac").value.trim();
            const ip = addTr.querySelector("#res-form-ip").value.trim();
            const hostname = addTr.querySelector("#res-form-host").value.trim();
            const description = addTr.querySelector("#res-form-desc").value.trim();

            if (!mac || !ip) { alert("MAC Address and IP are required."); return; }

            this.reservations.push({ mac, ip, hostname, description });
            this.render();
            if (this.onSave) this.onSave(this.reservations);
        };

        addTr.querySelector("#cancel-res-form-btn").onclick = () => addTr.remove();
    }

    showInlineEditRow(mac) {
        const cleanMac = mac.replace(/:/g, '');
        const targetRow = this.querySelector(`#res-row-${cleanMac}`);
        const res = this.reservations.find(r => r.mac === mac);
        if (!targetRow || !res) return;

        const temp = document.createElement("tbody");
        temp.innerHTML = renderInlineReservationFormTemplate(res, true);
        const editTr = temp.firstElementChild;

        targetRow.style.display = "none";
        targetRow.parentNode.insertBefore(editTr, targetRow.nextSibling);

        editTr.querySelector("#save-res-form-btn").onclick = () => {
            const ip = editTr.querySelector("#res-form-ip").value.trim();
            const hostname = editTr.querySelector("#res-form-host").value.trim();
            const description = editTr.querySelector("#res-form-desc").value.trim();

            if (!ip) { alert("IP address is required."); return; }

            res.ip = ip;
            res.hostname = hostname;
            res.description = description;

            this.render();
            if (this.onSave) this.onSave(this.reservations);
        };

        editTr.querySelector("#cancel-res-form-btn").onclick = () => {
            editTr.remove();
            targetRow.style.display = "";
        };
    }
}

if (!customElements.get("roost-dhcp-management")) {
    customElements.define("roost-dhcp-management", DhcpManagementComponent);
}
