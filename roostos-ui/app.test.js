const fs = require('fs');
const path = require('path');

// Mock window globals before evaluating the script
global.fetch = jest.fn();
global.alert = jest.fn();

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

// Stub dynamic DOM elements that might be manipulated on load/initialization
document.body.innerHTML = `
    <div class="sidebar-nav">
        <button class="nav-item">Dashboard</button>
        <button class="nav-item">Plugins</button>
    </div>
    <div class="view-container"></div>
    <div id="view-title">Dashboard</div>
`;

// Read and execute the entire app.js file into the test global scope
const appJsPath = path.resolve(__dirname, './app.js');
const appJsContent = fs.readFileSync(appJsPath, 'utf8');
eval(appJsContent);

describe('RoostOS app.js Frontend Unit Tests', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        window.location.search = '';
        window.location.href = 'http://localhost:8000/';
    });

    test('apiFetch attaches authorization header if token exists', async () => {
        localStorage.setItem('roostos_token', 'mock-jwt-token-123');
        fetch.mockResolvedValue({
            status: 200,
            json: () => Promise.resolve({ success: true })
        });

        const response = await apiFetch('/api/devices');
        expect(response.status).toBe(200);
        expect(fetch).toHaveBeenCalledWith('/api/devices', {
            headers: {
                'Authorization': 'Bearer mock-jwt-token-123'
            }
        });
    });

    test('apiFetch handles 401 Unauthorized by clearing token and redirecting', async () => {
        localStorage.setItem('roostos_token', 'expired-token');
        fetch.mockResolvedValue({
            status: 401
        });

        await expect(apiFetch('/api/devices')).rejects.toThrow('Unauthorized session');
        
        expect(localStorage.getItem('roostos_token')).toBeNull();
        expect(window.location.href).toContain('/oauth/authorize');
    });

    test('logout clears localStorage and redirects to login endpoint', () => {
        localStorage.setItem('roostos_token', 'some-valid-token');
        
        logout();

        expect(localStorage.getItem('roostos_token')).toBeNull();
        expect(window.location.href).toContain('/oauth/authorize?client_id=roostos-ui');
    });

    test('handleAuthentication returns false and redirects when no token is present', () => {
        const result = handleAuthentication();
        
        expect(result).toBe(false);
        expect(window.location.href).toContain('/oauth/authorize?client_id=roostos-ui');
    });

    test('handleAuthentication returns true if token exists and no oauth code in URL', () => {
        localStorage.setItem('roostos_token', 'active-token');
        
        const result = handleAuthentication();
        
        expect(result).toBe(true);
    });
});
