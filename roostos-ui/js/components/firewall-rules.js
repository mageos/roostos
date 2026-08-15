/**
 * FirewallRulesComponent - Web Component for Firewall Input Rules and NAT Port Forwarding
 * Uses top-of-file module-scoped HTML template helpers tagged with html\`...\`
 * for full IDE syntax highlighting, auto-completion, and separation of UI templates from class logic.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderFirewallRulesTemplate = (count, rowsHtml) => html`
    <div class="card" style="margin-bottom: 20px;">
        <div class="card-header table-action-bar">
            <h3>Inbound Firewall Rules (${count})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-rule-btn">+ Add Rule</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="firewall-rules-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Interface / Zone</th>
                        <th>Protocol</th>
                        <th>Port</th>
                        <th>Source Filter</th>
                        <th>Action</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="rules-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-rule-btn">+ Add Rule</button>
        </div>
    </div>
`;

const renderRuleRowTemplate = (r) => {
    const actionBadge = r.action === "accept" ? "badge-success" : "badge-danger";
    return html`
        <tr id="rule-row-${r.name}">
            <td><strong>${r.name}</strong></td>
            <td><span class="badge badge-secondary">${r.interface || "*"}</span></td>
            <td><code>${(r.protocol || "tcp").toUpperCase()}</code></td>
            <td><code>${r.port}</code></td>
            <td>${r.source ? html`<code>${r.source}</code>` : "<em>Any Source</em>"}</td>
            <td><span class="badge ${actionBadge}">${(r.action || "accept").toUpperCase()}</span></td>
            <td><span class="badge ${r.enabled !== false ? "badge-success" : "badge-secondary"}">${r.enabled !== false ? "Enabled" : "Disabled"}</span></td>
            <td>
                <button class="btn btn-secondary btn-sm edit-rule-btn" data-name="${r.name}">Edit</button>
                <button class="btn btn-danger btn-sm delete-rule-btn" data-name="${r.name}">Delete</button>
            </td>
        </tr>
    `;
};

const renderInlineAddRuleRowTemplate = () => html`
    <tr class="inline-add-row">
        <td><input type="text" class="inline-input" id="add-rule-name" placeholder="Rule Name"></td>
        <td><input type="text" class="inline-input" id="add-rule-iface" placeholder="eth0, wan, lan, *"></td>
        <td>
            <select class="inline-input" id="add-rule-proto">
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
                <option value="tcp/udp">TCP/UDP</option>
            </select>
        </td>
        <td><input type="number" class="inline-input" id="add-rule-port" placeholder="22"></td>
        <td><input type="text" class="inline-input" id="add-rule-source" placeholder="192.168.1.0/24 (Optional)"></td>
        <td>
            <select class="inline-input" id="add-rule-action">
                <option value="accept">ACCEPT</option>
                <option value="drop">DROP</option>
            </select>
        </td>
        <td>
            <label class="checkbox-container"><input type="checkbox" id="add-rule-enabled" checked> Enable</label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-rule-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-rule-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class FirewallRulesComponent extends HTMLElement {
    constructor() {
        super();
        this.rules = [];
        this.portForwards = [];
    }

    setRules(rulesList, portForwardsList) {
        this.rules = rulesList || [];
        this.portForwards = portForwardsList || [];
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const rowsHtml = this.rules.length === 0
            ? html`<tr><td colspan="8" class="empty-state">No firewall input rules configured. Click "+ Add Rule" to create one.</td></tr>`
            : this.rules.map(r => renderRuleRowTemplate(r)).join("");

        this.innerHTML = renderFirewallRulesTemplate(this.rules.length, rowsHtml);

        this.querySelectorAll("#top-add-rule-btn, #bottom-add-rule-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#rules-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineAddRuleRowTemplate();
        const addTr = tempContainer.firstElementChild;

        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-inline-rule-btn").onclick = () => {
            const name = addTr.querySelector("#add-rule-name").value.trim();
            const iface = addTr.querySelector("#add-rule-iface").value.trim() || "*";
            const protocol = addTr.querySelector("#add-rule-proto").value;
            const port = parseInt(addTr.querySelector("#add-rule-port").value, 10);
            const source = addTr.querySelector("#add-rule-source").value.trim() || null;
            const action = addTr.querySelector("#add-rule-action").value;
            const enabled = addTr.querySelector("#add-rule-enabled").checked;

            if (!name || isNaN(port)) {
                alert("Rule Name and Port are required.");
                return;
            }

            const newRule = { name, interface: iface, protocol, port, source, action, enabled };
            this.rules.push(newRule);
            this.render();
            if (this.onSave) this.onSave(this.rules);
        };

        addTr.querySelector("#cancel-inline-rule-btn").onclick = () => addTr.remove();
    }
}

if (!customElements.get("roost-firewall-rules")) {
    customElements.define("roost-firewall-rules", FirewallRulesComponent);
}
