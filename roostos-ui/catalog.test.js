const fs = require('fs');
const path = require('path');

global.fetch = jest.fn();
global.alert = jest.fn();
global.confirm = jest.fn(() => true);
global.console.warn = jest.fn();

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

delete window.location;
window.location = { origin: 'http://localhost:8000', pathname: '/', search: '', href: 'http://localhost:8000/' };

// Load services and components
function loadScript(relPath) {
    const fullPath = path.resolve(__dirname, relPath);
    let content = fs.readFileSync(fullPath, 'utf8');
    content = content.replace(/import\s*\{[\s\S]*?\}\s*from\s*['"][^'"]+['"];?/g, '');
    content = content.replace(/import\s+.*?from\s+['"][^'"]+['"];?/g, '');
    content = content.replace(/^export\s+const\s+(\w+)\s*=/gm, 'global.$1 = window.$1 =');
    content = content.replace(/^export\s+class\s+(\w+)/gm, 'global.$1 = window.$1 = class $1');
    content = content.replace(/^export\s+/gm, '');
    (0, eval)(content);
}

loadScript('js/services/auth-service.js');
loadScript('js/services/catalog-service.js');
loadScript('js/components/app-catalog-templates.js');
loadScript('js/components/app-catalog.js');

describe('CatalogService', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-token');
    });

    test('fetchSources retrieves catalog sources', async () => {
        const mockSources = [{ id: 'core', name: 'Core Apps', url: 'file:///var/lib/roostos/catalog' }];
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ sources: mockSources })
        });

        const res = await window.catalogService.fetchSources();
        expect(res.sources).toHaveLength(1);
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/sources', expect.anything());
    });

    test('saveSource sends POST payload', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ id: 'custom', name: 'Custom Apps' })
        });

        const res = await window.catalogService.saveSource({ id: 'custom', name: 'Custom Apps', url: 'https://example.com' });
        expect(res.id).toBe('custom');
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/sources', expect.objectContaining({
            method: 'POST'
        }));
    });

    test('deleteSource sends DELETE request', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ message: 'Deleted' })
        });

        const res = await window.catalogService.deleteSource('custom');
        expect(res.message).toBe('Deleted');
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/sources/custom', expect.objectContaining({
            method: 'DELETE'
        }));
    });

    test('fetchApps queries all or filtered by category', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ apps: [{ id: 'homeassistant', category: 'automation' }] })
        });

        const res = await window.catalogService.fetchApps('automation');
        expect(res.apps).toHaveLength(1);
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/apps?category=automation', expect.anything());
    });

    test('installApp sends installation payload', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ message: 'Installed', app_id: 'homeassistant' })
        });

        const payload = { app_id: 'homeassistant', target_node: 'local', expose_edge_ingress: false };
        const res = await window.catalogService.installApp(payload);
        expect(res.message).toBe('Installed');
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/apps/install', expect.objectContaining({
            method: 'POST'
        }));
    });

    test('fetchImages and uploadImage handle local docker workflows', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ images: [{ repository: 'homeassistant/home-assistant', tag: 'latest' }] })
        });
        const images = await window.catalogService.fetchImages();
        expect(images.images).toHaveLength(1);

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ message: 'Image loaded successfully', images: ['my-image:latest'] })
        });
        const fakeFile = new Blob(['fake tar bytes'], { type: 'application/x-tar' });
        const uploadRes = await window.catalogService.uploadImage(fakeFile);
        expect(uploadRes.message).toContain('loaded successfully');
    });
});

