/**
 * HTML Templates for Network Topology and Inter-Network Routing Component
 */

export const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export const renderTopologyTemplate = (networks = [], links = [], netRowsHtml = "", linkRowsHtml = "") => html`
    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Inter-Network Topology Map</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Visual architecture of physical LANs, WAN uplinks, WireGuard overlay tunnels, and Cloud VPC subnets.
                </p>
            </div>
            <span class="badge badge-success">${networks.length} Subnets • ${links.length} Connected Links</span>
        </div>

        <!-- Visual Subnet Nodes Grid -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 16px;">
            ${networks.map(n => renderTopologyCard(n, links)).join("")}
        </div>
    </div>

    <!-- Inter-Network Connections & Routing Policies -->
    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Inter-Network Connections & Routing Rules (${links.length})</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Define how subnets connect to each other (Physical WAN, WireGuard Tunnel, VPC Peering) and their firewall policies.
                </p>
            </div>
            <button class="btn btn-primary btn-sm" id="top-add-link-btn">+ Add Connection</button>
        </div>
        <div class="table-responsive">
            <table class="data-table" id="links-table">
                <thead>
                    <tr>
                        <th>Connection Path</th>
                        <th>Link Type</th>
                        <th>Routing Mode</th>
                        <th>Firewall Policy</th>
                        <th>Allowed Ports</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="links-tbody">${linkRowsHtml}</tbody>
            </table>
        </div>
        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-link-btn">+ Add Connection</button>
        </div>
    </div>

    <!-- Managed Subnets Registry -->
    <div class="card">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Managed Subnets Registry (${networks.length})</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Inventory of local, upstream, and remote subnets participating in the network topology.
                </p>
            </div>
            <button class="btn btn-primary btn-sm" id="top-add-net-btn">+ Add Subnet</button>
        </div>
        <div class="table-responsive">
            <table class="data-table" id="nets-table">
                <thead>
                    <tr>
                        <th>Network Name</th>
                        <th>Subnet CIDR</th>
                        <th>Gateway IP</th>
                        <th>Type</th>
                        <th>Interface</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="nets-tbody">${netRowsHtml}</tbody>
            </table>
        </div>
        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-net-btn">+ Add Subnet</button>
        </div>
    </div>
`;

export const renderTopologyCard = (n, links) => {
    const typeIcons = {
        lan: "🖥️ Local LAN",
        wan_upstream: "🌐 Upstream Home / WAN",
        vpn_overlay: "🔒 WireGuard Transit",
        cloud_vpc: "☁️ Cloud VPS VPC",
        dmz: "🛡️ DMZ",
        guest: "👥 Guest Wi-Fi",
    };
    const outgoing = links.filter(l => l.source_network_id === n.id);
    const incoming = links.filter(l => l.target_network_id === n.id);

    return html`
    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <strong style="font-size: 14px;">${n.name}</strong>
            <span class="badge badge-outline" style="font-size: 11px;">${typeIcons[n.network_type] || n.network_type}</span>
        </div>
        <div style="font-family: monospace; font-size: 15px; font-weight: 600; color: #38bdf8; margin-bottom: 4px;">
            ${n.subnet}
        </div>
        <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
            Gateway: <code>${n.gateway_ip || 'None'}</code> • Interface: <code>${n.interface || 'auto'}</code>
        </div>
        <div style="font-size: 11px; border-top: 1px solid rgba(255,255,255,0.07); padding-top: 8px; color: var(--text-secondary);">
            🔗 Links: ${outgoing.length} outgoing, ${incoming.length} incoming
        </div>
    </div>
    `;
};

export const renderLinkRowTemplate = (l, networks) => {
    const srcNet = networks.find(n => n.id === l.source_network_id);
    const tgtNet = networks.find(n => n.id === l.target_network_id);
    const typeLabels = {
        physical_wan: "🌐 Physical WAN Uplink",
        wireguard_tunnel: "🔒 WireGuard Tunnel",
        vpc_peering: "☁️ VPC Peering / Cloud",
        direct_bridge: "🌉 Direct L2 Bridge",
        static_route: "🔀 Static Route",
    };
    const routingBadges = {
        nat_masquerade: `<span class="badge badge-warning">NAT / Masquerade</span>`,
        routed: `<span class="badge badge-success">Direct Routed</span>`,
        isolated: `<span class="badge badge-danger">Isolated</span>`,
    };
    const policyBadges = {
        source_to_target_only: `<span class="badge badge-secondary">One-Way Outbound</span>`,
        bidirectional_allow: `<span class="badge badge-success">Allow Both Ways</span>`,
        restricted: `<span class="badge badge-warning">Restricted Ports</span>`,
        block: `<span class="badge badge-danger">Blocked</span>`,
    };

    return html`
    <tr id="link-row-${l.id}">
        <td>
            <strong>${srcNet ? srcNet.name : l.source_network_id}</strong>
            <span style="color: var(--text-secondary); margin: 0 4px;">&rarr;</span>
            <strong>${tgtNet ? tgtNet.name : l.target_network_id}</strong>
            ${l.description ? `<div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${l.description}</div>` : ''}
        </td>
        <td>${typeLabels[l.connection_type] || l.connection_type}</td>
        <td>${routingBadges[l.routing_mode] || l.routing_mode}</td>
        <td>${policyBadges[l.firewall_policy] || l.firewall_policy}</td>
        <td>${l.allowed_ports && l.allowed_ports.length > 0 ? l.allowed_ports.map(p => `<code>${p}</code>`).join(", ") : '<span style="color: var(--text-secondary);">All</span>'}</td>
        <td>
            <button class="btn btn-secondary btn-sm edit-link-btn" data-id="${l.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-link-btn" data-id="${l.id}">Delete</button>
        </td>
    </tr>
    `;
};

