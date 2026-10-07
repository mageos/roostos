const fs = require('fs');
const path = require('path');

global.fetch = jest.fn();
global.alert = jest.fn();
global.confirm = jest.fn(() => true);
global.console.error = jest.fn();

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
loadScript('js/services/cluster-service.js');
loadScript('js/components/cluster-templates.js');
loadScript('js/components/cluster-management.js');

describe('ClusterService', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-token');
    });

    test('fetchClusterStatus retrieves cluster status info', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ role: 'controller', is_controller: true, node_id: 'node-01', registered_nodes_count: 2 })
        });
        const status = await window.clusterService.fetchClusterStatus();
        expect(status.role).toBe('controller');
        expect(status.registered_nodes_count).toBe(2);
        expect(global.fetch).toHaveBeenCalledWith('/api/cluster/status', expect.anything());
    });

    test('fetchNodes retrieves node roster', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ nodes: [
                { id: 'node-01', name: 'Gateway', roles: ['controller', 'gateway_router'] },
                { id: 'node-02', name: 'Compute Node', roles: ['compute'] }
            ]})
        });
        const nodes = await window.clusterService.fetchNodes();
        expect(nodes).toHaveLength(2);
        expect(nodes[1].id).toBe('node-02');
    });

    test('saveNode sends POST payload', async () => {
        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) });
        const payload = { id: 'node-02', name: 'Compute Node', roles: ['compute'] };
        const res = await window.clusterService.saveNode(payload);
        expect(res.status).toBe('success');
        expect(global.fetch).toHaveBeenCalledWith('/api/cluster/nodes', expect.objectContaining({
            method: 'POST', body: JSON.stringify(payload)
        }));
    });

    test('removeNode sends DELETE request', async () => {
        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) });
        const res = await window.clusterService.removeNode('node-02');
        expect(res.status).toBe('success');
        expect(global.fetch).toHaveBeenCalledWith('/api/cluster/nodes/node-02', expect.objectContaining({ method: 'DELETE' }));
    });

    test('generateJoinToken calls token endpoint', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true, json: async () => ({ status: 'success', token: 'roost-test-token-123' })
        });
        const res = await window.clusterService.generateJoinToken();
        expect(res.token).toBe('roost-test-token-123');
        expect(global.fetch).toHaveBeenCalledWith('/api/cluster/token', expect.objectContaining({ method: 'POST' }));
    });

    test('fetchClusterUpdates retrieves fleet updates', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                total_upgradable: 5, total_security_upgradable: 2, reboot_required_nodes: ['node-02'],
                nodes: { 'node-02': { upgradable: 5, security_upgradable: 2, reboot_required: true } }
            })
        });
        const updates = await window.clusterService.fetchClusterUpdates();
        expect(updates.total_upgradable).toBe(5);
        expect(updates.total_security_upgradable).toBe(2);
        expect(global.fetch).toHaveBeenCalledWith('/api/cluster/updates', expect.anything());
    });

    test('triggerNodeUpdate queues remote update command', async () => {
        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', command: 'install_updates' }) });
        const res = await window.clusterService.triggerNodeUpdate('node-02', false);
        expect(res.status).toBe('success');
        expect(global.fetch).toHaveBeenCalledWith('/api/cluster/nodes/node-02/updates/install?security_only=false', expect.objectContaining({ method: 'POST' }));
    });
});

