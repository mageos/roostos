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

loadScript('js/components/network-topology-diagram.js');
loadScript('js/components/network-topology-templates.js');
loadScript('js/components/network-topology.js');
loadScript('js/components/network-view.js');

describe('Network Topology & Inter-Network Routing Component', () => {
    const mockTopologyData = {
        networks: [
            { id: "office-lan", name: "Primary LAN", subnet: "10.0.1.0/24", gateway_ip: "10.0.1.1", network_type: "lan", interface: "br-lan" },
            { id: "upstream-wan", name: "Upstream WAN", subnet: "198.51.100.0/24", gateway_ip: "198.51.100.1", network_type: "wan_upstream", interface: "eth0" },
            { id: "wg-overlay", name: "WireGuard Hub", subnet: "10.42.0.0/24", gateway_ip: "10.42.0.1", network_type: "vpn_overlay", interface: "wg-edge" },
            { id: "cloud-vpc", name: "Cloud VPC", subnet: "10.100.0.0/16", gateway_ip: "10.100.0.1", network_type: "cloud_vpc", interface: "vps-eth0" }
        ],
        links: [
            {
                id: "link-office-wan",
                source_network_id: "office-lan",
                target_network_id: "upstream-wan",
                connection_type: "physical_wan",
                routing_mode: "nat_masquerade",
                firewall_policy: "source_to_target_only",
                allowed_ports: []
            },
            {
                id: "link-office-wg",
                source_network_id: "office-lan",
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

        expect(elem.innerHTML).toContain('10.0.1.0/24');
        expect(elem.innerHTML).toContain('198.51.100.0/24');
        expect(elem.innerHTML).toContain('10.42.0.0/24');
        expect(elem.innerHTML).toContain('10.100.0.0/16');
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

        await elem.deleteLink('link-office-wan');
        expect(global.fetch).toHaveBeenCalledWith('/api/network/topology/links/link-office-wan', expect.objectContaining({
            method: 'DELETE'
        }));
    });

    test('Renders interactive SVG architectural diagram and switches views', async () => {
        const elem = document.getElementById('topo-elem');
        await elem.loadData();

        // Check SVG diagram is rendered
        const svg = elem.querySelector('.topology-diagram-container svg');
        expect(svg).not.toBeNull();
        expect(svg.querySelectorAll('.diagram-node').length).toBe(4);
        expect(svg.querySelectorAll('.diagram-edge').length).toBe(2);

        // Click a diagram node to select it
        const firstNode = svg.querySelector('.diagram-node[data-node-id="office-lan"]');
        expect(firstNode).not.toBeNull();
        firstNode.onclick();
        expect(elem.selectedNodeId).toBe('office-lan');

        // Toggle to Cards view
        const cardsBtn = elem.querySelector('#toggle-view-cards');
        expect(cardsBtn).not.toBeNull();
        cardsBtn.click();
        expect(elem.querySelector('#topology-cards-section').style.display).not.toBe('none');

        // Toggle back to Diagram view
        const diagBtn = elem.querySelector('#toggle-view-diagram');
        expect(diagBtn).not.toBeNull();
        diagBtn.click();
        expect(elem.querySelector('#topology-diagram-section').style.display).toBe('block');
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
