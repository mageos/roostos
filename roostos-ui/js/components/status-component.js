const STATUS_TEMPLATE = /* html */ `
    <div id="status-view" class="view-pane">
        <div id="system-warnings-container" style="display: none; margin-bottom: 20px;"></div>

        <div class="view-tabs-header">
            <button class="tab-btn active" onclick="switchSubTab('status', 'basic')">Basic</button>
            <button class="tab-btn" onclick="switchSubTab('status', 'advanced')">Advanced</button>
        </div>

        <div class="tab-pane basic-pane active">
            <div class="metrics-row">
                <div class="metric-card">
                    <div class="metric-title">Connected Devices</div>
                    <div class="metric-value" id="metric-connected">0</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Blocked Profiles</div>
                    <div class="metric-value" id="metric-blocked" style="color: var(--accent-red);">0</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Uptime</div>
                    <div class="metric-value" id="metric-uptime">Loading...</div>
                </div>
            </div>

            <div class="card-grid">
                <div class="card">
                    <h2>Router Connection Info</h2>
                    <div class="stat-item">
                        <span class="stat-label">Hostname:</span>
                        <span class="stat-value" id="stat-hostname">-</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Local Domain:</span>
                        <span class="stat-value" id="stat-domain">-</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">WAN IP Address:</span>
                        <span class="stat-value" id="stat-wan-ip">192.168.100.45 (mock)</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">LAN Gateway IP:</span>
                        <span class="stat-value" id="stat-lan-ip">192.168.1.1 (mock)</span>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Traffic & CPU Resources</h2>
                    <div style="display: flex; gap: 24px; margin-bottom: 12px; flex-wrap: wrap;">
                        <div class="stat-item" style="flex: 1; margin: 0; min-width: 100px;">
                            <span class="stat-label">CPU Load:</span>
                            <span class="stat-value" id="stat-cpu">0.0%</span>
                        </div>
                        <div class="stat-item" style="flex: 1; margin: 0; min-width: 100px;">
                            <span class="stat-label">RAM Usage:</span>
                            <span class="stat-value" id="stat-ram">0.0%</span>
                        </div>
                    </div>
                    <div style="margin-top: 16px; display: flex; flex-direction: column; gap: 16px;">
                        <div>
                            <h3 style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; font-weight: 500; display: flex; justify-content: space-between;">
                                <span>WAN Network Bandwidth</span>
                                <span id="traffic-legend-rates" style="font-family: monospace; font-size: 11px;">Rx: 0 B/s | Tx: 0 B/s</span>
                            </h3>
                            <canvas id="traffic-chart" style="width: 100%; height: 110px; border-radius: 6px; background: rgba(0,0,0,0.02); border: 1px solid var(--card-border);"></canvas>
                        </div>
                        <div>
                            <h3 style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; font-weight: 500;">CPU & RAM Load History</h3>
                            <canvas id="resources-chart" style="width: 100%; height: 110px; border-radius: 6px; background: rgba(0,0,0,0.02); border: 1px solid var(--card-border);"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="tab-pane advanced-pane">
            <div class="card">
                <h2>Core System Services</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Active status of core networking and orchestration services running on the host.
                </p>
                <div class="device-table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Service Name</th>
                                <th>systemd Unit</th>
                                <th>Active State</th>
                                <th>Sub State</th>
                            </tr>
                        </thead>
                        <tbody id="services-status-table-body">
                            <tr>
                                <td colspan="4" class="empty-state">Loading services status...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card" style="margin-top: 24px;">
                <h2>System Service Log Viewer</h2>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                    Fetch and view real-time system logs (journalctl) for troubleshooting system services.
                </p>
                <div style="display: flex; gap: 12px; align-items: flex-end; margin-bottom: 16px; flex-wrap: wrap;">
                    <div class="form-group" style="flex: 2; min-width: 150px; margin: 0;">
                        <label for="log-service-select">Select Service</label>
                        <select id="log-service-select" style="margin-top: 6px;">
                            <option value="roostd">RoostOS Management Daemon (roostd)</option>
                            <option value="roostos-web">RoostOS Web Console (roostos-web)</option>
                            <option value="systemd-networkd">Systemd Networkd (systemd-networkd)</option>
                            <option value="kea">Kea DHCPv4 Server (kea)</option>
                            <option value="iwd">iwd WiFi Daemon (iwd)</option>
                        </select>
                    </div>
                    <div class="form-group" style="flex: 1; min-width: 80px; margin: 0;">
                        <label for="log-limit-input">Lines Limit</label>
                        <select id="log-limit-input" style="margin-top: 6px;">
                            <option value="50">50 lines</option>
                            <option value="100" selected>100 lines</option>
                            <option value="200">200 lines</option>
                            <option value="500">500 lines</option>
                        </select>
                    </div>
                    <button class="btn btn-primary" onclick="fetchServiceLogs()" style="height: 36px; display: flex; align-items: center; justify-content: center; gap: 8px;">Fetch Logs</button>
                </div>
                <div id="log-viewer-container" style="display: none; background: #000; border: 1px solid var(--card-border); border-radius: 8px; padding: 16px; margin-top: 16px;">
                    <pre id="log-viewer-pre" style="font-family: monospace; font-size: 12px; color: #10b981; overflow-x: auto; max-height: 400px; overflow-y: auto; margin: 0; white-space: pre-wrap;"></pre>
                </div>
            </div>
        </div>
    </div>
`;