describe('ClusterManagementComponent UI', () => {
    let comp;

    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-token');
        document.body.innerHTML = '<div class="view-container"></div>';

        global.fetch.mockImplementation((url) => {
            if (url.includes('/api/cluster/status')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ role: 'controller', is_controller: true, node_id: 'node-01', registered_nodes_count: 2, controller_url: null })
                });
            }
            if (url.includes('/api/cluster/nodes')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({
                        nodes: [
                            { id: 'node-01', name: 'Gateway Node', roles: ['controller', 'gateway_router'], management_ip: '192.168.1.1' },
                            { id: 'node-02', name: 'Compute Node', roles: ['compute'], management_ip: '192.168.1.50' }
                        ]
                    })
                });
            }
            if (url.includes('/api/cluster/updates')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({
                        total_upgradable: 2, total_security_upgradable: 1, reboot_required_nodes: [],
                        nodes: { 'node-02': { upgradable: 2, security_upgradable: 1, reboot_required: false } }
                    })
                });
            }
            return Promise.resolve({ ok: true, json: async () => ({}) });
        });

        comp = new window.ClusterManagementComponent();
        document.querySelector('.view-container').appendChild(comp);
    });

    test('renders cluster overview, node roster, and fleet updates', async () => {
        await comp.loadData();
        expect(comp.innerHTML).toContain('CONTROLLER');
        expect(comp.innerHTML).toContain('Enrolled Nodes');
        expect(comp.innerHTML).toContain('Gateway Node');
        expect(comp.innerHTML).toContain('Compute Node');
        expect(comp.innerHTML).toContain('Fleet OS Updates Summary');
        expect(comp.innerHTML).toContain('Fleet Upgradable Packages');
    });

    test('top and bottom add buttons trigger inline add row', async () => {
        await comp.loadData();
        const topBtn = comp.querySelector('#top-add-node-btn');
        const bottomBtn = comp.querySelector('#bottom-add-node-btn');
        expect(topBtn).not.toBeNull();
        expect(bottomBtn).not.toBeNull();

        topBtn.click();
        let addRow = comp.querySelector('.inline-add-row');
        expect(addRow).not.toBeNull();
        expect(addRow.querySelector('#node-form-id')).not.toBeNull();
        expect(addRow.querySelector('#node-form-name')).not.toBeNull();

        // Clicking cancel removes the row
        addRow.querySelector('#cancel-node-row-btn').click();
        expect(comp.querySelector('.inline-add-row')).toBeNull();

        // Bottom button also works
        bottomBtn.click();
        expect(comp.querySelector('.inline-add-row')).not.toBeNull();
    });

    test('inline add row saves new node and reloads data', async () => {
        await comp.loadData();
        comp.querySelector('#top-add-node-btn').click();
        const addRow = comp.querySelector('.inline-add-row');

        addRow.querySelector('#node-form-id').value = 'node-03';
        addRow.querySelector('#node-form-name').value = 'Storage Vault';
        addRow.querySelector('#node-form-roles').value = 'storage, compute';
        addRow.querySelector('#node-form-ip').value = '192.168.1.60';

        const saveSpy = jest.spyOn(window.clusterService, 'saveNode').mockResolvedValueOnce({ status: 'success' });
        const loadSpy = jest.spyOn(comp, 'loadData').mockResolvedValueOnce();

        await addRow.querySelector('#save-node-row-btn').click();

        expect(saveSpy).toHaveBeenCalledWith(expect.objectContaining({
            id: 'node-03', name: 'Storage Vault', roles: ['storage', 'compute'], management_ip: '192.168.1.60'
        }));
        expect(loadSpy).toHaveBeenCalled();
    });

    test('clicking edit on a node row opens inline edit row', async () => {
        await comp.loadData();
        const editBtn = comp.querySelector('.edit-node-btn[data-id="node-02"]');
        expect(editBtn).not.toBeNull();

        editBtn.click();
        const editRow = comp.querySelector('.inline-edit-row');
        expect(editRow).not.toBeNull();
        expect(editRow.querySelector('#node-form-name').value).toBe('Compute Node');
        expect(editRow.querySelector('#node-form-roles').value).toBe('compute');

        // Cancel restores table view
        editRow.querySelector('#cancel-node-row-btn').click();
        expect(comp.querySelector('.inline-edit-row')).toBeNull();
        expect(comp.querySelector('#node-row-node-02')).not.toBeNull();
    });

    test('generates pairing join token and renders token alert banner', async () => {
        await comp.loadData();
        jest.spyOn(window.clusterService, 'generateJoinToken').mockResolvedValueOnce({
            status: 'success', token: 'roost-token-abc', expires_in_seconds: 600
        });

        await comp.querySelector('#gen-token-btn').click();
        expect(comp.innerHTML).toContain('Worker Node Pairing Token');
        expect(comp.innerHTML).toContain('roost-token-abc');
        expect(comp.querySelector('#copy-token-btn')).not.toBeNull();

        // Dismiss hides the banner
        comp.querySelector('#dismiss-token-btn').click();
        expect(comp.innerHTML).not.toContain('Worker Node Pairing Token');
    });

    test('clicking update button calls triggerNodeUpdate', async () => {
        await comp.loadData();
        const updateBtn = comp.querySelector('.update-node-btn[data-id="node-02"]');
        expect(updateBtn).not.toBeNull();

        const updateSpy = jest.spyOn(window.clusterService, 'triggerNodeUpdate').mockResolvedValueOnce({ status: 'success' });
        const loadSpy = jest.spyOn(comp, 'loadData').mockResolvedValueOnce();

        await updateBtn.click();
        expect(updateSpy).toHaveBeenCalledWith('node-02', false);
        expect(loadSpy).toHaveBeenCalled();
    });

    test('clicking promote button calls promoteNode and refreshes data', async () => {
        await comp.loadData();
        const promoteBtn = comp.querySelector('.promote-node-btn[data-id="node-02"]');
        expect(promoteBtn).not.toBeNull();

        const promoteSpy = jest.spyOn(window.clusterService, 'promoteNode').mockResolvedValueOnce({ status: 'promoted', epoch: 2 });
        const loadSpy = jest.spyOn(comp, 'loadData').mockResolvedValueOnce();

        await promoteBtn.click();
        expect(promoteSpy).toHaveBeenCalledWith('node-02');
        expect(loadSpy).toHaveBeenCalled();
    });
});
