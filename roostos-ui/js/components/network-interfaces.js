/**
 * NetworkInterfacesComponent - Web Component for Physical Network Ports and WAN Uplink Configuration
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderInterfacesTemplate = (interfacesCount, ifaceRowsHtml, wanConfigHtml) => html`
    <div class="network-interfaces-container">
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Physical Interfaces & Ports (${interfacesCount})</h3>
                    <p class="text-secondary" style="font-size:12px;">Hardware ethernet and wireless controllers</p>
                </div>
            </div>

            <div class="table-responsive">
                <table class="data-table" id="interfaces-table">
                    <thead>
                        <tr>
                            <th>Interface</th>
                            <th>Status</th>
                            <th>MAC Address</th>
                            <th>IP / CIDR</th>
                            <th>MTU</th>
                            <th>Speed / Duplex</th>
                            <th>Live Throughput</th>
                        </tr>
                    </thead>
                    <tbody id="interfaces-tbody">
                        ${ifaceRowsHtml}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <div class="card-header table-action-bar">
                <div>
                    <h3>WAN / Internet Uplink Configuration</h3>
                    <p class="text-secondary" style="font-size:12px;">Upstream provider routing and addressing mode</p>
                </div>
                <button class="btn btn-primary btn-sm" id="edit-wan-btn">Edit WAN Settings</button>
            </div>
            <div id="wan-config-container">
                ${wanConfigHtml}
            </div>
        </div>
    </div>
`;

const renderIfaceRowTemplate = (iface) => {
    const isUp = iface.status !== "down" && iface.status !== "DOWN";
    const statusBadge = isUp
        ? html`<span class="badge badge-success">UP</span>`
        : html`<span class="badge badge-danger">DOWN</span>`;
    return html`
        <tr id="iface-row-${iface.name}">
            <td><strong><code>${iface.name}</code></strong></td>
            <td>${statusBadge}</td>
            <td><code>${iface.mac || iface.hwaddr || "-"}</code></td>
            <td>${iface.ip ? html`<code>${iface.ip}</code>` : "<em>Unassigned</em>"}</td>
            <td>${iface.mtu || 1500}</td>
            <td><span class="badge badge-secondary">${iface.speed || "1000 Mbps"} ${iface.duplex || "Full"}</span></td>
            <td><span style="font-family: monospace; font-size: 11px;">Rx: ${window.formatSpeed(iface.rx_rate || 0)} | Tx: ${window.formatSpeed(iface.tx_rate || 0)}</span></td>
        </tr>
    `;
};

const renderWanViewTemplate = (wan) => html`
    <div class="grid-2-col" style="padding: 8px 0;">
        <div class="stat-item">
            <span class="stat-label">WAN Interface:</span>
            <span class="stat-value"><code>${wan.interface || "eth0"}</code></span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Connection Protocol:</span>
            <span class="stat-value"><span class="badge badge-info">${(wan.proto || "dhcp").toUpperCase()}</span></span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Assigned IP / Gateway:</span>
            <span class="stat-value"><code>${wan.ip || "192.168.100.45/24"}</code></span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Upstream DNS Servers:</span>
            <span class="stat-value"><code>${(wan.dns || ["1.1.1.1", "8.8.8.8"]).join(", ")}</code></span>
        </div>
    </div>
`;

const renderWanEditFormTemplate = (wan) => html`
    <form id="wan-edit-form" style="padding: 12px 0;">
        <div class="grid-2-col">
            <div class="form-group">
                <label>WAN Physical Interface</label>
                <input type="text" id="wan-input-interface" value="${wan.interface || "eth0"}">
            </div>
            <div class="form-group">
                <label>Connection Protocol</label>
                <select id="wan-input-proto">
                    <option value="dhcp" ${wan.proto === "dhcp" ? "selected" : ""}>DHCP (Automatic IP)</option>
                    <option value="static" ${wan.proto === "static" ? "selected" : ""}>Static IP</option>
                    <option value="pppoe" ${wan.proto === "pppoe" ? "selected" : ""}>PPPoE (DSL / Fiber)</option>
                </select>
            </div>
            <div class="form-group" id="wan-group-ip">
                <label>Static IP / Subnet (CIDR)</label>
                <input type="text" id="wan-input-ip" value="${wan.ip || ""}" placeholder="e.g. 192.168.100.45/24">
            </div>
            <div class="form-group" id="wan-group-gateway">
                <label>Default Gateway</label>
                <input type="text" id="wan-input-gateway" value="${wan.gateway || ""}" placeholder="e.g. 192.168.100.1">
            </div>
            <div class="form-group">
                <label>Custom MTU Override</label>
                <input type="number" id="wan-input-mtu" value="${wan.mtu || 1500}">
            </div>
            <div class="form-group">
                <label>DNS Overrides (comma separated)</label>
                <input type="text" id="wan-input-dns" value="${(wan.dns || []).join(", ")}" placeholder="1.1.1.1, 8.8.8.8">
            </div>
        </div>
        <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px;">
            <button type="button" class="btn btn-secondary" id="cancel-wan-edit-btn">Cancel</button>
            <button type="submit" class="btn btn-success" id="save-wan-edit-btn">Save WAN Settings</button>
        </div>
    </form>
`;

export class NetworkInterfacesComponent extends HTMLElement {
    constructor() {
        super();
        this.interfaces = [
            { name: "eth0", status: "up", mac: "52:54:00:12:34:56", ip: "192.168.100.45/24", mtu: 1500, speed: "1000 Mbps", duplex: "Full", rx_rate: 1048576, tx_rate: 262144 },
            { name: "eth1", status: "up", mac: "52:54:00:78:9a:bc", ip: "192.168.1.1/24", mtu: 1500, speed: "1000 Mbps", duplex: "Full", rx_rate: 524288, tx_rate: 1048576 },
            { name: "wlan0", status: "up", mac: "52:54:00:de:f0:12", ip: "", mtu: 1500, speed: "Wi-Fi 6", duplex: "Full", rx_rate: 131072, tx_rate: 65536 }
        ];
        this.wan = { interface: "eth0", proto: "dhcp", ip: "192.168.100.45/24", gateway: "192.168.100.1", dns: ["1.1.1.1", "8.8.8.8"], mtu: 1500 };
        this.isEditingWan = false;
    }

    setData(interfaces, wan) {
        if (interfaces && Array.isArray(interfaces)) this.interfaces = interfaces;
        if (wan) this.wan = wan;
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const ifaceRowsHtml = this.interfaces.map(i => renderIfaceRowTemplate(i)).join("");
        const wanConfigHtml = this.isEditingWan ? renderWanEditFormTemplate(this.wan) : renderWanViewTemplate(this.wan);

        this.innerHTML = renderInterfacesTemplate(this.interfaces.length, ifaceRowsHtml, wanConfigHtml);

        const editWanBtn = this.querySelector("#edit-wan-btn");
        if (editWanBtn) {
            editWanBtn.onclick = () => {
                this.isEditingWan = true;
                this.render();
            };
        }

        const cancelWanBtn = this.querySelector("#cancel-wan-edit-btn");
        if (cancelWanBtn) {
            cancelWanBtn.onclick = () => {
                this.isEditingWan = false;
                this.render();
            };
        }

        const wanForm = this.querySelector("#wan-edit-form");
        if (wanForm) {
            wanForm.onsubmit = (e) => {
                e.preventDefault();
                this.wan.interface = this.querySelector("#wan-input-interface").value.trim();
                this.wan.proto = this.querySelector("#wan-input-proto").value;
                this.wan.ip = this.querySelector("#wan-input-ip").value.trim();
                this.wan.gateway = this.querySelector("#wan-input-gateway").value.trim();
                this.wan.mtu = parseInt(this.querySelector("#wan-input-mtu").value, 10) || 1500;
                const dnsVal = this.querySelector("#wan-input-dns").value.trim();
                this.wan.dns = dnsVal ? dnsVal.split(",").map(s => s.trim()) : [];
                this.isEditingWan = false;
                this.render();
                if (this.onSaveWan) this.onSaveWan(this.wan);
            };
        }
    }
}

if (!customElements.get("roost-network-interfaces")) {
    customElements.define("roost-network-interfaces", NetworkInterfacesComponent);
}
