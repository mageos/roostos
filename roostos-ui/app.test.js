const fs = require('fs');
const path = require('path');

// Mock window globals before evaluating scripts
global.fetch = jest.fn();
global.alert = jest.fn();
global.console.error = jest.fn();

// Mock localStorage
const localStorageMock = (() => {
    let store = {};
    return {
        getItem(key) {
            return store[key] || null;
        },
        setItem(key, value) {
            store[key] = value.toString();
        },
        removeItem(key) {
            delete store[key];
        },
        clear() {
            store = {};
        }
    };
})();

Object.defineProperty(window, 'localStorage', {
    value: localStorageMock
});

// Configure mock window.location
delete window.location;
window.location = {
    origin: 'http://localhost:8000',
    pathname: '/',
    search: '',
    href: 'http://localhost:8000/'
};

// Replace window.history.replaceState with a mock
window.history = {
    replaceState: jest.fn()
};

// Stub dynamic DOM elements for component mounting
document.body.innerHTML = `
    <div class="sidebar-nav">
        <button class="nav-item">Dashboard</button>
        <button class="nav-item">Plugins</button>
    </div>
    <div class="view-container"></div>
    <div id="view-title">Dashboard</div>
`;

/**
 * Load modular scripts in dependency order:
 *   1. Services (auth first since other services depend on window.authService)
 *   2. Components (depend on services being available on window)
 *   3. app.js orchestrator (depends on all services and components being mounted)
 */
const scriptLoadOrder = [
    // Services
    'js/services/auth-service.js',
    'js/services/network-service.js',
    'js/services/device-service.js',
    'js/services/security-service.js',
    'js/services/system-service.js',
    // Components
    'js/components/status-component.js',
    'js/components/network-component.js',
    'js/components/device-component.js',
    'js/components/security-components.js',
    'js/components/management-components.js',
    // Main orchestrator
    'app.js'
];

for (const scriptRelativePath of scriptLoadOrder) {
    const absolutePath = path.resolve(__dirname, scriptRelativePath);
    if (fs.existsSync(absolutePath)) {
        const content = fs.readFileSync(absolutePath, 'utf8');
        eval(content);
    }
}

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe('AuthService', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        window.location.search = '';
        window.location.href = 'http://localhost:8000/';
    });

    test('apiFetch attaches Authorization header when token is present', async () => {
        localStorage.setItem('roostos_token', 'mock-jwt-token-123');
        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve({ success: true })
        });

        const response = await window.authService.apiFetch('/api/devices');
        expect(response.status).toBe(200);
        expect(fetch).toHaveBeenCalledWith('/api/devices', {
            headers: {
                'Authorization': 'Bearer mock-jwt-token-123'
            }
        });
    });

    test('apiFetch sends request without Authorization header when no token exists', async () => {
        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve({ data: [] })
        });

        await window.authService.apiFetch('/api/devices');
        expect(fetch).toHaveBeenCalledWith('/api/devices', {
            headers: {}
        });
    });

    test('apiFetch clears token and redirects on 401 Unauthorized', async () => {
        localStorage.setItem('roostos_token', 'expired-token');
        fetch.mockResolvedValue({
            status: 401,
            ok: false
        });

        const response = await window.authService.apiFetch('/api/devices');
        expect(response.status).toBe(401);
        expect(localStorage.getItem('roostos_token')).toBeNull();
        expect(window.location.href).toContain('/oauth/authorize');
    });

    test('logout clears token and redirects to OAuth login', () => {
        localStorage.setItem('roostos_token', 'some-valid-token');

        window.authService.logout();

        expect(localStorage.getItem('roostos_token')).toBeNull();
        expect(window.location.href).toContain('/oauth/authorize?client_id=roostos_admin_ui');
    });

    test('handleAuthentication returns false and redirects when no token is present', () => {
        const result = window.authService.handleAuthentication();

        expect(result).toBe(false);
        expect(window.location.href).toContain('/oauth/authorize?client_id=roostos_admin_ui');
    });

    test('handleAuthentication returns true when a valid token exists', () => {
        localStorage.setItem('roostos_token', 'active-token');

        const result = window.authService.handleAuthentication();

        expect(result).toBe(true);
    });

    test('handleAuthentication triggers code exchange when OAuth code is in URL', () => {
        window.location.search = '?code=auth-code-xyz';

        // exchangeAuthCode will call fetch for /oauth/token
        fetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ access_token: 'new-token' })
        });

        const result = window.authService.handleAuthentication();

        // Should return false because it starts the async exchange flow
        expect(result).toBe(false);
    });
});

