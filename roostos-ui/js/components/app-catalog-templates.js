/**
 * AppCatalogTemplates - HTML Template helpers for RoostOS App Catalog
 */

export const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export const renderCatalogTemplate = (activeTab, counts, bodyHtml) => html`
    <div class="view-tabs-header" style="margin-bottom: 20px;">
        <button class="tab-btn ${activeTab === 'apps' ? 'active' : ''}" data-tab="apps">
            Applications (${counts.apps})
        </button>
        <button class="tab-btn ${activeTab === 'sources' ? 'active' : ''}" data-tab="sources">
            Repositories (${counts.sources})
        </button>
        <button class="tab-btn ${activeTab === 'images' ? 'active' : ''}" data-tab="images">
            Local Images (${counts.images})
        </button>
    </div>
    <div class="catalog-content-container">
        ${bodyHtml}
    </div>
`;

export const renderAppsGridTemplate = (apps, selectedCategory, categories) => html`
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
            ${categories.map(c => html`
                <button class="btn btn-sm ${selectedCategory === c ? 'btn-primary' : 'btn-secondary'} category-filter-btn" data-category="${c}">
                    ${c.charAt(0).toUpperCase() + c.slice(1)}
                </button>
            `).join("")}
        </div>
        <button class="btn btn-secondary btn-sm" id="refresh-catalogs-btn">↻ Refresh Repositories</button>
    </div>
    ${apps.length === 0 ? html`
        <div class="card" style="text-align:center; padding:32px; color:var(--text-secondary);">
            <p>No applications found matching the selected category.</p>
        </div>
    ` : html`
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:16px;">
            ${apps.map(app => renderAppCardTemplate(app)).join("")}
        </div>
    `}
`;

export const renderAppCardTemplate = (app) => html`
    <div class="card" style="display:flex; flex-direction:column; justify-content:space-between; height:100%;">
        <div>
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div style="width:40px; height:40px; border-radius:8px; background:rgba(59,130,246,0.1); display:flex; align-items:center; justify-content:center; font-size:20px;">
                        ${app.icon_url ? html`<img src="${app.icon_url}" style="width:28px; height:28px; object-fit:contain;" alt="${app.name}"/>` : "📦"}
                    </div>
                    <div>
                        <h4 style="margin:0; font-size:16px; font-weight:600;">${app.name}</h4>
                        <span style="font-size:12px; color:var(--text-secondary);">v${app.version} • ${app.author || 'RoostOS'}</span>
                    </div>
                </div>
                <span class="badge badge-info">${app.category}</span>
            </div>
            <p style="font-size:13px; color:var(--text-secondary); line-height:1.5; margin-bottom:12px;">
                ${app.description}
            </p>
        </div>
        <div>
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; font-size:11px;">
                ${(app.container.ports || []).map(p => html`
                    <span class="badge badge-outline">Port ${p.host_port}:${p.container_port}</span>
                `).join("")}
                ${(app.container.volumes || []).map(v => html`
                    <span class="badge badge-outline">${v.container_path}</span>
                `).join("")}
                <span class="badge badge-secondary">${app.container.pull_policy}</span>
            </div>
            <button class="btn btn-primary btn-sm install-app-btn" style="width:100%;" data-id="${app.id}">
                Deploy / Install
            </button>
        </div>
    </div>
`;

export const renderSourcesTemplate = (sources, rowsHtml) => html`
    <div class="card">
        <div class="card-header table-action-bar">
            <div>
                <h3>Catalog Repositories (${sources.length})</h3>
                <p style="margin:4px 0 0; font-size:12px; color:var(--text-secondary);">
                    APT-style catalog feeds. Supports local directories (file://), LAN, and verified HTTPS mirrors.
                </p>
            </div>
            <div style="display:flex; gap:8px;">
                <button class="btn btn-secondary btn-sm" id="refresh-sources-btn">↻ Refresh Indexes</button>
                <button class="btn btn-primary btn-sm" id="top-add-source-btn">+ Add Repository</button>
            </div>
        </div>
        <div class="table-responsive">
            <table class="data-table" id="sources-table">
                <thead>
                    <tr>
                        <th>Identifier</th>
                        <th>Name</th>
                        <th>URL / Path</th>
                        <th>Signature Verification</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="sources-tbody">
                    ${rowsHtml}
                </tbody>
            </table>
        </div>
        <div class="card-footer table-action-bar" style="margin-top:12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-source-btn">+ Add Repository</button>
        </div>
    </div>
`;

