/**
 * Cluster Templates - HTML template generators for Cluster Management UI.
 */

const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export const renderClusterOverviewTemplate = (status, tokenData, discovered) => {
    const role = status.role || (status.is_controller ? "controller" : "standalone");
    const roleBadge = role === "controller" ? "badge-success" : (role === "standalone" ? "badge-info" : "badge-secondary");
    
    return html`
        <div class="metrics-row">
            <div class="metric-card">
                <div class="metric-title">Cluster Mode</div>
                <div class="metric-value"><span class="badge ${roleBadge}" style="font-size: 16px; padding: 4px 10px;">${role.toUpperCase()}</span></div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Enrolled Nodes</div>
                <div class="metric-value">${status.registered_nodes_count || (status.nodes ? status.nodes.length : 1)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Controller URL</div>
                <div style="font-size: 14px; font-weight: 600; margin-top: 8px; word-break: break-all;">
                    ${status.controller_url || "<em>(Local Controller / Standalone)</em>"}
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom: 20px;">
            <div class="table-action-bar">
                <div>
                    <h3 style="margin-bottom: 4px;">Cluster Actions & Pairing</h3>
                    <p style="font-size: 13px; color: var(--text-secondary);">Manage cluster membership, generate pairing tokens for worker nodes, or discover local controllers.</p>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary btn-sm" id="discover-controllers-btn">Discover Controllers</button>
                    <button class="btn btn-primary btn-sm" id="gen-token-btn">Generate Join Token</button>
                </div>
            </div>

            ${tokenData ? html`
                <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 14px; margin-top: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <strong>Worker Node Pairing Token</strong>
                        <span class="badge badge-success">Valid for 10 minutes</span>
                    </div>
                    <p style="font-size: 13px; margin-bottom: 8px;">Run this command on a worker node or enter token in setup wizard:</p>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <code style="background: var(--bg-primary); padding: 8px 12px; border-radius: 6px; border: 1px solid var(--card-border); flex-grow: 1; font-size: 13px;">roostos join ${tokenData.token} --controller ${window.location.origin}</code>
                        <button class="btn btn-secondary btn-sm" id="copy-token-btn" data-token="${tokenData.token}">Copy Token</button>
                        <button class="btn btn-secondary btn-sm" id="dismiss-token-btn">Dismiss</button>
                    </div>
                </div>
            ` : ""}

            ${discovered && discovered.length > 0 ? html`
                <div style="background: rgba(6, 182, 212, 0.08); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: 8px; padding: 12px; margin-top: 12px;">
                    <strong>Discovered Local Controllers:</strong>
                    <ul style="margin: 8px 0 0 16px; font-size: 13px;">
                        ${discovered.map(c => html`<li>${c.name || "RoostOS"} (${c.ip}:${c.port || 8000})</li>`).join("")}
                    </ul>
                </div>
            ` : ""}
        </div>
    `;
};

export const renderClusterNodesTableTemplate = (count, rowsHtml) => html`
    <div class="card" style="margin-bottom: 20px;">
        <div class="card-header table-action-bar">
            <h3>Cluster Nodes (${count})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-node-btn">+ Add Node</button>
        </div>

        <div class="table-responsive">
            <table class="data-table" id="cluster-nodes-table">
                <thead>
                    <tr>
                        <th>Node ID</th>
                        <th>Name</th>
                        <th>Roles</th>
                        <th>Management IP</th>
                        <th>Status</th>
                        <th>OS Updates</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="cluster-nodes-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>

        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-node-btn">+ Add Node</button>
        </div>
    </div>
`;

