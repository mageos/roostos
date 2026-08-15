/**
 * PeopleListComponent - Web Component for Household Members Management
 * Uses top-of-file module-scoped HTML template helpers tagged with html\`...\`
 * for full IDE syntax highlighting, auto-completion, and separation of UI templates from class logic.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderPeopleListTemplate = (count, rowsHtml) => html`
    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Household Members (${count})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-person-btn">+ Add Member</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="people-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>DNS Filter Profile</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="people-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-person-btn">+ Add Member</button>
        </div>
    </div>
`;

const renderPersonRowTemplate = (p) => html`
    <tr id="person-row-${p.id}">
        <td><code>${p.id}</code></td>
        <td><strong>${p.name}</strong></td>
        <td><span class="badge badge-info">${p.dns_profile || "Default"}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-person-btn" data-id="${p.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-person-btn" data-id="${p.id}">Delete</button>
        </td>
    </tr>
`;

const renderInlineAddPersonRowTemplate = (dnsProfiles) => html`
    <tr class="inline-add-row">
        <td><input type="text" class="inline-input" id="add-person-id" placeholder="e.g. alice_profile"></td>
        <td><input type="text" class="inline-input" id="add-person-name" placeholder="e.g. Alice"></td>
        <td>
            <select class="inline-input" id="add-person-dns">
                ${dnsProfiles.map(dp => html`<option value="${dp}">${dp}</option>`).join("")}
            </select>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-person-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-person-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class PeopleListComponent extends HTMLElement {
    constructor() {
        super();
        this.people = [];
        this.dnsProfiles = ["Default", "Kids-Safe", "Strict-Filter", "No-Filter"];
    }

    connectedCallback() {
        this.render();
    }

    setPeople(peopleList) {
        this.people = peopleList || [];
        this.render();
    }

    render() {
        const rowsHtml = this.people.length === 0
            ? html`<tr><td colspan="4" class="empty-state">No household members registered. Click "+ Add Member" to register one.</td></tr>`
            : this.people.map(p => renderPersonRowTemplate(p)).join("");

        this.innerHTML = renderPeopleListTemplate(this.people.length, rowsHtml);

        this.querySelectorAll("#top-add-person-btn, #bottom-add-person-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#people-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineAddPersonRowTemplate(this.dnsProfiles);
        const addTr = tempContainer.firstElementChild;

        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-inline-person-btn").onclick = async () => {
            const id = addTr.querySelector("#add-person-id").value.trim();
            const name = addTr.querySelector("#add-person-name").value.trim();
            const dns_profile = addTr.querySelector("#add-person-dns").value;

            if (!id || !name) {
                alert("ID and Name are required.");
                return;
            }

            const newPerson = { id, name, dns_profile };
            this.people.push(newPerson);
            this.render();
            if (this.onSave) this.onSave(this.people);
        };

        addTr.querySelector("#cancel-inline-person-btn").onclick = () => addTr.remove();
    }
}

if (!customElements.get("roost-people-list")) {
    customElements.define("roost-people-list", PeopleListComponent);
}
