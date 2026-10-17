// Concept 1: Household Hub - Safety, Security, VPN & Remote Access (CGNAT Bypass)
import { store } from '../state.js';
import { renderBlockedFeed } from './c1-blocked-feed.js';

export function renderHouseholdSafety(container) {
    const data = store.data;
    const prot = data.protection || {};
    const edge = data.edgeGateway || { enabled: false, vpsHostname: '', ingressRules: [] };
    const adBlocking = prot.adBlocking || { enabled: false, blockedToday: 0, blocklistPercent: 0 };
    const safeSearch = prot.safeSearch || { enabled: false };
    const vpnTunnel = prot.vpnTunnel || { name: 'WireGuard Client', endpoint: 'None', enabled: false };

    container.innerHTML = `
        <!-- Cloud Edge Relay & Remote Access (CGNAT Bypass for Power Users) -->
        <div class="card" style="border-left: 4px solid var(--accent-indigo); background: linear-gradient(to right, var(--bg-surface), var(--bg-subtle));">
            <div class="card-header">
                <div>
                    <h3 class="card-title">☁️ Remote Access & Cloud Edge Relay (CGNAT Bypass)</h3>
                    <p class="card-subtitle">Access your home devices securely while away without exposing home ports to the open web</p>
                </div>
                <span class="badge ${edge.enabled ? 'badge-success' : 'badge-neutral'}">● Relay ${edge.enabled ? 'Connected' : 'Not Configured'}</span>
            </div>

            <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <div style="font-size: 14px; font-weight: 700; color: var(--text-main);">
                            🔒 Secure Cloud Tunnel: <code>${edge.vpsHostname || 'Unenrolled • Configure in Admin Cockpit'}</code>
                        </div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                            Bypasses residential Carrier-Grade NAT (CGNAT) using stealth WireGuard encryption.
                        </div>
                    </div>
                    <span class="badge badge-info">Zero Open Home Ports</span>
                </div>
            </div>

            <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 8px;">Remotely Accessible Home Services</h4>
            <div style="display: flex; flex-direction: column; gap: 10px;">
                ${(edge.ingressRules && edge.ingressRules.length > 0) ? edge.ingressRules.map(r => `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md);">
                        <div>
                            <strong>${r.service}</strong>
                            <div style="font-size: 12px; color: var(--brand-primary); margin-top: 2px;">
                                <code>https://${r.domain}</code>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span class="badge badge-success" style="font-size: 11px;">🔒 ${r.ssl}</span>
                            <label class="switch-toggle">
                                <input type="checkbox" checked>
                                <span class="switch-slider"></span>
                            </label>
                        </div>
                    </div>
                `).join('') : `
                    <div style="text-align: center; padding: 24px 16px; color: var(--text-muted); background: var(--bg-surface); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md);">
                        No remote ingress services configured. All ports remain fully isolated behind firewall.
                    </div>
                `}
            </div>
        </div>

        <!-- Content Protection Overview -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🛡️ Household Security & Content Protection</h3>
                    <p class="card-subtitle">Zero-configuration network shields that protect every phone, tablet, and smart device</p>
                </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 16px;">
                <!-- Ad & Tracker Shield -->
                <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 18px; background: var(--bg-subtle);">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <h4 style="font-size: 16px; font-weight: 700;">Ad & Tracker Blocking</h4>
                                <span class="badge ${adBlocking.enabled ? 'badge-success' : 'badge-neutral'}">
                                    ${adBlocking.enabled ? '🟢 Active' : '⚪ Disabled'}
                                </span>
                            </div>
                            <p style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">
                                Silently blocks intrusive mobile ads, video trackers, and telemetry scripts at the DNS level.
                            </p>
                            <div style="font-size: 12px; color: var(--brand-primary); font-weight: 600; margin-top: 8px;">
                                📊 ${(adBlocking.blockedToday || 0).toLocaleString()} ads & trackers blocked today (${adBlocking.blocklistPercent || 0}% of queries)
                            </div>
                        </div>
                        <label class="switch-toggle">
                            <input type="checkbox" id="toggle-ad-block" ${adBlocking.enabled ? 'checked' : ''}>
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                </div>

                <!-- SafeSearch & Parental Filters -->
                <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 18px; background: var(--bg-subtle);">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <h4 style="font-size: 16px; font-weight: 700;">SafeSearch & Adult Content Shield</h4>
                                <span class="badge ${safeSearch.enabled ? 'badge-success' : 'badge-neutral'}">
                                    ${safeSearch.enabled ? '🟢 Enforced for Kids' : '⚪ Disabled'}
                                </span>
                            </div>
                            <p style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">
                                Forces strict Google, YouTube, and Bing SafeSearch. Automatically blocks adult domains on kids' devices.
                            </p>
                        </div>
                        <label class="switch-toggle">
                            <input type="checkbox" id="toggle-safesearch" ${safeSearch.enabled ? 'checked' : ''}>
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                </div>
            </div>
        </div>

        <!-- Whole Home VPN Privacy Tunnel -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">🔒 Outbound VPN Privacy Tunnel</h3>
                    <p class="card-subtitle">Route outbound household internet traffic through an encrypted WireGuard tunnel</p>
                </div>
            </div>

            <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 18px; background: var(--bg-subtle);">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <h4 style="font-size: 16px; font-weight: 700;">${vpnTunnel.name || 'Outbound VPN'}</h4>
                            <span class="badge ${vpnTunnel.enabled ? 'badge-success' : 'badge-neutral'}">
                                ${vpnTunnel.enabled ? '🟢 Tunnel Connected' : '⚪ Disconnected'}
                            </span>
                        </div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                            Endpoint: <code>${vpnTunnel.endpoint || 'Not configured'}</code> • Protocol: <strong>WireGuard (UDP)</strong>
                        </div>
                    </div>
                    <label class="switch-toggle">
                        <input type="checkbox" id="toggle-vpn" ${vpnTunnel.enabled ? 'checked' : ''}>
                        <span class="switch-slider"></span>
                    </label>
                </div>
            </div>
        </div>
    `;

    renderBlockedFeed(container, { isExpert: false, onReload: () => renderHouseholdSafety(container) });

    container.querySelector('#toggle-ad-block')?.addEventListener('change', () => store.toggleAdBlock());
    container.querySelector('#toggle-vpn')?.addEventListener('change', () => store.toggleVpn());
    container.querySelector('#toggle-safesearch')?.addEventListener('change', () => store.toggleSafeSearch());
}
