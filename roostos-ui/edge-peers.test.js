const fs = require('fs');
const path = require('path');

global.fetch = jest.fn();
global.alert = jest.fn();
global.confirm = jest.fn(() => true);

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
    content = content.replace(/^export\s+class\s+(\w+)/gm, 'global.$1 = window.$1 = class $1');
    content = content.replace(/^export\s+/gm, '');
    (0, eval)(content);
}

loadScript('js/components/edge-gateway-templates.js');
loadScript('js/components/edge-gateway-modals.js');
loadScript('js/components/edge-gateway.js');

describe('Edge Gateway & WireGuard Mobile / Multi-Peer VPN Component', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-jwt');
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({ gateways: [] })
        });
        document.body.innerHTML = '<roost-edge-gateway id="edge-elem"></roost-edge-gateway>';
    });

    test('Loads gateway status, mobile/site peers, and proxy routes', async () => {
        global.fetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    gateways: [{
                        id: 'gw-1',
                        domain: 'vps.myroost.org',
                        public_ip: '203.0.113.10',
                        listen_port: 51820,
                        tunnel_ip_gateway: '10.42.0.1/24',
                        status: 'connected'
                    }]
                })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => [
                    { id: 'route-1', domain: 'home.myroost.org', target_ip: '192.168.1.100', target_port: 8080, ssl_enabled: true }
                ]
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => [
                    {
                        id: 'peer-1',
                        name: "Matt's iPhone",
                        peer_type: 'mobile',
                        assigned_ip: '10.42.0.10/32',
                        subnets: [],
                        route_internet: true,
                        qr_svg: '<svg id="qr-mock"></svg>'
                    },
                    {
                        id: 'peer-2',
                        name: 'Vacation Cabin',
                        peer_type: 'site',
                        assigned_ip: '10.42.0.3/32',
                        subnets: ['192.168.2.0/24'],
                        route_internet: false
                    }
                ]
            });

        const elem = document.getElementById('edge-elem');
        await elem.loadData();

        expect(elem.innerHTML).toContain('vps.myroost.org');
        expect(elem.innerHTML).toContain('Connected &amp; Active');
        expect(elem.innerHTML).toContain("Matt's iPhone");
        expect(elem.innerHTML).toContain('Vacation Cabin');
        expect(elem.innerHTML).toContain('192.168.2.0/24');
        expect(elem.innerHTML).toContain('home.myroost.org');
    });

    test('Inserts inline peer row and registers mobile device with QR modal', async () => {
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ gateways: [] }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] })
            .mockResolvedValueOnce({ ok: true, json: async () => [] });

        const elem = document.getElementById('edge-elem');
        await elem.loadData();

        const topAddBtn = elem.querySelector('#top-add-peer-btn');
        expect(topAddBtn).not.toBeNull();
        topAddBtn.click();

        const addRow = elem.querySelector('#peers-tbody .inline-add-row');
        expect(addRow).not.toBeNull();

        const nameInput = addRow.querySelector('.peer-name-input');
        const typeSelect = addRow.querySelector('.peer-type-select');
        const internetCheckbox = addRow.querySelector('.peer-internet-input');
        nameInput.value = 'Pixel 8 Pro';
        typeSelect.value = 'mobile';
        internetCheckbox.checked = true;

        const newPeerResponse = {
            id: 'peer-99',
            name: 'Pixel 8 Pro',
            peer_type: 'mobile',
            assigned_ip: '10.42.0.11/32',
            subnets: [],
            route_internet: true,
            qr_svg: '<svg id="new-peer-qr"></svg>',
            client_config: '[Interface]\nPrivateKey=xyz'
        };

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => newPeerResponse
        });

        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ gateways: [] }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] })
            .mockResolvedValueOnce({ ok: true, json: async () => [newPeerResponse] });

        const saveBtn = addRow.querySelector('.save-peer-btn');
        await saveBtn.onclick();

        expect(global.fetch).toHaveBeenCalledWith('/api/edge/peers', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
                name: 'Pixel 8 Pro',
                peer_type: 'mobile',
                subnets: [],
                route_internet: true
            })
        }));

        const qrModal = document.getElementById('peer-qr-modal');
        expect(qrModal).not.toBeNull();
        expect(qrModal.innerHTML).toContain('Pixel 8 Pro');
        expect(qrModal.innerHTML).toContain('svg id="new-peer-qr"');
    });

    test('Revokes WireGuard peer on confirm', async () => {
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ gateways: [] }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => [
                    { id: 'peer-revoke', name: 'Old Tablet', peer_type: 'mobile', assigned_ip: '10.42.0.15/32', subnets: [], route_internet: false }
                ]
            });

        const elem = document.getElementById('edge-elem');
        await elem.loadData();

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'success' })
        });
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ gateways: [] }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] })
            .mockResolvedValueOnce({ ok: true, json: async () => [] });

        const revokeBtn = elem.querySelector('.delete-peer-btn');
        expect(revokeBtn).not.toBeNull();
        await elem.deletePeer('peer-revoke');

        expect(global.fetch).toHaveBeenCalledWith('/api/edge/peers/peer-revoke', expect.objectContaining({
            method: 'DELETE'
        }));
    });

    test('Opens QR modal on QR / Config button click', async () => {
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ gateways: [] }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => [
                    { id: 'peer-qr-test', name: 'Work Phone', peer_type: 'mobile', assigned_ip: '10.42.0.12/32', subnets: [], route_internet: true, qr_svg: '<svg id="work-phone-qr"></svg>' }
                ]
            });

        const elem = document.getElementById('edge-elem');
        await elem.loadData();

        const qrBtn = elem.querySelector('.view-peer-qr-btn');
        expect(qrBtn).not.toBeNull();
        qrBtn.click();

        const modal = document.getElementById('peer-qr-modal');
        expect(modal).not.toBeNull();
        expect(modal.innerHTML).toContain('Work Phone');
        expect(modal.innerHTML).toContain('/api/edge/peers/peer-qr-test/config');
    });
});
