// RoostOS SysAdmin - Application Catalog & Container Deployments
import { api } from '../api.js';
import { renderCatalogSources } from './c1-admin-app-sources.js';
import { showInstallModal } from './c1-admin-app-modal.js';

let selectedCategory = 'all';
let searchQuery = '';

export async function renderAdminApps(container) {
    container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-muted);">Loading application catalog...</div>`;

    try {
        const [pluginsData, appsData, sourcesData] = await Promise.all([
            api.getPlugins().catch(() => ({ plugins: [] })),
            api.getCatalogApps().catch(() => []),
            api.getCatalogSources().catch(() => [])
        ]);

        const installedPlugins = pluginsData.plugins || [];
        const catalogApps = appsData || [];
        const catalogSources = sourcesData || [];

        renderAppsView(container, installedPlugins, catalogApps, catalogSources);
    } catch (err) {
        container.innerHTML = `<div class="c1-card" style="color: var(--accent-red);">Failed to load apps: ${err.message}</div>`;
    }
}

function renderAppsView(container, installedPlugins, catalogApps, catalogSources) {
    container.innerHTML = '';

    const header = document.createElement('div');
    header.className = 'c1-cockpit-header';
    header.innerHTML = `
        <div>
            <h1 class="c1-page-title">📦 Application Catalog & Containers</h1>
            <p class="c1-page-subtitle">Deploy self-hosted apps, edge proxies, and smart home containers on your cluster.</p>
        </div>
        <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" id="refresh-apps-btn">🔄 Refresh</button>
        </div>
    `;
    container.appendChild(header);

    // 1. Installed Containers Section
    const installedCard = document.createElement('div');
    installedCard.className = 'c1-card';
    installedCard.style.marginBottom = '20px';

    const installedRows = installedPlugins.length === 0
        ? `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">No containers currently deployed. Select an application below to deploy.</td></tr>`
        : installedPlugins.map(p => {
            const isRunning = p.enabled !== false;
            const containerInfo = (p.containers && p.containers[0]) || {};
            const ports = containerInfo.ports || [];
            const portStr = ports.map(pt => `${pt.host_port || pt.container_port}:${pt.container_port}`).join(', ') || 'Host/None';
            const openPort = ports[0]?.host_port || ports[0]?.container_port;
            const openUrl = openPort ? `http://${window.location.hostname}:${openPort}` : null;

            return `
                <tr data-plugin-id="${p.id}">
                    <td style="font-weight: 600;">
                        ${p.name || p.id}
                        <div style="font-size: 11px; color: var(--text-muted); font-family: monospace;">${containerInfo.image || p.id}</div>
                    </td>
                    <td>
                        <span class="badge ${isRunning ? 'badge-success' : 'badge-neutral'}">
                            ${isRunning ? '● Running' : '○ Stopped'}
                        </span>
                    </td>
                    <td><code style="font-size: 12px;">${portStr}</code></td>
                    <td>
                        ${openUrl ? `<a href="${openUrl}" target="_blank" class="btn btn-secondary btn-sm" style="font-size: 11px; text-decoration: none; padding: 2px 6px;">🔗 Open UI</a>` : '<span style="color: var(--text-muted); font-size: 11px;">Backend</span>'}
                    </td>
                    <td style="text-align: right; white-space: nowrap;">
                        <button class="btn btn-secondary btn-sm toggle-plugin-btn" data-id="${p.id}" data-enabled="${isRunning}">
                            ${isRunning ? '⏹ Stop' : '▶ Start'}
                        </button>
                        <button class="btn btn-secondary btn-sm delete-plugin-btn" data-id="${p.id}" style="color: var(--accent-red); margin-left: 4px;">
                            🗑️
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

    installedCard.innerHTML = `
        <h3 style="margin: 0 0 12px; font-size: 15px; font-weight: 700;">🚀 Active Deployed Containers</h3>
        <div class="c1-table-responsive">
            <table class="c1-table" style="width: 100%;">
                <thead>
                    <tr><th>Application / Image</th><th>Status</th><th>Port Mappings</th><th>Interface</th><th style="text-align: right;">Actions</th></tr>
                </thead>
                <tbody>${installedRows}</tbody>
            </table>
        </div>
    `;
    container.appendChild(installedCard);

    // 2. Catalog Section
    const catalogCard = document.createElement('div');
    catalogCard.className = 'c1-card';

    const categories = ['all', 'automation', 'media', 'privacy', 'tools', 'networking'];
    const catButtonsHtml = categories.map(cat => `
        <button class="btn btn-sm ${selectedCategory === cat ? 'btn-primary' : 'btn-secondary'} cat-filter-btn" data-category="${cat}" style="text-transform: capitalize;">
            ${cat}
        </button>
    `).join('');

    catalogCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
            <div>
                <h3 style="margin: 0; font-size: 15px; font-weight: 700;">🏪 Available Applications</h3>
                <p style="margin: 2px 0 0; font-size: 12px; color: var(--text-muted);">One-click verified container deployments with built-in networking.</p>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <input type="text" id="app-search-input" class="c1-input" placeholder="Search apps..." value="${searchQuery}" style="padding: 4px 10px; font-size: 12px; width: 180px;">
                <div style="display: flex; gap: 4px;">${catButtonsHtml}</div>
            </div>
        </div>
        <div id="catalog-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px;"></div>
    `;
    container.appendChild(catalogCard);

    const gridEl = catalogCard.querySelector('#catalog-grid');
    renderAppGridCards(gridEl, catalogApps, installedPlugins);

    // 3. Catalog Sources Section
    renderCatalogSources(container, catalogSources, () => renderAdminApps(container));

    // Bind Event Listeners
    container.querySelector('#refresh-apps-btn').onclick = () => renderAdminApps(container);

    const searchInput = catalogCard.querySelector('#app-search-input');
    searchInput.oninput = (e) => {
        searchQuery = e.target.value.toLowerCase();
        renderAppGridCards(gridEl, catalogApps, installedPlugins);
    };

    catalogCard.querySelectorAll('.cat-filter-btn').forEach(btn => {
        btn.onclick = () => {
            selectedCategory = btn.dataset.category;
            renderAdminApps(container);
        };
    });

    installedCard.querySelectorAll('.toggle-plugin-btn').forEach(btn => {
        btn.onclick = async () => {
            const pid = btn.dataset.id;
            const currentEnabled = btn.dataset.enabled === 'true';
            btn.disabled = true;
            try {
                await api.togglePlugin(pid, !currentEnabled);
                renderAdminApps(container);
            } catch (e) {
                alert(`Action failed: ${e.message}`);
                btn.disabled = false;
            }
        };
    });

    installedCard.querySelectorAll('.delete-plugin-btn').forEach(btn => {
        btn.onclick = async () => {
            const pid = btn.dataset.id;
            if (!confirm(`Are you sure you want to remove container application "${pid}"?`)) return;
            btn.disabled = true;
            try {
                await api.deletePlugin(pid);
                renderAdminApps(container);
            } catch (e) {
                alert(`Failed to delete plugin: ${e.message}`);
                btn.disabled = false;
            }
        };
    });
}

function renderAppGridCards(gridEl, catalogApps, installedPlugins) {
    const installedIds = new Set(installedPlugins.map(p => p.id));
    const filtered = catalogApps.filter(a => {
        const matchCat = selectedCategory === 'all' || (a.category && a.category.toLowerCase() === selectedCategory);
        const matchSearch = !searchQuery || a.name.toLowerCase().includes(searchQuery) || (a.description || '').toLowerCase().includes(searchQuery);
        return matchCat && matchSearch;
    });

    if (filtered.length === 0) {
        gridEl.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 32px;">No applications found matching criteria.</div>`;
        return;
    }

    gridEl.innerHTML = filtered.map(app => {
        const isInstalled = installedIds.has(app.id);
        const icon = getAppIcon(app.id, app.category);
        return `
            <div class="c1-card" style="border: 1px solid var(--border-color); display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 24px;">${icon}</span>
                            <div>
                                <h4 style="margin: 0; font-size: 14px; font-weight: 700;">${app.name}</h4>
                                <span class="badge badge-neutral" style="font-size: 10px; text-transform: uppercase;">${app.category || 'App'}</span>
                            </div>
                        </div>
                        ${isInstalled ? '<span class="badge badge-success" style="font-size: 10px;">Installed</span>' : ''}
                    </div>
                    <p style="font-size: 12px; color: var(--text-muted); margin: 6px 0 12px; min-height: 36px; line-height: 1.4;">
                        ${app.description || 'Containerized cluster service.'}
                    </p>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 10px; margin-top: 6px;">
                    <span style="font-size: 11px; color: var(--text-muted);">v${app.version || 'latest'}</span>
                    ${isInstalled
                        ? `<button class="btn btn-secondary btn-sm" disabled style="opacity: 0.6; font-size: 11px;">Installed</button>`
                        : `<button class="btn btn-primary btn-sm install-app-btn" data-id="${app.id}" style="font-size: 11px;">⬇️ Install</button>`
                    }
                </div>
            </div>
        `;
    }).join('');

    gridEl.querySelectorAll('.install-app-btn').forEach(btn => {
        btn.onclick = () => {
            const app = catalogApps.find(a => a.id === btn.dataset.id);
            if (app) showInstallModal(app, () => renderAdminApps(gridEl.closest('#view-mount-point') || gridEl.parentElement));
        };
    });
}

function getAppIcon(id, category) {
    const idLower = (id || '').toLowerCase();
    if (idLower.includes('plex') || idLower.includes('jellyfin')) return '🎬';
    if (idLower.includes('homeassistant') || idLower.includes('home-assistant')) return '🏠';
    if (idLower.includes('pihole') || idLower.includes('adguard')) return '🛡️';
    if (idLower.includes('vaultwarden') || idLower.includes('bitwarden')) return '🔐';
    if (idLower.includes('nextcloud')) return '☁️';
    if (idLower.includes('wireguard') || idLower.includes('tailscale')) return '🌐';
    if (category === 'media') return '📺';
    if (category === 'automation') return '🤖';
    if (category === 'privacy') return '🔒';
    if (category === 'networking') return '🔌';
    return '📦';
}
