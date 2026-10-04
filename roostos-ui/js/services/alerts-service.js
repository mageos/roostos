/**
 * Service for fetching active alerts, history, and telemetry health.
 */

export class AlertsService {
    static async fetchActiveAlerts() {
        const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
        const res = await fetch('/api/v1/alerts/active', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(`Failed to fetch active alerts: ${res.statusText}`);
        return await res.json();
    }

    static async fetchAlertHistory(limit = 20) {
        const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
        const res = await fetch(`/api/v1/alerts/history?limit=${limit}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(`Failed to fetch alert history: ${res.statusText}`);
        return await res.json();
    }

    static async acknowledgeAlert(alertId) {
        const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
        const res = await fetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(`Failed to acknowledge alert: ${res.statusText}`);
        return await res.json();
    }

    static async fetchTelemetryHealth() {
        const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
        const res = await fetch('/api/v1/telemetry/health', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return { healthy: false, binary_installed: false };
        return await res.json();
    }
}