describe('Backward Compatibility Wrappers', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        window.location.search = '';
        window.location.href = 'http://localhost:8000/';
    });

    test('window.apiFetch delegates to authService.apiFetch', async () => {
        localStorage.setItem('roostos_token', 'compat-token');
        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve({ ok: true })
        });

        const response = await window.apiFetch('/api/system');
        expect(response.status).toBe(200);
        expect(fetch).toHaveBeenCalledWith('/api/system', {
            headers: { 'Authorization': 'Bearer compat-token' }
        });
    });

    test('window.logout delegates to authService.logout', () => {
        localStorage.setItem('roostos_token', 'logout-token');

        window.logout();

        expect(localStorage.getItem('roostos_token')).toBeNull();
        expect(window.location.href).toContain('/oauth/authorize');
    });

    test('window.handleAuthentication delegates to authService.handleAuthentication', () => {
        localStorage.setItem('roostos_token', 'delegate-token');

        const result = window.handleAuthentication();

        expect(result).toBe(true);
    });
});

describe('Global Helpers', () => {
    test('escapeHtml escapes special characters', () => {
        expect(window.escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
        );
    });

    test('escapeHtml returns empty string for null/undefined', () => {
        expect(window.escapeHtml(null)).toBe('');
        expect(window.escapeHtml(undefined)).toBe('');
    });

    test('formatSpeed formats bytes per second correctly', () => {
        expect(window.formatSpeed(0)).toBe('0 B/s');
        expect(window.formatSpeed(512)).toBe('512 B/s');
        expect(window.formatSpeed(1024)).toBe('1.0 KB/s');
        expect(window.formatSpeed(1024 * 1024)).toBe('1.0 MB/s');
    });

    test('formatSpeed handles null/undefined/NaN', () => {
        expect(window.formatSpeed(null)).toBe('0 B/s');
        expect(window.formatSpeed(undefined)).toBe('0 B/s');
        expect(window.formatSpeed(NaN)).toBe('0 B/s');
    });
});

describe('View Routing', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    test('switchView updates the view-title text', () => {
        // Stub loadDashboard to avoid cascading service calls
        const originalLoadDashboard = window.loadDashboard;
        window.loadDashboard = jest.fn();

        // Add a mock nav button and pane for the "devices" view
        const btn = document.createElement('button');
        btn.id = 'nav-devices';
        btn.className = 'nav-item';
        document.querySelector('.sidebar-nav').appendChild(btn);

        const pane = document.createElement('div');
        pane.id = 'devices-view';
        pane.className = 'view-pane';
        document.querySelector('.view-container').appendChild(pane);

        window.switchView('devices');

        expect(document.getElementById('view-title').textContent).toBe('Registered Devices');
        expect(btn.classList.contains('active')).toBe(true);
        expect(pane.classList.contains('active')).toBe(true);

        // Restore
        window.loadDashboard = originalLoadDashboard;
    });
});

describe('Theme Engine', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    test('changeTheme applies dark-theme class for dark mode', () => {
        window.changeTheme('dark');

        expect(document.documentElement.classList.contains('dark-theme')).toBe(true);
        expect(document.documentElement.classList.contains('light-theme')).toBe(false);
        expect(localStorage.getItem('roostos_theme')).toBe('dark');
    });

    test('changeTheme applies light-theme class for light mode', () => {
        window.changeTheme('light');

        expect(document.documentElement.classList.contains('light-theme')).toBe(true);
        expect(document.documentElement.classList.contains('dark-theme')).toBe(false);
        expect(localStorage.getItem('roostos_theme')).toBe('light');
    });
});

describe('Extension Registry', () => {
    test('registerExtension adds an extension and creates a nav button', () => {
        const ext = {
            id: 'test-ext',
            title: 'Test Extension',
            render: jest.fn()
        };

        window.RoostOS.registerExtension(ext);

        expect(window.RoostOS.extensions).toContainEqual(ext);
        const navButtons = document.querySelectorAll('.sidebar-nav .nav-item');
        const extButton = Array.from(navButtons).find(b => b.textContent === 'Test Extension');
        expect(extButton).toBeDefined();
    });

    test('registerExtension ignores duplicate extension ids', () => {
        const countBefore = window.RoostOS.extensions.length;
        window.RoostOS.registerExtension({
            id: 'test-ext',
            title: 'Duplicate',
            render: jest.fn()
        });

        expect(window.RoostOS.extensions.length).toBe(countBefore);
    });

    test('registerVpnFormHandler stores and retrieves VPN handlers', () => {
        const handler = { renderForm: jest.fn() };
        window.RoostOS.registerVpnFormHandler('wireguard', handler);

        expect(window.RoostOS.getVpnFormHandler('wireguard')).toBe(handler);
    });
});