export const renderInlineLinkFormTemplate = (l = {}, networks = []) => html`
    <tr class="inline-add-row" ${l.id ? `id="edit-link-row-${l.id}"` : ''}>
        <td>
            <div style="display: flex; gap: 6px; align-items: center; margin-bottom: 4px;">
                <select class="inline-input link-src-select">
                    ${networks.map(n => `<option value="${n.id}" ${l.source_network_id === n.id ? 'selected' : ''}>${n.name} (${n.subnet})</option>`).join("")}
                </select>
                <span>&rarr;</span>
                <select class="inline-input link-tgt-select">
                    ${networks.map(n => `<option value="${n.id}" ${l.target_network_id === n.id ? 'selected' : ''}>${n.name} (${n.subnet})</option>`).join("")}
                </select>
            </div>
            <input type="text" class="inline-input link-desc-input" placeholder="Description (e.g. Lab WAN uplink)" value="${l.description || ''}" style="font-size: 11px;">
        </td>
        <td>
            <select class="inline-input link-type-select">
                <option value="wireguard_tunnel" ${l.connection_type === 'wireguard_tunnel' ? 'selected' : ''}>🔒 WireGuard Tunnel</option>
                <option value="physical_wan" ${l.connection_type === 'physical_wan' ? 'selected' : ''}>🌐 Physical WAN Uplink</option>
                <option value="vpc_peering" ${l.connection_type === 'vpc_peering' ? 'selected' : ''}>☁️ VPC Peering / Cloud</option>
                <option value="direct_bridge" ${l.connection_type === 'direct_bridge' ? 'selected' : ''}>🌉 Direct L2 Bridge</option>
                <option value="static_route" ${l.connection_type === 'static_route' ? 'selected' : ''}>🔀 Static Route</option>
            </select>
        </td>
        <td>
            <select class="inline-input link-routing-select">
                <option value="routed" ${l.routing_mode === 'routed' ? 'selected' : ''}>Direct Routed (No NAT)</option>
                <option value="nat_masquerade" ${l.routing_mode === 'nat_masquerade' ? 'selected' : ''}>NAT / Masquerade</option>
                <option value="isolated" ${l.routing_mode === 'isolated' ? 'selected' : ''}>Isolated</option>
            </select>
        </td>
        <td>
            <select class="inline-input link-policy-select">
                <option value="source_to_target_only" ${l.firewall_policy === 'source_to_target_only' ? 'selected' : ''}>One-Way Outbound</option>
                <option value="bidirectional_allow" ${l.firewall_policy === 'bidirectional_allow' ? 'selected' : ''}>Allow Both Ways</option>
                <option value="restricted" ${l.firewall_policy === 'restricted' ? 'selected' : ''}>Restricted Ports</option>
                <option value="block" ${l.firewall_policy === 'block' ? 'selected' : ''}>Block All</option>
            </select>
        </td>
        <td>
            <input type="text" class="inline-input link-ports-input" placeholder="e.g. 80, 443, 22" value="${l.allowed_ports ? l.allowed_ports.join(', ') : ''}">
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-link-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-link-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;

export const renderNetRowTemplate = (n) => html`
    <tr id="net-row-${n.id}">
        <td><strong>${n.name}</strong></td>
        <td><code>${n.subnet}</code></td>
        <td><code>${n.gateway_ip || 'None'}</code></td>
        <td><span class="badge badge-outline">${n.network_type}</span></td>
        <td><code>${n.interface || 'auto'}</code></td>
        <td>
            <button class="btn btn-secondary btn-sm edit-net-btn" data-id="${n.id}">Edit</button>
            <button class="btn btn-danger btn-sm delete-net-btn" data-id="${n.id}">Delete</button>
        </td>
    </tr>
`;

export const renderInlineNetFormTemplate = (n = {}) => html`
    <tr class="inline-add-row" ${n.id ? `id="edit-net-row-${n.id}"` : ''}>
        <td><input type="text" class="inline-input net-name-input" placeholder="e.g. RoostOS Lab" value="${n.name || ''}"></td>
        <td><input type="text" class="inline-input net-subnet-input" placeholder="e.g. 192.168.1.0/24" value="${n.subnet || ''}"></td>
        <td><input type="text" class="inline-input net-gw-input" placeholder="e.g. 192.168.1.1" value="${n.gateway_ip || ''}"></td>
        <td>
            <select class="inline-input net-type-select">
                <option value="lan" ${n.network_type === 'lan' ? 'selected' : ''}>Local LAN</option>
                <option value="wan_upstream" ${n.network_type === 'wan_upstream' ? 'selected' : ''}>Upstream WAN</option>
                <option value="vpn_overlay" ${n.network_type === 'vpn_overlay' ? 'selected' : ''}>WireGuard Overlay</option>
                <option value="cloud_vpc" ${n.network_type === 'cloud_vpc' ? 'selected' : ''}>Cloud VPS VPC</option>
                <option value="dmz" ${n.network_type === 'dmz' ? 'selected' : ''}>DMZ</option>
            </select>
        </td>
        <td><input type="text" class="inline-input net-if-input" placeholder="br-lan / eth0" value="${n.interface || ''}"></td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-net-btn">Save</button>
                <button class="btn btn-secondary btn-sm cancel-net-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;
