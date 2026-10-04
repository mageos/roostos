/**
 * Alerts drawer component for managing live cluster incidents and notifications.
 */

import { AlertsService } from '../services/alerts-service.js';

let alertsDrawerOpen = false;

export async function updateAlertsBadge() {
    try {
        const active = await AlertsService.fetchActiveAlerts();
        const badge = document.getElementById('alerts-count-badge');
        const icon = document.getElementById('alerts-indicator-icon');
        if (!badge || !icon) return;

        const count = active.length;
        if (count > 0) {
            badge.textContent = `${count}`;
            badge.style.display = 'inline-block';
            const hasCritical = active.some(a => a.severity === 'critical');
            badge.style.background = hasCritical ? 'var(--accent-red, #ef4444)' : 'var(--accent-yellow, #f59e0b)';
            badge.style.color = '#fff';
            icon.textContent = '🚨';
        } else {
            badge.style.display = 'none';
            icon.textContent = '🔔';
        }
    } catch {
        // Silently ignore if unauthorized or offline
    }
}

export function toggleAlertsDrawer() {
    alertsDrawerOpen = !alertsDrawerOpen;
    let modal = document.getElementById('alerts-drawer-modal');
    if (!modal) {
        modal = createAlertsDrawerModal();
        document.body.appendChild(modal);
    }
    if (alertsDrawerOpen) {
        modal.style.display = 'flex';
        renderAlertsContent();
    } else {
        modal.style.display = 'none';
    }
}

function createAlertsDrawerModal() {
    const modal = document.createElement('div');
    modal.id = 'alerts-drawer-modal';
    modal.style.cssText = `
        display: none; position: fixed; inset: 0; z-index: 1000;
        background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px);
        justify-content: flex-end; align-items: stretch;
    `;
    modal.onclick = (e) => {
        if (e.target === modal) toggleAlertsDrawer();
    };

    const drawer = document.createElement('div');
    drawer.id = 'alerts-drawer-content';
    drawer.style.cssText = `
        width: 480px; max-width: 90vw; background: var(--card-bg, #1a1b26);
        border-left: 1px solid var(--card-border, #2e3044);
        padding: 24px; display: flex; flex-direction: column; gap: 16px;
        overflow-y: auto; box-shadow: -4px 0 20px rgba(0,0,0,0.4);
    `;
    modal.appendChild(drawer);
    return modal;
}

export async function renderAlertsContent() {
    const container = document.getElementById('alerts-drawer-content');
    if (!container) return;

    container.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border); padding-bottom: 12px;">
            <h2 style="margin: 0; font-size: 18px; display: flex; align-items: center; gap: 8px;">
                <span>🔔</span> Incident & Telemetry Alerts
            </h2>
            <button onclick="window.toggleAlertsDrawer()" style="background: none; border: none; font-size: 20px; color: var(--text-secondary); cursor: pointer;">✕</button>
        </div>
        <div id="alerts-telemetry-status" style="font-size: 12px; color: var(--text-secondary); padding: 8px 12px; background: rgba(255,255,255,0.03); border-radius: 6px;">
            Connecting to VictoriaMetrics...
        </div>
        <div>
            <h3 style="font-size: 14px; text-transform: uppercase; color: var(--text-secondary); margin: 8px 0;">Active Incidents</h3>
            <div id="active-alerts-list" style="display: flex; flex-direction: column; gap: 8px;">Loading...</div>
        </div>
        <div>
            <h3 style="font-size: 14px; text-transform: uppercase; color: var(--text-secondary); margin: 16px 0 8px;">Recent History</h3>
            <div id="history-alerts-list" style="display: flex; flex-direction: column; gap: 8px;">Loading...</div>
        </div>
    `;

    try {
        const [health, active, history] = await Promise.all([
            AlertsService.fetchTelemetryHealth(),
            AlertsService.fetchActiveAlerts(),
            AlertsService.fetchAlertHistory(10),
        ]);

        const statusEl = document.getElementById('alerts-telemetry-status');
        if (statusEl) {
            statusEl.innerHTML = health.healthy
                ? `🟢 VictoriaMetrics Engine: <strong>Online</strong> (${health.base_url})`
                : `🟡 VictoriaMetrics Engine: <strong>Standby / Initializing</strong>`;
        }

        const activeListEl = document.getElementById('active-alerts-list');
        if (activeListEl) {
            if (active.length === 0) {
                activeListEl.innerHTML = `<div style="padding: 12px; border-radius: 6px; background: rgba(34, 197, 94, 0.1); color: #22c55e; font-size: 13px;">✓ All cluster systems healthy. No active firing alerts.</div>`;
            } else {
                activeListEl.innerHTML = active.map(a => renderAlertCard(a, true)).join('');
            }
        }

        const historyListEl = document.getElementById('history-alerts-list');
        if (historyListEl) {
            if (history.length === 0) {
                historyListEl.innerHTML = `<div style="font-size: 12px; color: var(--text-secondary); padding: 8px 0;">No alert history recorded yet.</div>`;
            } else {
                historyListEl.innerHTML = history.map(a => renderAlertCard(a, false)).join('');
            }
        }
    } catch (e) {
        const activeListEl = document.getElementById('active-alerts-list');
        if (activeListEl) activeListEl.innerHTML = `<div style="color: var(--accent-red); font-size: 12px;">Failed to load alerts: ${e.message}</div>`;
    }
}

function renderAlertCard(alert, isFiring) {
    const isCrit = alert.severity === 'critical';
    const borderCol = isCrit ? '#ef4444' : (alert.severity === 'warning' ? '#f59e0b' : '#3b82f6');
    const badgeBg = isCrit ? 'rgba(239, 68, 68, 0.2)' : (alert.severity === 'warning' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(59, 130, 246, 0.2)');
    const stateBadge = alert.state === 'firing'
        ? `<span style="background: rgba(239, 68, 68, 0.2); color: #ef4444; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;">FIRING</span>`
        : `<span style="background: rgba(34, 197, 94, 0.2); color: #22c55e; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;">RESOLVED</span>`;

    return `
        <div style="padding: 12px; border: 1px solid var(--card-border); border-left: 3px solid ${borderCol}; border-radius: 6px; background: rgba(255,255,255,0.02); display: flex; flex-direction: column; gap: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="background: ${badgeBg}; color: ${borderCol}; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase;">${alert.severity}</span>
                    <span style="font-weight: 600; font-size: 13px;">${alert.title}</span>
                </div>
                ${stateBadge}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary);">${alert.message}</div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-secondary); margin-top: 4px;">
                <span>Node: <strong>${alert.node_id}</strong> | ${new Date(alert.fired_at).toLocaleTimeString()}</span>
                ${isFiring && !alert.acknowledged ? `<button onclick="window.acknowledgeAlert('${alert.id}')" style="background: rgba(255,255,255,0.05); border: 1px solid var(--card-border); color: var(--text-primary); padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;">Ack</button>` : ''}
            </div>
        </div>
    `;
}

window.toggleAlertsDrawer = toggleAlertsDrawer;
window.updateAlertsBadge = updateAlertsBadge;
window.acknowledgeAlert = async (id) => {
    try {
        await AlertsService.acknowledgeAlert(id);
        renderAlertsContent();
        updateAlertsBadge();
    } catch (e) {
        alert(e.message);
    }
};

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        updateAlertsBadge();
    });
}
