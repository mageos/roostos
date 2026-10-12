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

loadScript('js/components/network-topology-templates.js');
loadScript('js/components/network-topology.js');
loadScript('js/components/network-view.js');

describe('Network Topology & Inter-Network Routing Component', () => {
    const mockTopologyData = {
        networks: [
            { id: "lab-lan", name: "RoostOS Lab", subnet: "192.168.1.0/24", gateway_ip: "192.168.1.1", network_type: "lan", interface: "br-lan" },
            { id: "home-lan", name: "Upstream Home", subnet: "192.168.5.0/24", gateway_ip: "192.168.5.1", network_type: "wan_upstream", interface: "eth0" },
            { id: "wg-overlay", name: "WireGuard Hub", subnet: "10.42.0.0/24", gateway_ip: "10.42.0.1", network_type: "vpn_overlay", interface: "wg-edge" },
            { id: "vps-vpc", name: "Cloud VPS", subnet: "172.26.0.0/20", gateway_ip: "172.26.2.49", network_type: "cloud_vpc", interface: "vps-eth0" }
        ],
        links: [
            {
                id: "link-lab-home",
                source_network_id: "lab-lan",
                target_network_id: "home-lan",
                connection_type: "physical_wan",
                routing_mode: "nat_masquerade",
                firewall_policy: "source_to_target_only",
                allowed_ports: []
            },
            {
                id: "link-lab-wg",
                source_network_id: "lab-lan",
                target_network_id: "wg-overlay",
                connection_type: "wireguard_tunnel",
                routing_mode: "routed",
                firewall_policy: "bidirectional_allow",
                allowed_ports: []
            }
        ]
    };

    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-jwt');
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => mockTopologyData
        });
        document.body.innerHTML = '<roost-network-topology id="topo-elem"></roost-network-topology>';
    });

    test('Renders visual topology subnet cards, links table, and subnets registry', async () => {
        const elem = document.getElementById('topo-elem');
        await elem.loadData();

        expect(elem.innerHTML).toContain('192.168.1.0/24');
        expect(elem.innerHTML).toContain('192.168.5.0/24');
        expect(elem.innerHTML).toContain('10.42.0.0/24');
        expect(elem.innerHTML).toContain('172.26.0.0/20');
        expect(elem.innerHTML).toContain('Physical WAN Uplink');
        expect(elem.innerHTML).toContain('WireGuard Tunnel');
        expect(elem.innerHTML).toContain('NAT / Masquerade');
        expect(elem.innerHTML).toContain('Allow Both Ways');
    });

    test('Inserts inline connection form and creates new inter-network link', async () => {
        const elem = document.getElementById('topo-elem');
        await elem.loadData();

        const addBtn = elem.querySelector('#top-add-link-btn');
        expect(addBtn).not.toBeNull();
        addBtn.click();

        const addRow = elem.querySelector('#links-tbody .inline-add-row');
        expect(addRow).not.toBeNull();

        addRow.querySelector('.link-src-select').value = 'wg-overlay';
        addRow.querySelector('.link-tgt-select').value = 'vps-vpc';
        addRow.querySelector('.link-type-select').value = 'vpc_peering';
        addRow.querySelector('.link-routing-select').value = 'routed';
        addRow.querySelector('.link-policy-select').value = 'restricted';
        addRow.querySelector('.link-ports-input').value = '80, 443';

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ id: 'new-link' })
        });
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockTopologyData
        });

        await addRow.querySelector('.save-link-btn').onclick();

        expect(global.fetch).toHaveBeenCalledWith('/api/network/topology/links', expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('"vpc_peering"')
        }));
    });

    test('Deletes an inter-network link on confirm', async () => {
        const elem = document.getElementById('topo-elem');
        await elem.loadData();

        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) });
        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => mockTopologyData });

        await elem.deleteLink('link-lab-home');
        expect(global.fetch).toHaveBeenCalledWith('/api/network/topology/links/link-lab-home', expect.objectContaining({
            method: 'DELETE'
        }));
    });

    test('NetworkViewComponent activates topology subtab pane on switch', () => {
        const viewComp = document.createElement('roost-network-view');
        document.body.appendChild(viewComp);

        const topoBtn = viewComp.querySelector('.sub-tab-btn[data-subtab="topology"]');
        expect(topoBtn).not.toBeNull();

        viewComp.switchSubtab('topology');
        expect(viewComp.querySelector('#pane-topology').style.display).toBe('block');
        expect(viewComp.querySelector('#pane-interfaces').style.display).toBe('none');

        viewComp.remove();
    });
});