describe('DeviceService', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        localStorage.setItem('roostos_token', 'test-token');
    });

    test('fetchDevices returns parsed device data', async () => {
        const mockData = {
            devices: [{ mac: 'AA:BB:CC:DD:EE:FF', name: 'Laptop' }],
            active_leases: [{ ip: '192.168.1.100', mac: 'AA:BB:CC:DD:EE:FF' }]
        };

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockData)
        });

        const result = await window.deviceService.fetchDevices();
        expect(result.devices).toHaveLength(1);
        expect(result.devices[0].name).toBe('Laptop');
        expect(result.active_leases).toHaveLength(1);
    });

    test('fetchDevices throws on non-ok response', async () => {
        fetch.mockResolvedValue({
            status: 500,
            ok: false
        });

        await expect(window.deviceService.fetchDevices()).rejects.toThrow('Failed to fetch devices');
    });
});

describe('NetworkService', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        localStorage.setItem('roostos_token', 'test-token');
    });

    test('fetchConfig populates global network and wifi settings', async () => {
        const mockNetworkData = {
            network: { interfaces: [{ name: 'eth0' }], bridges: [] },
            wifi: { radios: [{ name: 'wlan0' }] },
            vpns: []
        };

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockNetworkData)
        });

        const result = await window.networkService.fetchConfig();
        expect(window.networkSettings.interfaces).toHaveLength(1);
        expect(window.wifiSettings.radios).toHaveLength(1);
        expect(result.network.interfaces[0].name).toBe('eth0');
    });

    test('saveConfig sends POST with network, wifi, and vpns payload', async () => {
        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve({ success: true })
        });

        const network = { interfaces: [] };
        const wifi = { radios: [] };
        const vpns = [];

        await window.networkService.saveConfig(network, wifi, vpns);

        expect(fetch).toHaveBeenCalledWith('/api/network', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ network, wifi, vpns })
        }));
    });
});

describe('SecurityService', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        localStorage.setItem('roostos_token', 'test-token');
    });

    test('fetchSchedules returns schedule data', async () => {
        const mockSchedules = { schedules: [{ name: 'bedtime', days: ['mon'] }] };

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockSchedules)
        });

        const result = await window.securityService.fetchSchedules();
        expect(result.schedules).toHaveLength(1);
        expect(result.schedules[0].name).toBe('bedtime');
    });

    test('fetchDnsConfig populates global localDnsRecords', async () => {
        const mockDns = {
            upstream: '1.1.1.1',
            local_records: [{ domain: 'test.lan', ip: '10.0.0.1', type: 'A' }]
        };

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockDns)
        });

        const result = await window.securityService.fetchDnsConfig();
        expect(window.localDnsRecords).toHaveLength(1);
        expect(result.upstream).toBe('1.1.1.1');
    });

    test('fetchUsers returns user list', async () => {
        const mockUsers = [{ username: 'admin', role: 'admin' }];

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockUsers)
        });

        const result = await window.securityService.fetchUsers();
        expect(result).toHaveLength(1);
        expect(result[0].role).toBe('admin');
    });
});

describe('SystemService', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        localStorage.setItem('roostos_token', 'test-token');
    });

    test('fetchSystemSettings returns system telemetry', async () => {
        const mockSystem = {
            hostname: 'roost-router',
            cpu_load: 12.5,
            ram_usage: 45.0,
            uptime: '3 days'
        };

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockSystem)
        });

        const result = await window.systemService.fetchSystemSettings();
        expect(result.hostname).toBe('roost-router');
        expect(result.cpu_load).toBe(12.5);
    });

    test('fetchPlugins returns plugin list', async () => {
        const mockPlugins = [{ id: 'dns-technitium', name: 'Technitium DNS', enabled: true }];

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockPlugins)
        });

        const result = await window.systemService.fetchPlugins();
        expect(result).toHaveLength(1);
        expect(result[0].id).toBe('dns-technitium');
    });

    test('fetchBuildings returns buildings list', async () => {
        const mockBuildings = [{ id: 'main', name: 'Main House' }];

        fetch.mockResolvedValue({
            status: 200,
            ok: true,
            json: () => Promise.resolve(mockBuildings)
        });

        const result = await window.systemService.fetchBuildings();
        expect(result).toHaveLength(1);
        expect(result[0].name).toBe('Main House');
    });
});
