// Concept 1: Household Hub - Wi-Fi, Guest Access & Speed Test
import { store } from '../state.js';

export function renderHouseholdWifi(container) {
    const data = store.data;

    container.innerHTML = `
        <!-- Wi-Fi SSIDs List -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">📶 Wi-Fi Networks</h3>
                    <p class="card-subtitle">Manage wireless access points, guest isolation, and credentials</p>
                </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 16px;">
                ${data.wifiNetworks.length === 0 ? `
                    <div style="border: 1px dashed var(--border-subtle); border-radius: var(--radius-lg); padding: 24px; text-align: center; color: var(--text-muted);">
                        <p>No Wi-Fi access points configured on this router.</p>
                        <p style="font-size: 12px; margin-top: 4px;">Ethernet interfaces are currently serving the local network.</p>
                    </div>
                ` : data.wifiNetworks.map(w => `
                    <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 18px; background: var(--bg-subtle);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                            <div>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <h4 style="font-size: 16px; font-weight: 700;">${w.ssid}</h4>
                                    <span class="badge ${w.isolate ? 'badge-warning' : 'badge-success'}">
                                        ${w.isolate ? '🛡️ Isolated VLAN' : '🟢 Main LAN'}
                                    </span>
                                </div>
                                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                                    Band: <strong>${w.band}</strong> • Security: <strong>${w.security}</strong> • Radio: <strong>${w.channel}</strong>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <span class="badge badge-info" style="font-size: 12px; padding: 4px 10px;">${w.clients} Devices Connected</span>
                                ${w.qr ? `<button class="btn btn-primary btn-sm show-qr-btn" data-ssid="${w.ssid}">📱 View Guest QR</button>` : ''}
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>

        <!-- Speed Test Widget -->
        <div class="card">
            <div class="card-header">
                <div>
                    <h3 class="card-title">⚡ Internet Speed & Diagnostics</h3>
                    <p class="card-subtitle">Live bandwidth test to nearest regional test server</p>
                </div>
                <button class="btn btn-primary btn-sm" id="btn-run-speedtest">▶ Run Speed Test</button>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; text-align: center;">
                <div style="background: var(--bg-subtle); padding: 20px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                    <div style="font-size: 13px; color: var(--text-muted); font-weight: 500;">DOWNLOAD</div>
                    <div style="font-size: 32px; font-weight: 800; color: var(--brand-primary); margin: 6px 0;" id="st-down-val">${data.system.downloadMbps}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">Mbps (Gigabit Line)</div>
                </div>

                <div style="background: var(--bg-subtle); padding: 20px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                    <div style="font-size: 13px; color: var(--text-muted); font-weight: 500;">UPLOAD</div>
                    <div style="font-size: 32px; font-weight: 800; color: var(--accent-emerald); margin: 6px 0;" id="st-up-val">${data.system.uploadMbps}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">Mbps (Symmetric Fiber)</div>
                </div>

                <div style="background: var(--bg-subtle); padding: 20px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                    <div style="font-size: 13px; color: var(--text-muted); font-weight: 500;">PING / LATENCY</div>
                    <div style="font-size: 32px; font-weight: 800; color: var(--accent-amber); margin: 6px 0;" id="st-ping-val">${data.system.pingMs}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">ms (Fiber Hop)</div>
                </div>
            </div>

            <div id="st-progress-bar" style="display: none; margin-top: 16px; width: 100%; height: 6px; background: var(--bg-subtle); border-radius: var(--radius-full); overflow: hidden;">
                <div id="st-progress-fill" style="width: 0%; height: 100%; background: var(--brand-primary); transition: width 0.2s linear;"></div>
            </div>
        </div>

        <!-- Local Subnets & DHCP Settings for Power Users -->
        <div class="card" style="border-left: 4px solid var(--accent-emerald);">
            <div class="card-header table-action-bar">
                <div>
                    <h3 class="card-title">📡 Network IP Ranges & DHCP</h3>
                    <p class="card-subtitle">Automatic IP address assignment scopes across your home networks</p>
                </div>
                <button class="btn btn-secondary btn-sm" id="btn-wifi-open-dhcp">Configure DHCP Scopes →</button>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                ${data.admin.dhcpScopes.map(s => `
                    <div style="background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <strong>${s.name}</strong>
                            <span class="badge ${s.enabled ? 'badge-success' : 'badge-danger'}">${s.enabled ? 'Active' : 'Off'}</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">Gateway: <code>${s.gateway}</code></div>
                        <div style="font-size: 13px; font-weight: 700; color: var(--brand-primary); margin: 4px 0;">
                            <code>${s.poolStart}</code> - <code>${s.poolEnd}</code>
                        </div>
                        <div style="font-size: 11px; color: var(--text-muted);">${s.leaseTimeHuman} lease • ${s.activeLeasesCount || 0} active devices</div>
                    </div>
                `).join('')}
            </div>
        </div>

        <div id="qr-modal-container"></div>
    `;

    container.querySelector('#btn-wifi-open-dhcp')?.addEventListener('click', () => {
        store.concept1Persona = 'admin';
        window.c1SwitchTab('dhcp');
    });

    // Speed test simulator
    const speedBtn = container.querySelector('#btn-run-speedtest');
    const progBar = container.querySelector('#st-progress-bar');
    const progFill = container.querySelector('#st-progress-fill');
    const downVal = container.querySelector('#st-down-val');
    const upVal = container.querySelector('#st-up-val');
    const pingVal = container.querySelector('#st-ping-val');

    speedBtn.onclick = async () => {
        speedBtn.disabled = true;
        speedBtn.textContent = 'Testing...';
        progBar.style.display = 'block';
        progFill.style.width = '15%';
        pingVal.textContent = '...';
        downVal.textContent = '...';
        upVal.textContent = '...';

        setTimeout(() => { progFill.style.width = '45%'; }, 300);
        setTimeout(() => { progFill.style.width = '75%'; }, 700);

        const res = await store.runSpeedTest();
        progFill.style.width = '100%';

        if (res) {
            pingVal.textContent = res.ping_ms;
            downVal.textContent = Math.round(res.download_mbps);
            upVal.textContent = Math.round(res.upload_mbps);
        } else {
            pingVal.textContent = store.data.system.pingMs;
            downVal.textContent = store.data.system.downloadMbps;
            upVal.textContent = store.data.system.uploadMbps;
        }

        speedBtn.disabled = false;
        speedBtn.textContent = '▶ Run Speed Test';
        setTimeout(() => { progBar.style.display = 'none'; }, 600);
    };

    // QR Modal
    container.querySelectorAll('.show-qr-btn').forEach(btn => {
        btn.onclick = () => {
            const net = data.wifiNetworks.find(w => w.ssid === btn.dataset.ssid) || {
                ssid: btn.dataset.ssid || 'Guest Wi-Fi',
                password: ''
            };
            const modal = container.querySelector('#qr-modal-container');
            modal.innerHTML = `
                <div class="drawer-backdrop" id="qr-backdrop" style="justify-content: center; align-items: center;">
                    <div class="card" style="max-width: 360px; width: 100%; text-align: center; padding: 24px;">
                        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">Guest Wi-Fi QR Code</h3>
                        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 16px;">Scan with iPhone or Android camera to instantly connect</p>

                        <!-- High contrast visual QR code representation -->
                        <div style="background: #ffffff; padding: 18px; border-radius: var(--radius-md); display: inline-block; border: 1px solid var(--border-subtle); margin-bottom: 16px;">
                            <svg width="140" height="140" viewBox="0 0 160 160" fill="none">
                                <rect width="160" height="160" fill="white"/>
                                <rect x="10" y="10" width="40" height="40" fill="black"/>
                                <rect x="20" y="20" width="20" height="20" fill="white"/>
                                <rect x="110" y="10" width="40" height="40" fill="black"/>
                                <rect x="120" y="20" width="20" height="20" fill="white"/>
                                <rect x="10" y="110" width="40" height="40" fill="black"/>
                                <rect x="20" y="120" width="20" height="20" fill="white"/>
                                <rect x="60" y="20" width="10" height="30" fill="black"/>
                                <rect x="80" y="10" width="20" height="10" fill="black"/>
                                <rect x="60" y="70" width="40" height="20" fill="black"/>
                                <rect x="20" y="70" width="20" height="20" fill="black"/>
                                <rect x="120" y="70" width="20" height="20" fill="black"/>
                                <rect x="70" y="110" width="30" height="30" fill="black"/>
                            </svg>
                        </div>

                        <div style="background: var(--bg-subtle); padding: 10px; border-radius: var(--radius-sm); font-size: 12px; margin-bottom: 16px;">
                            Network: <strong>${net.ssid}</strong><br>
                            Password: <code>${net.password || net.passphrase || 'WPA Protected'}</code>
                        </div>

                        <div style="display: flex; gap: 8px;">
                            <button class="btn btn-secondary btn-sm" id="btn-copy-pass" style="flex: 1;">📋 Copy Password</button>
                            <button class="btn btn-primary btn-sm" id="btn-close-qr" style="flex: 1;">Done</button>
                        </div>
                    </div>
                </div>
            `;

            modal.querySelector('#btn-close-qr').onclick = () => modal.innerHTML = '';
            modal.querySelector('#qr-backdrop').onclick = (e) => {
                if (e.target.id === 'qr-backdrop') modal.innerHTML = '';
            };
            modal.querySelector('#btn-copy-pass').onclick = (e) => {
                navigator.clipboard?.writeText(net.password || net.passphrase || '');
                e.target.textContent = 'Copied!';
                setTimeout(() => e.target.textContent = '📋 Copy Password', 1500);
            };
        };
    });
}