class StatusComponent {
    constructor() {
        this.template = STATUS_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.fetchServiceLogs = () => this.fetchServiceLogs();
        window.refreshServicesStatus = () => this.refreshServicesStatus();
    }

    render(sysData) {
        if (!sysData) return;
        const hostnameEl = document.getElementById("stat-hostname");
        if (hostnameEl) hostnameEl.textContent = sysData.hostname || "-";
        
        const domainEl = document.getElementById("stat-domain");
        if (domainEl) domainEl.textContent = sysData.domain || "-";

        const cpuEl = document.getElementById("stat-cpu");
        if (cpuEl) cpuEl.textContent = sysData.cpu_load || "0.0%";

        const ramEl = document.getElementById("stat-ram");
        if (ramEl) ramEl.textContent = sysData.ram_usage || "0.0%";

        const uptimeEl = document.getElementById("metric-uptime");
        if (uptimeEl) uptimeEl.textContent = sysData.uptime || "-";

        const wanEl = document.getElementById("stat-wan-ip");
        if (wanEl) wanEl.textContent = sysData.wan_ip || "-";

        const lanEl = document.getElementById("stat-lan-ip");
        if (lanEl) lanEl.textContent = sysData.lan_ip || "-";

        const rxVal = parseFloat(sysData.rx_rate || 0.0);
        const txVal = parseFloat(sysData.tx_rate || 0.0);
        const legendRates = document.getElementById("traffic-legend-rates");
        if (legendRates) {
            legendRates.textContent = `Rx: ${window.formatSpeed(rxVal)} | Tx: ${window.formatSpeed(txVal)}`;
        }

        // Render warnings
        const warningsContainer = document.getElementById("system-warnings-container");
        if (warningsContainer) {
            const warnings = sysData.warnings || [];
            if (warnings.length > 0) {
                warningsContainer.style.display = "block";
                warningsContainer.innerHTML = warnings.map(w => `
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; padding: 12px 16px; border-radius: 6px; margin-bottom: 10px; font-size: 13px; display: flex; align-items: center; gap: 8px;">
                        <svg style="width: 16px; height: 16px; fill: currentColor; flex-shrink: 0;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                        <span><strong>System Alert:</strong> ${escapeHtml(w)}</span>
                    </div>
                `).join("");
            } else {
                warningsContainer.style.display = "none";
                warningsContainer.innerHTML = "";
            }
        }

        // Trigger services status refresh
        this.refreshServicesStatus();
    }

