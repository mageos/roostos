// RoostOS SysAdmin - Catalog Sources Sub-panel
import { api } from '../api.js';

export function renderCatalogSources(container, sources = [], onSourcesChanged = () => {}) {
    const wrapper = document.createElement('div');
    wrapper.className = 'c1-card';
    wrapper.style.marginTop = '20px';

    const renderRows = () => {
        if (!sources || sources.length === 0) {
            return `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">No catalog sources configured. Add one below.</td></tr>`;
        }
        return sources.map(s => `
            <tr data-source-id="${s.id}">
                <td style="font-weight: 600;">${s.name || s.id}</td>
                <td><code style="font-size: 11px;">${s.id}</code></td>
                <td><span style="font-size: 12px; color: var(--text-muted);">${s.url}</span></td>
                <td>
                    <span class="badge ${s.enabled ? 'badge-success' : 'badge-neutral'}" style="font-size: 11px;">
                        ${s.enabled ? 'Active' : 'Disabled'}
                    </span>
                </td>
                <td style="text-align: right;">
                    <button class="btn btn-secondary btn-sm delete-source-btn" data-id="${s.id}" style="color: var(--accent-red); padding: 2px 8px;">
                        🗑️
                    </button>
                </td>
            </tr>
        `).join('');
    };

    wrapper.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div>
                <h3 style="margin: 0; font-size: 15px; font-weight: 700;">📦 Catalog Sources & Repositories</h3>
                <p style="margin: 2px 0 0; font-size: 12px; color: var(--text-muted);">Decentralized git and remote manifest feeds for containerized apps.</p>
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn btn-secondary btn-sm" id="refresh-sources-btn" title="Re-fetch remote manifests">
                    🔄 Sync Feeds
                </button>
                <button class="btn btn-primary btn-sm" id="top-add-source-btn">
                    + Add Repository
                </button>
            </div>
        </div>

        <div class="c1-table-responsive">
            <table class="c1-table" style="width: 100%;">
                <thead>
                    <tr>
                        <th>Repository</th>
                        <th>Identifier</th>
                        <th>URL / Endpoint</th>
                        <th>Status</th>
                        <th style="text-align: right;">Actions</th>
                    </tr>
                </thead>
                <tbody id="catalog-sources-tbody">
                    ${renderRows()}
                </tbody>
            </table>
        </div>

        <div style="margin-top: 10px; display: flex; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" id="bottom-add-source-btn">
                + Add Repository
            </button>
        </div>
    `;

    container.appendChild(wrapper);

    const tbody = wrapper.querySelector('#catalog-sources-tbody');

    const showInlineAddRow = (atTop = true) => {
        if (tbody.querySelector('.inline-add-source-row')) return;
        const tr = document.createElement('tr');
        tr.className = 'inline-add-source-row';
        tr.style.background = 'var(--bg-card-hover, rgba(255,255,255,0.03))';
        tr.innerHTML = `
            <td><input type="text" class="c1-input input-name" placeholder="Official Apps" style="padding: 4px 8px; font-size: 12px; width: 100%;"></td>
            <td><input type="text" class="c1-input input-id" placeholder="roostos-official" style="padding: 4px 8px; font-size: 12px; width: 100%;"></td>
            <td><input type="text" class="c1-input input-url" placeholder="https://github.com/mageos/roostos-apps.git" style="padding: 4px 8px; font-size: 12px; width: 100%;"></td>
            <td><span class="badge badge-success" style="font-size: 11px;">Active</span></td>
            <td style="text-align: right; white-space: nowrap;">
                <button class="btn btn-primary btn-sm save-new-source-btn" style="padding: 3px 8px; font-size: 11px;">Save</button>
                <button class="btn btn-secondary btn-sm cancel-new-source-btn" style="padding: 3px 8px; font-size: 11px;">✕</button>
            </td>
        `;

        if (atTop) tbody.insertBefore(tr, tbody.firstChild);
        else tbody.appendChild(tr);

        tr.querySelector('.cancel-new-source-btn').onclick = () => tr.remove();
        tr.querySelector('.save-new-source-btn').onclick = async () => {
            const name = tr.querySelector('.input-name').value.trim();
            const id = tr.querySelector('.input-id').value.trim();
            const url = tr.querySelector('.input-url').value.trim();
            if (!id || !url) return alert('Repository Identifier and URL are required.');

            try {
                await api.addCatalogSource({ id, name: name || id, url, enabled: true });
                onSourcesChanged();
            } catch (e) {
                alert(`Failed to add catalog source: ${e.message}`);
            }
        };
    };

    wrapper.querySelector('#top-add-source-btn').onclick = () => showInlineAddRow(true);
    wrapper.querySelector('#bottom-add-source-btn').onclick = () => showInlineAddRow(false);

    wrapper.querySelector('#refresh-sources-btn').onclick = async () => {
        const btn = wrapper.querySelector('#refresh-sources-btn');
        btn.disabled = true;
        btn.textContent = '⏳ Syncing...';
        try {
            await api.refreshCatalogs();
            onSourcesChanged();
        } catch (e) {
            alert(`Failed to sync catalogs: ${e.message}`);
        } finally {
            btn.disabled = false;
            btn.textContent = '🔄 Sync Feeds';
        }
    };

    tbody.querySelectorAll('.delete-source-btn').forEach(btn => {
        btn.onclick = async () => {
            const sid = btn.dataset.id;
            if (!confirm(`Are you sure you want to remove catalog source "${sid}"?`)) return;
            try {
                await api.deleteCatalogSource(sid);
                onSourcesChanged();
            } catch (e) {
                alert(`Failed to delete source: ${e.message}`);
            }
        };
    });
}