export const renderNodeRowTemplate = (node, updateInfo, isLocalNode) => {
    const rolesHtml = (node.roles || ["gateway_router"]).map(r => 
        html`<span class="badge badge-secondary">${r}</span>`
    ).join(" ");

    let updatesBadge = html`<span class="badge badge-success">Up to date</span>`;
    if (updateInfo && updateInfo.upgradable > 0) {
        updatesBadge = html`<span class="badge badge-warning">${updateInfo.upgradable} updates${updateInfo.security_upgradable ? ` (${updateInfo.security_upgradable} sec)` : ""}</span>`;
    }

    return html`
        <tr id="node-row-${node.id}">
            <td><code>${node.id}</code> ${isLocalNode ? html`<span class="badge badge-outline">Local</span>` : ""}</td>
            <td><strong>${node.name}</strong></td>
            <td>${rolesHtml}</td>
            <td><code>${node.management_ip || "-"}</code></td>
            <td><span class="badge badge-online"><span class="pulse-dot" style="margin-right: 4px;"></span>Online</span></td>
            <td>${updatesBadge}</td>
            <td>
                <div style="display: flex; gap: 6px;">
                    <button class="btn btn-secondary btn-sm edit-node-btn" data-id="${node.id}">Edit</button>
                    ${updateInfo && updateInfo.upgradable > 0 ? html`
                        <button class="btn btn-primary btn-sm update-node-btn" data-id="${node.id}">Update</button>
                    ` : ""}
                    ${!isLocalNode ? html`
                        <button class="btn btn-danger btn-sm delete-node-btn" data-id="${node.id}">Remove</button>
                    ` : ""}
                </div>
            </td>
        </tr>
    `;
};

export const renderInlineNodeRowTemplate = (node = null) => {
    const isEdit = !!node;
    const rolesStr = node && node.roles ? node.roles.join(", ") : "compute";

    return html`
        <tr class="${isEdit ? 'inline-edit-row' : 'inline-add-row'}" id="${isEdit ? `edit-node-row-${node.id}` : 'inline-add-node-row'}">
            <td>
                ${isEdit 
                    ? html`<code>${node.id}</code><input type="hidden" id="node-form-id" value="${node.id}">`
                    : html`<input type="text" class="inline-input" id="node-form-id" placeholder="node-02">`
                }
            </td>
            <td><input type="text" class="inline-input" id="node-form-name" placeholder="e.g. Living Room Node" value="${node ? node.name : ''}"></td>
            <td><input type="text" class="inline-input" id="node-form-roles" placeholder="e.g. compute, storage" value="${rolesStr}"></td>
            <td><input type="text" class="inline-input" id="node-form-ip" placeholder="e.g. 192.168.1.50" value="${node && node.management_ip ? node.management_ip : ''}"></td>
            <td><em>Pending</em></td>
            <td><em>-</em></td>
            <td>
                <div class="inline-form-controls">
                    <button class="btn btn-success btn-sm" id="save-node-row-btn">Save</button>
                    <button class="btn btn-secondary btn-sm" id="cancel-node-row-btn">Cancel</button>
                </div>
            </td>
        </tr>
    `;
};

export const renderFleetUpdatesTemplate = (summary) => {
    if (!summary) return "";
    return html`
        <div class="card">
            <div class="card-header table-action-bar">
                <div>
                    <h3>Fleet OS Updates Summary</h3>
                    <p style="font-size: 13px; color: var(--text-secondary);">Centrally monitor and trigger operating system package updates across all nodes.</p>
                </div>
            </div>
            <div class="metrics-row" style="margin-top: 12px; margin-bottom: 0;">
                <div class="metric-card">
                    <div class="metric-title">Fleet Upgradable Packages</div>
                    <div class="metric-value">${summary.total_upgradable || 0}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Security Updates</div>
                    <div class="metric-value" style="color: ${summary.total_security_upgradable > 0 ? 'var(--accent-red)' : 'inherit'};">
                        ${summary.total_security_upgradable || 0}
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Nodes Requiring Reboot</div>
                    <div class="metric-value" style="color: ${(summary.reboot_required_nodes || []).length > 0 ? '#f59e0b' : 'inherit'};">
                        ${(summary.reboot_required_nodes || []).length}
                    </div>
                </div>
            </div>
        </div>
    `;
};