    async refreshServicesStatus() {
        const tbody = document.getElementById("services-status-table-body");
        if (!tbody) return;

        try {
            const data = await window.systemService.fetchServicesStatus();
            tbody.innerHTML = data.map(s => {
                const isActive = s.status === "active";
                const isFailed = s.status === "failed";
                let badgeClass = "badge-offline";
                if (isActive) badgeClass = "badge-online";
                else if (isFailed) badgeClass = "badge-offline";
                
                return `
                    <tr>
                        <td><strong>${escapeHtml(s.name)}</strong></td>
                        <td><code>${escapeHtml(s.service)}</code></td>
                        <td><span class="badge ${badgeClass}">${s.status.toUpperCase()}</span></td>
                        <td><code>${escapeHtml(s.substate)}</code></td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="4" class="empty-state" style="color: var(--accent-red);">Failed to load services: ${escapeHtml(e.message)}</td></tr>`;
        }
    }

    async fetchServiceLogs() {
        const service = document.getElementById("log-service-select").value;
        const limit = parseInt(document.getElementById("log-limit-input").value, 10) || 100;
        const container = document.getElementById("log-viewer-container");
        const pre = document.getElementById("log-viewer-pre");
        if (!container || !pre) return;

        pre.textContent = "Fetching logs...";
        pre.style.color = "#10b981";
        container.style.display = "block";

        try {
            const data = await window.systemService.fetchLogs(service, limit);
            pre.textContent = data.logs || "No logs returned for this service.";
            pre.scrollTop = pre.scrollHeight;
        } catch (e) {
            pre.textContent = `Error fetching logs: ${e.message}`;
            pre.style.color = "#ef4444";
        }
    }

    drawCharts() {
        const trafficCanvas = document.getElementById("traffic-chart");
        const resourcesCanvas = document.getElementById("resources-chart");
        if (!trafficCanvas || !resourcesCanvas) return;

        if (metricsHistory.length === 0) return;

        const setupCanvas = (canvas) => {
            const rect = canvas.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            const ctx = canvas.getContext('2d');
            ctx.resetTransform();
            ctx.scale(dpr, dpr);
            return { ctx, width: rect.width, height: rect.height };
        };

        const drawGrid = (ctx, w, h, maxValStr) => {
            ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);

            const lines = 4;
            for (let i = 0; i <= lines; i++) {
                const y = (i / lines) * (h - 20) + 10;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }
            ctx.setLineDash([]);

            if (maxValStr) {
                ctx.fillStyle = "var(--text-secondary)";
                ctx.font = "9px monospace";
                ctx.fillText(maxValStr, 4, 15);
            }
        };

        // Draw Traffic Chart
        const t = setupCanvas(trafficCanvas);
        const maxTraffic = Math.max(...metricsHistory.map(d => Math.max(d.rx, d.tx, 1024)));
        drawGrid(t.ctx, t.width, t.height, window.formatSpeed(maxTraffic));

        const drawPath = (ctx, w, h, dataKey, strokeStyle, fillGradientColor) => {
            ctx.beginPath();
            const points = metricsHistory.map((d, index) => {
                const x = (index / (MAX_HISTORY_POINTS - 1)) * w;
                const y = h - ((d[dataKey] / maxTraffic) * (h - 20)) - 10;
                return { x, y };
            });

            if (points.length === 0) return;

            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.strokeStyle = strokeStyle;
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.lineTo(points[points.length - 1].x, h);
            ctx.lineTo(points[0].x, h);
            ctx.closePath();
            const grad = ctx.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0, fillGradientColor);
            grad.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.fillStyle = grad;
            ctx.fill();
        };

        drawPath(t.ctx, t.width, t.height, "rx", "#10b981", "rgba(16, 185, 129, 0.15)");
        drawPath(t.ctx, t.width, t.height, "tx", "#3b82f6", "rgba(59, 130, 246, 0.15)");

        // Draw Resources Chart
        const r = setupCanvas(resourcesCanvas);
        drawGrid(r.ctx, r.width, r.height, "100%");

        const drawResourcePath = (ctx, w, h, dataKey, strokeStyle) => {
            ctx.beginPath();
            const points = metricsHistory.map((d, index) => {
                const x = (index / (MAX_HISTORY_POINTS - 1)) * w;
                const y = h - ((d[dataKey] / 100.0) * (h - 20)) - 10;
                return { x, y };
            });

            if (points.length === 0) return;

            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.strokeStyle = strokeStyle;
            ctx.lineWidth = 2;
            ctx.stroke();
        };

        drawResourcePath(r.ctx, r.width, r.height, "cpu", "#06b6d4");
        drawResourcePath(r.ctx, r.width, r.height, "ram", "#a855f7");
    }
}

window.statusComponent = new StatusComponent();
