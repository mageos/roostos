/**
 * Identity & Active Directory Plugin UI Extension
 * Provides Central User Directory management and Workstation Enrollment guides.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

const renderIdentityTemplate = (status, usersHtml, enrollmentInfo) => html`
    <div class="identity-plugin-container" style="display: flex; flex-direction: column; gap: 20px;">
        <div class="card">
            <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h2 style="margin:0;">Central Identity & Active Directory</h2>
                    <p style="margin:4px 0 0 0; color:var(--text-muted, #888); font-size:13px;">
                        Manage domain accounts and single sign-on credentials for all workstations on your network.
                    </p>
                </div>
                <span class="badge ${status.status === 'running' ? 'badge-success' : 'badge-warning'}" style="font-size:13px; padding:6px 12px;">
                    ● ${status.status.toUpperCase()} (${status.realm})
                </span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px;">
                <div class="stat-box" style="background:rgba(255,255,255,0.03); padding:12px 16px; border-radius:8px; border:1px solid var(--card-border, #333);">
                    <div style="font-size:12px; color:var(--text-muted, #888);">Active Directory Realm</div>
                    <div style="font-size:16px; font-weight:600; margin-top:4px;">${status.realm}</div>
                </div>
                <div class="stat-box" style="background:rgba(255,255,255,0.03); padding:12px 16px; border-radius:8px; border:1px solid var(--card-border, #333);">
                    <div style="font-size:12px; color:var(--text-muted, #888);">NetBIOS Workgroup</div>
                    <div style="font-size:16px; font-weight:600; margin-top:4px;">${status.workgroup}</div>
                </div>
                <div class="stat-box" style="background:rgba(255,255,255,0.03); padding:12px 16px; border-radius:8px; border:1px solid var(--card-border, #333);">
                    <div style="font-size:12px; color:var(--text-muted, #888);">Domain Controller</div>
                    <div style="font-size:16px; font-weight:600; margin-top:4px;">${status.dc_hostname}</div>
                </div>
                <div class="stat-box" style="background:rgba(255,255,255,0.03); padding:12px 16px; border-radius:8px; border:1px solid var(--card-border, #333);">
                    <div style="font-size:12px; color:var(--text-muted, #888);">Total Domain Users</div>
                    <div style="font-size:16px; font-weight:600; margin-top:4px;">${status.user_count}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header table-action-bar" style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0;">Domain Accounts</h3>
                <button class="btn btn-primary btn-sm" id="top-add-domain-user-btn">+ Add Domain User</button>
            </div>

            <div class="table-responsive" style="margin-top:12px;">
                <table class="data-table" id="domain-users-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Full Name</th>
                            <th>Role</th>
                            <th>Linked Person</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="domain-users-tbody">
                        ${usersHtml}
                    </tbody>
                </table>
            </div>

            <div class="card-footer table-action-bar" style="margin-top:12px; display:flex; justify-content:flex-end;">
                <button class="btn btn-primary btn-sm" id="bottom-add-domain-user-btn">+ Add Domain User</button>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3 style="margin:0;">Workstation Enrollment (Join Domain)</h3>
            </div>
            <div style="margin-top:12px;">
                <p style="font-size:13px; color:var(--text-muted, #888); margin-bottom:8px;">
                    Run this command on any Linux workstation (Ubuntu, Debian, Arch Linux, Fedora) to join this RoostOS domain:
                </p>
                <div style="position:relative; background:#1e1e1e; padding:12px; border-radius:6px; font-family:monospace; font-size:13px; color:#4af626; overflow-x:auto;">
                    <code>${enrollmentInfo.enrollment_command}</code>
                </div>

                <p style="font-size:13px; color:var(--text-muted, #888); margin-top:16px; margin-bottom:8px;">
                    For Windows workstations, navigate to <strong>System Properties &gt; Computer Name &gt; Change...</strong> and set Domain to:
                </p>
                <div style="background:#1e1e1e; padding:8px 12px; border-radius:6px; font-family:monospace; font-size:13px; display:inline-block;">
                    <strong>${enrollmentInfo.realm}</strong>
                </div>
            </div>
        </div>
    </div>
`;

const renderDomainUserRow = (u) => html`
    <tr id="domain-user-row-${u.username}">
        <td><strong>${u.username}</strong></td>
        <td>${[u.first_name, u.last_name].filter(Boolean).join(" ") || "-"}</td>
        <td><span class="badge ${u.role === 'admin' ? 'badge-success' : 'badge-secondary'}">${u.role}</span></td>
        <td>${u.person ? html`<code>${u.person}</code>` : "<em>Unlinked</em>"}</td>
        <td><span class="badge ${u.enabled ? 'badge-success' : 'badge-danger'}">${u.enabled ? 'Active' : 'Disabled'}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-domain-user-btn" data-username="${u.username}">Edit</button>
            <button class="btn btn-warning btn-sm reset-pwd-btn" data-username="${u.username}">Password</button>
            <button class="btn btn-danger btn-sm delete-domain-user-btn" data-username="${u.username}">Delete</button>
        </td>
    </tr>
`;

const renderInlineAddDomainUserRow = (roles) => html`
    <tr class="inline-add-row" style="background:rgba(255,255,255,0.05);">
        <td><input type="text" class="inline-input" id="add-domain-username" placeholder="Username (e.g. john)" style="width:100%;"></td>
        <td><input type="text" class="inline-input" id="add-domain-fullname" placeholder="First Last" style="width:100%;"></td>
        <td>
            <select class="inline-input" id="add-domain-role">
                ${roles.map(r => html`<option value="${r}">${r.toUpperCase()}</option>`).join("")}
            </select>
        </td>
        <td><input type="text" class="inline-input" id="add-domain-person" placeholder="Person ID" style="width:100%;"></td>
        <td><input type="password" class="inline-input" id="add-domain-password" placeholder="Password" style="width:100%;"></td>
        <td>
            <div class="inline-form-controls" style="display:flex; gap:6px;">
                <button class="btn btn-success btn-sm" id="save-inline-domain-user-btn">Save</button>
                <button class="btn btn-secondary btn-sm" id="cancel-inline-domain-user-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export class IdentityPluginComponent extends HTMLElement {
    constructor() {
        super();
        this.status = {
            realm: "ROOSTOS.LOCAL",
            workgroup: "ROOSTOS",
            dc_hostname: "roost-dc",
            provider: "samba_ad",
            status: "running",
            user_count: 0
        };
        this.users = [];
        this.roles = ["admin", "parent", "member"];
        this.enrollmentInfo = {
            realm: "ROOSTOS.LOCAL",
            enrollment_command: "curl -sSf http://roost.lan/api/v1/identity/join.sh | sudo bash"
        };
    }

    async connectedCallback() {
        await this.loadData();
        this.render();
    }

    async loadData() {
        try {
            const [statusRes, usersRes, enrollRes] = await Promise.all([
                fetch("/api/v1/identity/status"),
                fetch("/api/v1/identity/users"),
                fetch("/api/v1/identity/enrollment-info")
            ]);
            if (statusRes.ok) this.status = await statusRes.json();
            if (usersRes.ok) this.users = await usersRes.json();
            if (enrollRes.ok) this.enrollmentInfo = await enrollRes.json();
        } catch (e) {
            console.warn("Could not fetch domain status via API:", e);
        }
    }

    render() {
        const usersHtml = this.users.length === 0
            ? html`<tr><td colspan="6" class="empty-state" style="text-align:center; padding:18px;">No domain accounts found. Click "+ Add Domain User" to provision one.</td></tr>`
            : this.users.map(u => renderDomainUserRow(u)).join("");

        this.innerHTML = renderIdentityTemplate(this.status, usersHtml, this.enrollmentInfo);

        this.querySelectorAll("#top-add-domain-user-btn, #bottom-add-domain-user-btn").forEach(btn => {
            btn.onclick = () => this.showInlineAddRow();
        });

        this.querySelectorAll(".delete-domain-user-btn").forEach(btn => {
            btn.onclick = async (e) => {
                const user = e.target.dataset.username;
                if (confirm(`Delete domain user ${user}?`)) {
                    await fetch(`/api/v1/identity/users/${user}`, { method: "DELETE" });
                    await this.loadData();
                    this.render();
                }
            };
        });

        this.querySelectorAll(".reset-pwd-btn").forEach(btn => {
            btn.onclick = async (e) => {
                const user = e.target.dataset.username;
                const newPwd = prompt(`Enter new password for domain user ${user}:`);
                if (newPwd) {
                    await fetch(`/api/v1/identity/users/${user}/password`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ new_password: newPwd })
                    });
                    alert(`Password reset for ${user}`);
                }
            };
        });
    }

    showInlineAddRow() {
        const tbody = this.querySelector("#domain-users-tbody");
        if (!tbody || tbody.querySelector(".inline-add-row")) return;

        const tempContainer = document.createElement("tbody");
        tempContainer.innerHTML = renderInlineAddDomainUserRow(this.roles);
        const addTr = tempContainer.firstElementChild;
        tbody.insertBefore(addTr, tbody.firstChild);

        addTr.querySelector("#save-inline-domain-user-btn").onclick = async () => {
            const username = addTr.querySelector("#add-domain-username").value.trim();
            const fullName = addTr.querySelector("#add-domain-fullname").value.trim();
            const role = addTr.querySelector("#add-domain-role").value;
            const person = addTr.querySelector("#add-domain-person").value.trim() || null;
            const password = addTr.querySelector("#add-domain-password").value;

            if (!username || !password) {
                alert("Username and password are required.");
                return;
            }

            const names = fullName.split(" ");
            const first_name = names[0] || null;
            const last_name = names.slice(1).join(" ") || null;

            await fetch("/api/v1/identity/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, first_name, last_name, role, person, password })
            });

            await this.loadData();
            this.render();
        };

        addTr.querySelector("#cancel-inline-domain-user-btn").onclick = () => addTr.remove();
    }
}

if (!customElements.get("roost-identity-plugin")) {
    customElements.define("roost-identity-plugin", IdentityPluginComponent);
}

if (window.RoostOS && typeof window.RoostOS.registerExtension === "function") {
    window.RoostOS.registerExtension({
        id: "identity-ad",
        title: "Central Identity",
        render(containerEl) {
            containerEl.innerHTML = `<roost-identity-plugin></roost-identity-plugin>`;
        }
    });
}
