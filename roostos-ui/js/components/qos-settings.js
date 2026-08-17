/**
 * QosSettingsComponent - Web Component for Smart Queue Management (SQM / Cake / FQ_CoDel)
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderQosTemplate = (qos) => html`
    <div class="qos-settings-container">
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Active Queue Management & Bufferbloat Mitigation (SQM)</h3>
                    <p class="text-secondary" style="font-size:12px;">Eliminate latency spikes under network load using Cake or FQ_CoDel</p>
                </div>
            </div>

            <form id="qos-form" style="padding: 12px 0;">
                <div class="grid-2-col">
                    <div class="form-group">
                        <label>Enable Traffic Shaping (QoS)</label>
                        <label class="checkbox-container">
                            <input type="checkbox" id="qos-enabled" ${qos.enabled ? "checked" : ""}> Enable SQM Bandwidth Management
                        </label>
                    </div>

                    <div class="form-group">
                        <label>Queueing Algorithm</label>
                        <select id="qos-algorithm">
                            <option value="cake" ${qos.algorithm === "cake" ? "selected" : ""}>CAKE (Common Applications Kept Enhanced)</option>
                            <option value="fq_codel" ${qos.algorithm === "fq_codel" ? "selected" : ""}>FQ_CoDel (Fair Queueing Controlled Delay)</option>
                            <option value="htb" ${qos.algorithm === "htb" ? "selected" : ""}>HTB (Hierarchical Token Bucket)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Download Bandwidth Limit (Mbps)</label>
                        <input type="number" id="qos-download" value="${qos.download_mbps || 1000}" placeholder="1000">
                    </div>

                    <div class="form-group">
                        <label>Upload Bandwidth Limit (Mbps)</label>
                        <input type="number" id="qos-upload" value="${qos.upload_mbps || 100}" placeholder="100">
                    </div>

                    <div class="form-group">
                        <label>Target WAN Interface</label>
                        <input type="text" id="qos-interface" value="${qos.interface || "eth0"}" placeholder="eth0">
                    </div>

                    <div class="form-group">
                        <label>DiffServ Priority Handling</label>
                        <select id="qos-diffserv">
                            <option value="diffserv4" ${qos.diffserv === "diffserv4" ? "selected" : ""}>Diffserv4 (Best Effort, Bulk, Video, Voice)</option>
                            <option value="diffserv3" ${qos.diffserv === "diffserv3" ? "selected" : ""}>Diffserv3 (Bulk, Best Effort, Voice)</option>
                            <option value="besteffort" ${qos.diffserv === "besteffort" ? "selected" : ""}>Best Effort Only (No Priority Classes)</option>
                        </select>
                    </div>
                </div>

                <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
                    <button type="submit" class="btn btn-success" id="save-qos-btn">Apply QoS Configuration</button>
                </div>
            </form>
        </div>
    </div>
`;

export class QosSettingsComponent extends HTMLElement {
    constructor() {
        super();
        this.qos = {
            enabled: true,
            algorithm: "cake",
            download_mbps: 1000,
            upload_mbps: 100,
            interface: "eth0",
            diffserv: "diffserv4"
        };
    }

    setQos(qosConfig) {
        if (qosConfig) this.qos = qosConfig;
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        this.innerHTML = renderQosTemplate(this.qos);

        const form = this.querySelector("#qos-form");
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.qos.enabled = this.querySelector("#qos-enabled").checked;
                this.qos.algorithm = this.querySelector("#qos-algorithm").value;
                this.qos.download_mbps = parseFloat(this.querySelector("#qos-download").value) || 0;
                this.qos.upload_mbps = parseFloat(this.querySelector("#qos-upload").value) || 0;
                this.qos.interface = this.querySelector("#qos-interface").value.trim() || "eth0";
                this.qos.diffserv = this.querySelector("#qos-diffserv").value;

                alert("QoS traffic shaping settings updated!");
                if (this.onSave) this.onSave(this.qos);
            };
        }
    }
}

if (!customElements.get("roost-qos-settings")) {
    customElements.define("roost-qos-settings", QosSettingsComponent);
}