export const renderSourceRowTemplate = (s) => html`
    <tr id="source-row-${s.id}">
        <td><code>${s.id}</code></td>
        <td><strong>${s.name}</strong></td>
        <td><code style="word-break:break-all;">${s.url}</code></td>
        <td>
            ${s.signing_key ? html`
                <span class="badge badge-success" title="${s.signing_key}">✓ Ed25519 Enforced</span>
            ` : html`
                <span class="badge badge-outline">Unsigned</span>
            `}
        </td>
        <td>
            <span class="badge ${s.enabled ? 'badge-success' : 'badge-secondary'}">
                ${s.enabled ? 'Enabled' : 'Disabled'}
            </span>
        </td>
        <td>
            <button class="btn btn-secondary btn-sm edit-source-btn" data-id="${s.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-source-btn" data-id="${s.id}">Delete</button>
        </td>
    </tr>
`;

export const renderInlineSourceRowTemplate = (s = {}) => html`
    <tr class="inline-add-row" ${s.id ? `id="edit-row-${s.id}"` : ''}>
        <td><input type="text" class="inline-input src-id-input" placeholder="e.g. community" value="${s.id || ''}" ${s.id ? 'disabled' : ''}></td>
        <td><input type="text" class="inline-input src-name-input" placeholder="e.g. Community Catalog" value="${s.name || ''}"></td>
        <td><input type="text" class="inline-input src-url-input" placeholder="file:///opt/apps or https://..." value="${s.url || ''}"></td>
        <td><input type="text" class="inline-input src-key-input" placeholder="Optional Ed25519 PubKey hex" value="${s.signing_key || ''}"></td>
        <td>
            <label style="font-size:12px; display:flex; align-items:center; gap:4px; cursor:pointer;">
                <input type="checkbox" class="src-enabled-input" ${s.enabled !== false ? 'checked' : ''}> Active
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-source-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-source-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export const renderImagesTemplate = (images) => html`
    <div class="card" style="margin-bottom:20px;">
        <div class="card-header">
            <h3>Air-Gapped Local Docker Image Deployment</h3>
            <p style="margin:4px 0 0; font-size:12px; color:var(--text-secondary);">
                Upload local Docker image archives (.tar) to deploy containers without connecting to Docker Hub or external registries.
            </p>
        </div>
        <div style="display:flex; gap:12px; align-items:center; margin-top:16px; flex-wrap:wrap;">
            <input type="file" id="docker-image-file" accept=".tar,.tar.gz" class="input-field" style="max-width:320px;">
            <button class="btn btn-primary btn-sm" id="upload-image-btn">Upload & Load to Docker</button>
            <span id="upload-status" style="font-size:13px; color:var(--text-secondary);"></span>
        </div>
    </div>
    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Loaded Local Images (${images.length})</h3>
            <button class="btn btn-secondary btn-sm" id="refresh-images-btn">↻ Refresh</button>
        </div>
        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Repository</th>
                        <th>Tag</th>
                        <th>Image ID</th>
                        <th>Size</th>
                    </tr>
                </thead>
                <tbody>
                    ${images.length === 0 ? html`
                        <tr><td colspan="4" class="empty-state">No local images loaded yet.</td></tr>
                    ` : images.map(img => html`
                        <tr>
                            <td><strong>${img.repository}</strong></td>
                            <td><span class="badge badge-info">${img.tag}</span></td>
                            <td><code>${(img.id || '').slice(0, 12)}</code></td>
                            <td>${img.size || '-'}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    </div>
`;
