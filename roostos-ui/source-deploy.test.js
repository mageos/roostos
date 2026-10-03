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
loadScript('js/components/app-catalog-modal.js');
loadScript('js/components/app-catalog-templates.js');
loadScript('js/components/app-catalog.js');

describe('Source Deploy Service & Component', () => {
    let container;

    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-token');
        container = document.createElement('div');
        document.body.appendChild(container);
    });

    afterEach(() => {
        container.remove();
    });

    test('inspectManifest sends inspect POST request', async () => {
        const mockManifest = {
            id: 'custom-tool',
            name: 'Custom Tool',
            version: '1.0.0',
            description: 'A tool built from source',
            container: { image: '', ports: [{ host_port: 8080, container_port: 8080 }] }
        };
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockManifest
        });

        const res = await window.catalogService.inspectManifest(
            'https://github.com/example/tool.git',
            'main'
        );

        expect(res.id).toBe('custom-tool');
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/manifest/inspect', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
                source_url_or_path: 'https://github.com/example/tool.git',
                git_ref: 'main'
            })
        }));
    });

    test('buildAndInstallFromSource sends build POST request', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                message: 'Successfully built and installed',
                app_id: 'custom-tool',
                plugin_id: 'plugin-custom-tool',
                ingress_domain: 'custom-tool.local.mesh'
            })
        });

        const payload = {
            source_url_or_path: 'https://github.com/example/tool.git',
            git_ref: 'main',
            target_node: 'local',
            expose_edge_ingress: true
        };
        const res = await window.catalogService.buildAndInstallFromSource(payload);

        expect(res.message).toContain('Successfully built');
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/build-and-install', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify(payload)
        }));
    });

    test('importAppFromSource sends import POST request', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                message: 'Successfully imported',
                app: { id: 'custom-tool' }
            })
        });

        const payload = {
            source_url_or_path: 'https://github.com/example/tool.git',
            git_ref: 'main',
            approve_network: true
        };
        const res = await window.catalogService.importAppFromSource(payload);

        expect(res.success).toBe(true);
        expect(global.fetch).toHaveBeenCalledWith('/api/catalog/import', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify(payload)
        }));
    });

    test('renders source tab and handles inspect & import interaction', async () => {
        window.catalogService.fetchSources = jest.fn().mockResolvedValue({ sources: [] });
        window.catalogService.fetchApps = jest.fn().mockResolvedValue({ apps: [] });
        window.catalogService.fetchImages = jest.fn().mockResolvedValue({ images: [] });

        const mockManifest = {
            id: 'my-service',
            name: 'My Service',
            version: '2.1.0',
            description: 'Custom microservice',
            category: 'tools',
            author: 'Developer',
            container: {
                ports: [{ host_port: 5000, container_port: 5000 }],
                volumes: [{ host_path: '/tmp/data', container_path: '/data' }]
            },
            permissions: { scopes: ['network_read'] }
        };

        window.catalogService.inspectManifest = jest.fn().mockResolvedValue(mockManifest);
        window.catalogService.importAppFromSource = jest.fn().mockResolvedValue({
            success: true,
            message: 'App imported',
            app: mockManifest
        });

        const el = document.createElement('roost-app-catalog');
        container.appendChild(el);
        await el.loadData();

        // Switch to Source Import tab
        const sourceTabBtn = el.querySelector('button[data-tab="source"]');
        expect(sourceTabBtn).not.toBeNull();
        sourceTabBtn.click();

        expect(el.innerHTML).toContain('Build &amp; Import Application from Source');
        expect(el.innerHTML).toContain('Inspect Manifest');

        // Fill in source URL
        const gitInput = el.querySelector('#source-input');
        expect(gitInput).not.toBeNull();
        gitInput.value = 'https://github.com/myorg/myservice.git';

        // Click Inspect button
        const inspectBtn = el.querySelector('#inspect-manifest-btn');
        inspectBtn.click();
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(window.catalogService.inspectManifest).toHaveBeenCalledWith(
            'https://github.com/myorg/myservice.git',
            'main'
        );

        // Check that manifest preview is rendered
        expect(el.innerHTML).toContain('My Service');
        expect(el.innerHTML).toContain('Custom microservice');
        expect(el.innerHTML).toContain('5000➔5000');

        // Consent required before import
        const deployBtn = el.querySelector('#deploy-source-btn');
        expect(deployBtn).not.toBeNull();
        deployBtn.click();
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('consent'));

        // Check consent and import
        const consentBox = el.querySelector('#source-consent-check');
        consentBox.checked = true;
        deployBtn.click();
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(window.catalogService.importAppFromSource).toHaveBeenCalledWith(expect.objectContaining({
            source_url_or_path: 'https://github.com/myorg/myservice.git',
            git_ref: 'main'
        }));
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('Successfully imported My Service into Local Catalog!'));
    });

    test('blocks import when network required and approval not checked', async () => {
        window.catalogService.fetchSources = jest.fn().mockResolvedValue({ sources: [] });
        window.catalogService.fetchApps = jest.fn().mockResolvedValue({ apps: [] });
        window.catalogService.fetchImages = jest.fn().mockResolvedValue({ images: [] });

        const mockManifest = {
            id: 'net-service',
            name: 'Network Service',
            version: '1.0.0',
            description: 'Needs network to build',
            build: {
                sandbox: {
                    network_required: true,
                    allowed_endpoints: ['registry.npmjs.org'],
                    network_justification: 'Fetch npm packages'
                }
            }
        };

        window.catalogService.inspectManifest = jest.fn().mockResolvedValue(mockManifest);
        window.catalogService.importAppFromSource = jest.fn().mockResolvedValue({
            success: true,
            app: mockManifest
        });

        const el = document.createElement('roost-app-catalog');
        container.appendChild(el);
        await el.loadData();

        el.querySelector('button[data-tab="source"]').click();
        el.querySelector('#source-input').value = 'https://github.com/myorg/netservice.git';
        el.querySelector('#inspect-manifest-btn').click();
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(el.innerHTML).toContain('Network Access Required');
        expect(el.innerHTML).toContain('registry.npmjs.org');

        el.querySelector('#source-consent-check').checked = true;
        el.querySelector('#deploy-source-btn').click();
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('review and approve the requested network access'));
        expect(window.catalogService.importAppFromSource).not.toHaveBeenCalled();

        // Check approve-network-check
        el.querySelector('#approve-network-check').checked = true;
        el.querySelector('#deploy-source-btn').click();
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(window.catalogService.importAppFromSource).toHaveBeenCalledWith(expect.objectContaining({
            approve_network: true,
            approved_endpoints: ['registry.npmjs.org']
        }));
    });
});
