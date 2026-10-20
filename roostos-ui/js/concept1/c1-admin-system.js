// Concept 1: SysAdmin Console - System Updates, Maintenance & Declarative Configuration
import { store } from '../state.js';
import { api } from '../api.js';
import { renderClusterFleet } from './c1-admin-cluster-fleet.js';

let activeYaml = 'network.yaml';
let updateState = null; // { checking, installing, result, error }

export function renderAdminSystem(container) {
    const data = store.data;
    const admin = data.admin;

    const updateInfo = updateState?.result || null;
    const updatesAvailable = updateInfo?.updates_available ?? false;
    const secCount = updateInfo?.security_updates_count ?? 0;
    const allCount = updateInfo?.total_updates_count ?? (updateInfo?.packages?.length || 0);

    container.innerHTML = `
        <!-- Multi-Node Cluster Fleet Mount Point -->
        <div id="cluster-fleet-mount"></div>

        <!-- OS & Security Updates and Router Maintenance -->
        <div class="card" style="border-left: 4px solid var(--accent-amber);">
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">🛡️ OS Updates & Router Maintenance</h3>
                    <p class="card-subtitle">Keep Debian base system, kernel, security patches, and router services up to date</p>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="badge ${updatesAvailable ? (secCount > 0 ? 'badge-danger' : 'badge-warning') : 'badge-success'}">
                        ${updatesAvailable ? `● ${allCount} Update(s) Pending` : '● Up to Date'}
                    </span>
                </div>
            </div>

            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center;">
                <button class="btn btn-primary btn-sm" id="btn-check-updates" ${updateState?.checking ? 'disabled' : ''}>
                    ${updateState?.checking ? '⏳ Checking Repositories...' : '🔍 Check for Updates'}
                </button>
                <button class="btn btn-success btn-sm" id="btn-install-all-updates" ${(!updatesAvailable || updateState?.installing) ? 'disabled' : ''}>
                    ${updateState?.installing ? '⏳ Installing...' : '⬇️ Install All Updates'}
                </button>
                <button class="btn btn-secondary btn-sm" id="btn-install-sec-updates" ${(!updatesAvailable || secCount === 0 || updateState?.installing) ? 'disabled' : ''}>
                    🛡️ Install Security Only (${secCount})
                </button>
                <button class="btn btn-danger btn-sm" id="btn-reboot-router" style="margin-left:auto;">
                    🔄 Reboot Router
                </button>
            </div>

            ${updateState?.installMessage ? `
                <div style="padding: 10px 14px; border-radius: var(--radius-md); background: var(--bg-subtle); border-left: 4px solid var(--accent-emerald); font-size: 12px; margin-bottom: 14px;">
                    <strong>✓ Update Result:</strong> ${updateState.installMessage}
                </div>
            ` : ''}

            ${updateState?.error ? `
                <div style="padding: 10px 14px; border-radius: var(--radius-md); background: var(--bg-subtle); border-left: 4px solid var(--accent-amber); font-size: 12px; margin-bottom: 14px;">
                    <strong>⚠ Error:</strong> ${updateState.error}
                </div>
            ` : ''}

            ${updateInfo?.packages && updateInfo.packages.length > 0 ? `
                <div class="table-responsive">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Package Name</th>
                                <th>Current Version</th>
                                <th>Candidate Version</th>
                                <th>Classification</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${updateInfo.packages.map(p => `
                                <tr>
                                    <td><strong>${p.name}</strong></td>
                                    <td><code>${p.current_version || '-'}</code></td>
                                    <td><code style="color:var(--brand-primary);">${p.candidate_version}</code></td>
                                    <td>
                                        <span class="badge ${p.is_security ? 'badge-danger' : 'badge-neutral'}">
                                            ${p.is_security ? '🛡️ Security Patch' : 'Enhancement'}
                                        </span>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            ` : ''}
        </div>

        <!-- Declarative Configuration Inspector -->
        <div class="card">
            <div class="card-header" style="flex-wrap: wrap; gap: 10px;">
                <div>
                    <h3 class="card-title">📄 Declarative Configuration (/etc/roostos/)</h3>
                    <p class="card-subtitle">GitOps-ready YAML schemas controlling network, devices, users, and schedules</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-copy-yaml">📋 Copy YAML</button>
            </div>

            <div class="c1-nav-tabs" style="margin-bottom: 12px;">
                ${['network.yaml', 'system.yaml', 'devices.yaml', 'firewall.yaml', 'schedules.yaml', 'plugins.yaml'].map(f => `
                    <button class="c1-nav-link yaml-tab ${activeYaml === f ? 'active' : ''}" data-file="${f}">
                        ${f}
                    </button>
                `).join('')}
            </div>

            <div class="c2-yaml-viewer" id="yaml-code-display">${(admin.yamlFiles && admin.yamlFiles[activeYaml]) || '# Declarative configuration files\n# Location: /etc/roostos/'}</div>
        </div>
    `;

    const fleetMount = container.querySelector('#cluster-fleet-mount');
    if (fleetMount) {
        renderClusterFleet(fleetMount, () => renderAdminSystem(container));
    }

    container.querySelector('#btn-check-updates')?.addEventListener('click', async () => {
        updateState = { checking: true };
        renderAdminSystem(container);
        try {
            const res = await api.checkUpdates();
            updateState = { result: res };
        } catch (err) {
            updateState = { error: String(err) };
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-install-all-updates')?.addEventListener('click', async () => {
        if (!confirm('Install all pending OS packages and updates now?')) return;
        updateState = { ...updateState, installing: true };
        renderAdminSystem(container);
        try {
            const res = await api.installUpdates(false);
            updateState = { installMessage: res.message || 'Packages installed successfully.' };
        } catch (err) {
            alert(`Installation failed: ${err.message || err}`);
            updateState = { ...updateState, installing: false };
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-install-sec-updates')?.addEventListener('click', async () => {
        updateState = { ...updateState, installing: true };
        renderAdminSystem(container);
        try {
            const res = await api.installUpdates(true);
            updateState = { installMessage: res.message || 'Security updates installed.' };
        } catch (err) {
            alert(`Security install failed: ${err.message || err}`);
            updateState = { ...updateState, installing: false };
        }
        renderAdminSystem(container);
    });

    container.querySelector('#btn-reboot-router')?.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to reboot the RoostOS router? Network connectivity will be temporarily interrupted.')) return;
        try {
            await api.rebootRouter();
            alert('Reboot command sent to router. System will restart shortly.');
        } catch (err) {
            alert(`Failed to reboot: ${err.message || err}`);
        }
    });

    container.querySelectorAll('.yaml-tab').forEach(b => {
        b.onclick = () => {
            activeYaml = b.dataset.file;
            renderAdminSystem(container);
        };
    });

    container.querySelector('#btn-copy-yaml').onclick = (e) => {
        const text = (admin.yamlFiles && admin.yamlFiles[activeYaml]) || '';
        navigator.clipboard?.writeText(text);
        e.target.textContent = 'Copied!';
        setTimeout(() => e.target.textContent = '📋 Copy YAML', 1500);
    };
}