describe('AppCatalogComponent', () => {
    let container;

    beforeEach(() => {
        jest.clearAllMocks();
        container = document.createElement('div');
        document.body.appendChild(container);

        window.catalogService.fetchSources = jest.fn().mockResolvedValue({
            sources: [
                { id: 'core', name: 'Core Apps', url: 'file:///var/lib/roostos/catalog', signing_key: null, enabled: true }
            ]
        });

        window.catalogService.fetchApps = jest.fn().mockResolvedValue({
            apps: [
                {
                    id: 'homeassistant',
                    name: 'Home Assistant',
                    version: '2024.5',
                    description: 'Smart home automation hub',
                    category: 'automation',
                    author: 'Home Assistant',
                    container: {
                        image: 'homeassistant/home-assistant:stable',
                        pull_policy: 'if_not_present',
                        ports: [{ host_port: 8123, container_port: 8123 }],
                        volumes: [{ host_path: '/opt/ha', container_path: '/config' }]
                    }
                }
            ]
        });

        window.catalogService.fetchImages = jest.fn().mockResolvedValue({
            images: [
                { repository: 'immich-app/immich-server', tag: 'release', id: 'sha256:123456789012', size: '350MB' }
            ]
        });

        window.catalogService.saveSource = jest.fn().mockResolvedValue({ message: 'Saved' });
        window.catalogService.deleteSource = jest.fn().mockResolvedValue({ message: 'Deleted' });
        window.catalogService.installApp = jest.fn().mockResolvedValue({ message: 'Installed' });
    });

    afterEach(() => {
        container.remove();
    });

    test('renders application cards and allows switching tabs', async () => {
        const el = document.createElement('roost-app-catalog');
        container.appendChild(el);
        await el.loadData();

        expect(el.innerHTML).toContain('Home Assistant');
        expect(el.innerHTML).toContain('Smart home automation hub');

        // Switch to Repositories tab
        const sourcesTabBtn = el.querySelector('button[data-tab="sources"]');
        expect(sourcesTabBtn).not.toBeNull();
        sourcesTabBtn.click();
        await Promise.resolve();

        expect(el.innerHTML).toContain('Catalog Repositories (1)');
        expect(el.innerHTML).toContain('Core Apps');

        // Switch to Local Images tab
        const imagesTabBtn = el.querySelector('button[data-tab="images"]');
        expect(imagesTabBtn).not.toBeNull();
        imagesTabBtn.click();
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(el.innerHTML).toContain('Air-Gapped Local Docker Image Deployment');
        expect(el.innerHTML).toContain('immich-app/immich-server');
    });

    test('handles inline add and edit rows for catalog repositories', async () => {
        const el = document.createElement('roost-app-catalog');
        container.appendChild(el);
        await el.loadData();

        // Switch to sources tab
        el.querySelector('button[data-tab="sources"]').click();

        // Click + Add Repository
        const addBtn = el.querySelector('#top-add-source-btn');
        addBtn.click();

        const addRow = el.querySelector('.inline-add-row');
        expect(addRow).not.toBeNull();

        addRow.querySelector('.src-id-input').value = 'selfhosted';
        addRow.querySelector('.src-name-input').value = 'LAN Catalog';
        addRow.querySelector('.src-url-input').value = 'http://192.168.1.50/catalog';

        addRow.querySelector('.save-source-btn').click();
        await Promise.resolve();

        expect(window.catalogService.saveSource).toHaveBeenCalledWith(expect.objectContaining({
            id: 'selfhosted',
            name: 'LAN Catalog',
            url: 'http://192.168.1.50/catalog'
        }));
    });

    test('shows install modal with permission consent before deploying', async () => {
        const el = document.createElement('roost-app-catalog');
        container.appendChild(el);
        await el.loadData();

        const installBtn = el.querySelector('.install-app-btn');
        installBtn.click();

        const modal = document.querySelector('#app-install-modal');
        expect(modal).not.toBeNull();
        expect(modal.innerHTML).toContain('Install Home Assistant');
        expect(modal.innerHTML).toContain('Required System Scopes &amp; Permissions');

        // Attempt submit without checking consent -> alert triggered
        const confirmBtn = modal.querySelector('#confirm-install-btn');
        confirmBtn.click();
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('consent'));
        expect(window.catalogService.installApp).not.toHaveBeenCalled();

        // Check consent and submit
        modal.querySelector('#install-consent-check').checked = true;
        confirmBtn.click();
        await Promise.resolve();

        expect(window.catalogService.installApp).toHaveBeenCalledWith(expect.objectContaining({
            app_id: 'homeassistant',
            target_node: 'local',
            expose_edge_ingress: false
        }));
    });
});
