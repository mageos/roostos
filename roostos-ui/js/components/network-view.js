/**
 * NetworkViewComponent - Orchestrating Container for Network Administration Sub-Panels
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderNetworkViewTemplate = () => html`
    <div id="networks-view" class="view-pane active">
        <!-- Sub-Tabs Navigation -->
        <div class="sub-tab-nav" id="network-subtabs-bar">
            <button class="sub-tab-btn active" data-subtab="interfaces">Interfaces & WAN</button>
            <button class="sub-tab-btn" data-subtab="bridges">Bridges & VLANs</button>
            <button class="sub-tab-btn" data-subtab="zones">Network Zones</button>
            <button class="sub-tab-btn" data-subtab="wifi">Wi-Fi Access Points</button>
            <button class="sub-tab-btn" data-subtab="dhcp">DHCP & Leases</button>
            <button class="sub-tab-btn" data-subtab="qos">QoS & Shaping</button>
        </div>

        <!-- Sub-Tab Content Panes -->
        <div class="sub-tab-content-container">
            <div class="sub-tab-pane active" id="pane-interfaces">
                <roost-network-interfaces id="net-interfaces-comp"></roost-network-interfaces>
            </div>
            <div class="sub-tab-pane" id="pane-bridges" style="display: none;">
                <roost-network-bridges id="net-bridges-comp"></roost-network-bridges>
            </div>
            <div class="sub-tab-pane" id="pane-zones" style="display: none;">
                <roost-network-zones id="net-zones-comp"></roost-network-zones>
            </div>
            <div class="sub-tab-pane" id="pane-wifi" style="display: none;">
                <roost-wifi-management id="net-wifi-comp"></roost-wifi-management>
            </div>
            <div class="sub-tab-pane" id="pane-dhcp" style="display: none;">
                <roost-dhcp-management id="net-dhcp-comp"></roost-dhcp-management>
            </div>
            <div class="sub-tab-pane" id="pane-qos" style="display: none;">
                <roost-qos-settings id="net-qos-comp"></roost-qos-settings>
            </div>
        </div>
    </div>
`;

export class NetworkViewComponent extends HTMLElement {
    constructor() {
        super();
        this.activeSubtab = "interfaces";
    }

    connectedCallback() {
        this.render();
    }

    render() {
        this.innerHTML = renderNetworkViewTemplate();
        this.bindSubtabs();
        this.bindChildEvents();
    }

    bindSubtabs() {
        const buttons = this.querySelectorAll(".sub-tab-btn");
        buttons.forEach(btn => {
            btn.onclick = () => {
                const subtab = btn.dataset.subtab;
                this.switchSubtab(subtab);
            };
        });
    }

    switchSubtab(subtabName) {
        this.activeSubtab = subtabName;
        this.querySelectorAll(".sub-tab-btn").forEach(btn => {
            if (btn.dataset.subtab === subtabName) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        const panes = ["interfaces", "bridges", "zones", "wifi", "dhcp", "qos"];
        panes.forEach(name => {
            const pane = this.querySelector(`#pane-${name}`);
            if (pane) {
                pane.style.display = name === subtabName ? "block" : "none";
                if (name === subtabName) pane.classList.add("active");
                else pane.classList.remove("active");
            }
        });
    }

    bindChildEvents() {
        const interfacesComp = this.querySelector("#net-interfaces-comp");
        if (interfacesComp) {
            interfacesComp.onSaveWan = async (wanData) => {
                await this.persistNetworkConfig();
            };
        }

        const bridgesComp = this.querySelector("#net-bridges-comp");
        if (bridgesComp) {
            bridgesComp.onSave = async () => {
                await this.persistNetworkConfig();
            };
        }

        const zonesComp = this.querySelector("#net-zones-comp");
        if (zonesComp) {
            zonesComp.onSave = async () => {
                await this.persistNetworkConfig();
            };
        }

        const wifiComp = this.querySelector("#net-wifi-comp");
        if (wifiComp) {
            wifiComp.onSave = async () => {
                await this.persistNetworkConfig();
            };
        }

        const dhcpComp = this.querySelector("#net-dhcp-comp");
        if (dhcpComp) {
            dhcpComp.onSave = async () => {
                await this.persistNetworkConfig();
            };
        }

        const qosComp = this.querySelector("#net-qos-comp");
        if (qosComp) {
            qosComp.onSave = async () => {
                await this.persistNetworkConfig();
            };
        }
    }

    async persistNetworkConfig() {
        if (!window.networkService) return;
        try {
            const bridgesComp = this.querySelector("#net-bridges-comp");
            const zonesComp = this.querySelector("#net-zones-comp");
            const wifiComp = this.querySelector("#net-wifi-comp");
            const qosComp = this.querySelector("#net-qos-comp");

            const networkPayload = {
                ...(window.networkSettings || {}),
                bridges: bridgesComp ? bridgesComp.bridges : [],
                vlans: bridgesComp ? bridgesComp.vlans : [],
                zones: zonesComp ? zonesComp.zones : [],
                qos: qosComp ? qosComp.qos : {}
            };

            const wifiPayload = {
                ...(window.wifiSettings || {}),
                access_points: wifiComp ? wifiComp.accessPoints : []
            };

            await window.networkService.saveConfig(networkPayload, wifiPayload, window.vpnSettings || []);
        } catch (e) {
            console.error("Failed to save network configuration:", e);
        }
    }
}

if (!customElements.get("roost-network-view")) {
    customElements.define("roost-network-view", NetworkViewComponent);
}
