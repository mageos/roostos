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
    content = content.replace(/^export\s+/gm, '');
    (0, eval)(content);
}

loadScript('js/services/auth-service.js');
loadScript('js/services/system-service.js');
loadScript('js/components/system-settings.js');

describe('SystemService & SystemComponent (Updates & Maintenance)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-jwt');
        document.body.innerHTML = '<div class="view-container"></div>';
        window.systemComponent = new window.SystemComponent();
        window.systemComponent.mount(document.querySelector('.view-container'));
    });

    test('SystemService update API methods make correct HTTP calls', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ success: true })
        });

        await window.systemService.fetchUpdatesStatus();
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/updates/status', expect.anything());

        await window.systemService.checkUpdates();
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/updates/check', expect.objectContaining({ method: 'POST' }));

        await window.systemService.installUpdates(true);
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/updates/install?security_only=true', expect.objectContaining({ method: 'POST' }));

        await window.systemService.fetchUpdatesConfig();
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/updates/config', expect.anything());

        await window.systemService.saveUpdatesConfig({ auto_update_enabled: true });
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/updates/config', expect.objectContaining({
            method: 'PUT',
            body: JSON.stringify({ auto_update_enabled: true })
        }));
    });

    test('SystemComponent.mount attaches #system-view and subtab buttons', () => {
        const view = document.getElementById('system-view');
        expect(view).not.toBeNull();
        expect(document.getElementById('btn-check-updates')).not.toBeNull();
        expect(document.getElementById('btn-install-updates')).not.toBeNull();
        expect(document.getElementById('btn-install-security')).not.toBeNull();
    });

    test('SystemComponent.loadUpdatesStatus updates badges and buttons when updates available', async () => {
        jest.spyOn(window.systemService, 'fetchUpdatesStatus').mockResolvedValueOnce({
            os_type: 'debian',
            updates_available: 3,
            security_updates_available: 1,
            packages: ['linux-image-amd64', 'curl', 'openssl'],
            reboot_required: true
        });

        await window.systemComponent.loadUpdatesStatus();

        expect(document.getElementById('badge-os-type').textContent).toBe('OS: debian');
        expect(document.getElementById('badge-update-status').textContent).toBe('3 Updates Available');
        expect(document.getElementById('badge-security-status').textContent).toBe('1 Security Update');
        expect(document.getElementById('badge-security-status').style.display).toBe('inline-block');
        expect(document.getElementById('reboot-warning-banner').style.display).toBe('block');
        expect(document.getElementById('btn-install-updates').disabled).toBe(false);
        expect(document.getElementById('btn-install-security').disabled).toBe(false);
        expect(document.getElementById('packages-container').style.display).toBe('block');
        expect(document.getElementById('packages-list').textContent).toContain('linux-image-amd64');
    });

    test('SystemComponent.loadUpdatesStatus renders up-to-date state correctly', async () => {
        jest.spyOn(window.systemService, 'fetchUpdatesStatus').mockResolvedValueOnce({
            os_type: 'arch',
            updates_available: 0,
            security_updates_available: 0,
            packages: [],
            reboot_required: false
        });

        await window.systemComponent.loadUpdatesStatus();

        expect(document.getElementById('badge-update-status').textContent).toBe('Up to Date');
        expect(document.getElementById('badge-security-status').style.display).toBe('none');
        expect(document.getElementById('reboot-warning-banner').style.display).toBe('none');
        expect(document.getElementById('btn-install-updates').disabled).toBe(true);
        expect(document.getElementById('btn-install-security').disabled).toBe(true);
        expect(document.getElementById('packages-container').style.display).toBe('none');
    });

    test('SystemComponent.checkUpdates displays banner message', async () => {
        jest.spyOn(window.systemService, 'checkUpdates').mockResolvedValueOnce({
            updates_available: 2,
            security_updates_available: 1
        });
        jest.spyOn(window.systemService, 'fetchUpdatesStatus').mockResolvedValueOnce({
            updates_available: 2,
            security_updates_available: 1
        });

        await window.systemComponent.checkUpdates();

        const banner = document.getElementById('update-action-banner');
        expect(banner.style.display).toBe('block');
        expect(banner.textContent).toContain('Found 2 updates (1 security)');
    });

    test('SystemComponent.installUpdates triggers install and refreshes status', async () => {
        jest.spyOn(window.systemService, 'installUpdates').mockResolvedValueOnce({
            success: true,
            packages_updated: 2,
            reboot_required: true,
            scheduled_reboot_time: 'Sun 03:00'
        });
        jest.spyOn(window.systemService, 'fetchUpdatesStatus').mockResolvedValueOnce({
            updates_available: 0,
            security_updates_available: 0,
            reboot_required: true
        });

        await window.systemComponent.installUpdates(false);

        const banner = document.getElementById('update-action-banner');
        expect(banner.textContent).toContain('Successfully updated 2 packages');
        expect(banner.textContent).toContain('Reboot scheduled for Sun 03:00');
    });

    test('SystemComponent loads and saves update schedule configuration', async () => {
        jest.spyOn(window.systemService, 'fetchUpdatesConfig').mockResolvedValueOnce({
            auto_update_enabled: true,
            security_only: true,
            auto_reboot: false,
            reboot_window: 'Wed 04:00'
        });

        await window.systemComponent.loadUpdatesConfig();

        expect(document.getElementById('cfg-auto-update').checked).toBe(true);
        expect(document.getElementById('cfg-auto-security').checked).toBe(true);
        expect(document.getElementById('cfg-auto-reboot').checked).toBe(false);
        expect(document.getElementById('cfg-reboot-window').value).toBe('Wed 04:00');

        const saveSpy = jest.spyOn(window.systemService, 'saveUpdatesConfig').mockResolvedValueOnce({ success: true });

        document.getElementById('cfg-reboot-window').value = 'Sat 02:30';
        await window.systemComponent.saveUpdatesConfig();

        expect(saveSpy).toHaveBeenCalledWith({
            auto_update_enabled: true,
            security_only: true,
            auto_reboot: false,
            reboot_window: 'Sat 02:30'
        });
    });
});
