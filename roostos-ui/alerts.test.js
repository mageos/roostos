const fs = require('fs');
const path = require('path');

global.fetch = jest.fn();
global.alert = jest.fn();

const localStorageMock = (() => {
    let store = {};
    return {
        getItem: (k) => store[k] || null,
        setItem: (k, v) => { store[k] = v.toString(); },
        removeItem: (k) => delete store[k],
        clear: () => { store = {}; }
    };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

function loadScript(relPath) {
    const fullPath = path.resolve(__dirname, relPath);
    let content = fs.readFileSync(fullPath, 'utf8');
    content = content.replace(/import\s*\{[\s\S]*?\}\s*from\s*['"][^'"]+['"];?/g, '');
    content = content.replace(/import\s+.*?from\s+['"][^'"]+['"];?/g, '');
    content = content.replace(/^export\s+const\s+(\w+)\s*=/gm, 'global.$1 = window.$1 =');
    content = content.replace(/^export\s+function\s+(\w+)/gm, 'global.$1 = window.$1 = function $1');
    content = content.replace(/^export\s+class\s+(\w+)/gm, 'global.$1 = window.$1 = class $1');
    content = content.replace(/^export\s+/gm, '');
    (0, eval)(content);
}

loadScript('js/services/alerts-service.js');
loadScript('js/components/alerts-drawer.js');

describe('AlertsService & AlertsDrawer', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('access_token', 'test-jwt');
        document.body.innerHTML = `
            <div id="alerts-indicator-icon">🔔</div>
            <div id="alerts-count-badge" style="display: none;">0</div>
        `;
    });

    test('AlertsService.fetchActiveAlerts retrieves active incidents', async () => {
        const mockAlerts = [
            { id: 'disk_critical:node-01', title: 'Disk Critical', severity: 'critical', message: 'Disk 95%' }
        ];
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockAlerts,
        });

        const alerts = await window.AlertsService.fetchActiveAlerts();
        expect(alerts).toHaveLength(1);
        expect(alerts[0].id).toBe('disk_critical:node-01');
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/alerts/active', expect.objectContaining({
            headers: { 'Authorization': 'Bearer test-jwt' }
        }));
    });

    test('AlertsService.acknowledgeAlert sends POST request', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, alert_id: 'disk_critical:node-01' }),
        });

        const res = await window.AlertsService.acknowledgeAlert('disk_critical:node-01');
        expect(res.success).toBe(true);
        expect(global.fetch).toHaveBeenCalledWith(
            '/api/v1/alerts/disk_critical%3Anode-01/acknowledge',
            expect.objectContaining({ method: 'POST' })
        );
    });

    test('AlertsService.fetchTelemetryHealth retrieves engine health', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ healthy: true, binary_installed: true, base_url: 'http://127.0.0.1:8428' }),
        });

        const health = await window.AlertsService.fetchTelemetryHealth();
        expect(health.healthy).toBe(true);
        expect(health.binary_installed).toBe(true);
    });

    test('updateAlertsBadge updates DOM badge when alerts active', async () => {
        const mockAlerts = [
            { id: 'disk_critical:node-01', title: 'Disk Critical', severity: 'critical' },
            { id: 'cpu_high:node-01', title: 'CPU High', severity: 'warning' },
        ];
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockAlerts,
        });

        await window.updateAlertsBadge();

        const badge = document.getElementById('alerts-count-badge');
        const icon = document.getElementById('alerts-indicator-icon');

        expect(badge.textContent).toBe('2');
        expect(badge.style.display).toBe('inline-block');
        expect(icon.textContent).toBe('🚨');
    });

    test('updateAlertsBadge hides badge when no alerts active', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => [],
        });

        await window.updateAlertsBadge();

        const badge = document.getElementById('alerts-count-badge');
        const icon = document.getElementById('alerts-indicator-icon');

        expect(badge.style.display).toBe('none');
        expect(icon.textContent).toBe('🔔');
    });

    test('toggleAlertsDrawer toggles modal visibility', () => {
        window.toggleAlertsDrawer();
        const modal = document.getElementById('alerts-drawer-modal');
        expect(modal).not.toBeNull();
        expect(modal.style.display).toBe('flex');

        window.toggleAlertsDrawer();
        expect(modal.style.display).toBe('none');
    });
});
