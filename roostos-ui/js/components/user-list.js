/**
 * UserListComponent - Web Component for Web Console User Accounts
 * Uses top-of-file module-scoped HTML template helpers tagged with html\`...\`
 * for full IDE syntax highlighting, auto-completion, and separation of UI templates from class logic.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderUserListTemplate = (count, rowsHtml) => html`
    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Console Operator Accounts (${count})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-user-btn">+ Add User</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="users-table">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Linked Member Profile</th>
                        <th>SSH Keys Count</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="users-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-user-btn">+ Add User</button>
        </div>
    </div>
`;

const renderUserRowTemplate = (u) => {
    const roleBadgeClass = u.role === "admin" ? "badge-success" : (u.role === "parent" ? "badge-primary" : "badge-secondary");
    return html`
        <tr id="user-row-${u.username}">
            <td><strong>${u.username}</strong></td>
            <td><span class="badge ${roleBadgeClass}">${u.role}</span></td>
            <td>${u.person ? html`<code>${u.person}</code>` : "<em>Unlinked</em>"}</td>
            <td><span class="badge">${(u.ssh_keys || []).length} keys</span></td>
            <td>
                <button class="btn btn-secondary btn-sm edit-user-btn" data-username="${u.username}">Edit</button>
                <button class="btn btn-danger btn-sm delete-user-btn" data-username="${u.username}">Delete</button>
            </td>
        </tr>
    `;
};

const renderInlineAddUserRowTemplate = (roles) => html`
    <tr class="inline-add-row">
        <td><input type="text" class="inline-input" id="add-user-username" placeholder="Username"></td>
        <td>
            <select class="inline-input" id="add-user-role">
                ${roles.map(r => html`<option value="${r}">${r.toUpperCase()}</option>`).join("")}
            </select>
        </td>
        <td><input type="text" class="inline-input" id="add-user-person" placeholder="Person ID (Optional)"></td>
        <td><em>0 keys</em></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm" id="save-inline-user-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-user-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class UserListComponent extends HTMLElement {
    constructor() {
        super();
        this.users = [];
        this.roles = ["admin", "parent", "member"];
    }

    setUsers(userList) {
        this.users = userList || [];
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const rowsHtml = this.users.length === 0
            ? html`<tr><td colspan="5" class="empty-state">No user accounts found. Click "+ Add User" to create one.</td></tr>`
            : this.users.map(u => renderUserRowTemplate(u)).join("");

        this.innerHTML = renderUserListTemplate(this.users.length, rowsHtml);

        this.querySelectorAll("#top-add-user-btn, #bottom-add-user-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#users-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineAddUserRowTemplate(this.roles);
        const addTr = tempContainer.firstElementChild;

        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-inline-user-btn").onclick = () => {
            const username = addTr.querySelector("#add-user-username").value.trim();
            const role = addTr.querySelector("#add-user-role").value;
            const person = addTr.querySelector("#add-user-person").value.trim() || null;

            if (!username) {
                alert("Username is required.");
                return;
            }

            const newUser = { username, role, person, ssh_keys: [] };
            this.users.push(newUser);
            this.render();
            if (this.onSave) this.onSave(this.users);
        };

        addTr.querySelector("#cancel-inline-user-btn").onclick = () => addTr.remove();
    }
}

if (!customElements.get("roost-user-list")) {
    customElements.define("roost-user-list", UserListComponent);
}
