/**
 * Network Topology Diagram - Interactive SVG Architectural Map
 * Generates an architectural diagram of subnets, gateways, and inter-network tunnels.
 */

export const TIER_CONFIG = {
    wan_upstream: { tier: 0, color: "#0ea5e9", icon: "🌐", label: "Upstream WAN" },
    lan: { tier: 1, color: "#10b981", icon: "🖥️", label: "Local LAN" },
    guest: { tier: 1, color: "#f59e0b", icon: "👥", label: "Guest Wi-Fi" },
    dmz: { tier: 1, color: "#f43f5e", icon: "🛡️", label: "DMZ Network" },
    vpn_overlay: { tier: 2, color: "#8b5cf6", icon: "🔒", label: "WireGuard Hub" },
    cloud_vpc: { tier: 3, color: "#06b6d4", icon: "☁️", label: "Cloud VPC" }
};

export const calculateTopologyLayout = (networks = [], svgWidth = 940, svgHeight = 360) => {
    const nodeW = 180;
    const nodeH = 74;
    const paddingX = 40;
    const paddingY = 40;

    // Group networks by column tier
    const tierGroups = new Map();
    networks.forEach(net => {
        const tier = TIER_CONFIG[net.network_type]?.tier ?? 1;
        if (!tierGroups.has(tier)) tierGroups.set(tier, []);
        tierGroups.get(tier).push(net);
    });

    const activeTiers = Array.from(tierGroups.keys()).sort((a, b) => a - b);
    const tierCount = activeTiers.length || 1;
    const colSpacing = tierCount > 1 
        ? (svgWidth - (paddingX * 2) - nodeW) / (tierCount - 1)
        : 0;

    const nodes = new Map();
    activeTiers.forEach((tier, colIdx) => {
        const netsInTier = tierGroups.get(tier);
        const colX = tierCount === 1 
            ? (svgWidth - nodeW) / 2 
            : paddingX + (colIdx * colSpacing);
        const rowSpacing = (svgHeight - (paddingY * 2)) / (netsInTier.length + 1);

        netsInTier.forEach((net, rowIdx) => {
            const y = paddingY + ((rowIdx + 1) * rowSpacing) - (nodeH / 2);
            nodes.set(net.id, {
                ...net,
                x: colX,
                y,
                width: nodeW,
                height: nodeH,
                cx: colX + (nodeW / 2),
                cy: y + (nodeH / 2),
                tierConfig: TIER_CONFIG[net.network_type] || { color: "#94a3b8", icon: "🖧", label: net.network_type }
            });
        });
    });

    return { nodes, width: svgWidth, height: svgHeight };
};

const getBezierPath = (src, tgt) => {
    let x1, y1, x2, y2, cx1, cy1, cx2, cy2;
    if (src.x + src.width < tgt.x) {
        x1 = src.x + src.width; y1 = src.cy;
        x2 = tgt.x; y2 = tgt.cy;
        const dx = (x2 - x1) * 0.5;
        cx1 = x1 + dx; cy1 = y1;
        cx2 = x2 - dx; cy2 = y2;
    } else if (src.x > tgt.x + tgt.width) {
        x1 = src.x; y1 = src.cy;
        x2 = tgt.x + tgt.width; y2 = tgt.cy;
        const dx = (x1 - x2) * 0.5;
        cx1 = x1 - dx; cy1 = y1;
        cx2 = x2 + dx; cy2 = y2;
    } else {
        x1 = src.cx; y1 = src.y + (src.y < tgt.y ? src.height : 0);
        x2 = tgt.cx; y2 = tgt.y + (src.y < tgt.y ? 0 : tgt.height);
        const dy = (y2 - y1) * 0.5;
        cx1 = x1 + 20; cy1 = y1 + dy;
        cx2 = x2 + 20; cy2 = y2 - dy;
    }
    const mx = 0.125 * x1 + 0.375 * cx1 + 0.375 * cx2 + 0.125 * x2;
    const my = 0.125 * y1 + 0.375 * cy1 + 0.375 * cy2 + 0.125 * y2;
    return { d: `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`, mx, my };
};

export const renderTopologyDiagramSvg = (networks = [], links = [], selectedNodeId = null, selectedLinkId = null) => {
    if (networks.length === 0) {
        return `<div class="empty-state" style="padding: 48px; text-align: center;">No networks discovered to build diagram.</div>`;
    }

    const { nodes, width, height } = calculateTopologyLayout(networks, 940, 360);

    const edgesSvg = links.map(link => {
        const src = nodes.get(link.source_network_id);
        const tgt = nodes.get(link.target_network_id);
        if (!src || !tgt) return "";

        const isWg = link.connection_type === "wireguard_tunnel";
        const isWan = link.connection_type === "physical_wan";
        const strokeColor = isWg ? "#a78bfa" : (isWan ? "#38bdf8" : "#34d399");
        const marker = isWg ? "url(#arrow-wg)" : (isWan ? "url(#arrow-wan)" : "url(#arrow-routed)");
        const isSelected = selectedLinkId === link.id;
        const isDimmed = selectedNodeId && (link.source_network_id !== selectedNodeId && link.target_network_id !== selectedNodeId);

        const { d, mx, my } = getBezierPath(src, tgt);
        const badgeLabel = isWg ? "🔒 WireGuard" : (isWan ? "🌐 NAT Uplink" : "🔀 Routed");

        return `
        <g class="diagram-edge ${isSelected ? 'selected' : ''} ${isDimmed ? 'dimmed' : ''}" data-link-id="${link.id}">
            <path d="${d}" fill="none" stroke="${strokeColor}" stroke-width="${isSelected ? 3.5 : 2}" 
                  class="${isWg ? 'wireguard-link' : ''}" marker-end="${marker}" opacity="${isDimmed ? 0.2 : 0.85}" />
            <g class="diagram-link-badge" data-link-id="${link.id}" style="cursor: pointer;" opacity="${isDimmed ? 0.3 : 1}">
                <rect x="${mx - 46}" y="${my - 11}" width="92" height="22" rx="11" 
                      fill="#0f172a" stroke="${strokeColor}" stroke-width="1.2" opacity="0.95" />
                <text x="${mx}" y="${my + 4}" text-anchor="middle" font-size="10" font-weight="600" 
                      fill="#e2e8f0" font-family="system-ui, sans-serif">${badgeLabel}</text>
            </g>
        </g>
        `;
    }).join("");

    const nodesSvg = Array.from(nodes.values()).map(node => {
        const isSelected = selectedNodeId === node.id;
        const isDimmed = selectedNodeId && selectedNodeId !== node.id;
        const color = node.tierConfig.color;

        return `
        <g class="diagram-node ${isSelected ? 'selected' : ''} ${isDimmed ? 'dimmed' : ''}" 
           data-node-id="${node.id}" style="cursor: pointer;" opacity="${isDimmed ? 0.4 : 1}">
            <rect x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}" rx="10" 
                  fill="#1e293b" stroke="${isSelected ? '#38bdf8' : color}" stroke-width="${isSelected ? 2.5 : 1.2}" 
                  filter="url(#diagram-glow)" />
            <rect x="${node.x}" y="${node.y}" width="${node.width}" height="4" rx="2" fill="${color}" />
            <text x="${node.x + 12}" y="${node.y + 22}" font-size="12" font-weight="700" fill="#f8fafc" 
                  font-family="system-ui, sans-serif">${node.tierConfig.icon} ${node.name}</text>
            <text x="${node.x + 12}" y="${node.y + 44}" font-family="monospace" font-size="12" font-weight="600" 
                  fill="${color}">${node.subnet}</text>
            <text x="${node.x + 12}" y="${node.y + 62}" font-size="10" fill="#94a3b8" 
                  font-family="system-ui, sans-serif">gw: ${node.gateway_ip || 'None'} • ${node.interface || 'auto'}</text>
            <circle cx="${node.x + node.width - 14}" cy="${node.y + 18}" r="4" fill="#10b981" />
        </g>
        `;
    }).join("");

    return `
    <div class="topology-diagram-container" style="width: 100%; overflow-x: auto; background: rgba(15, 23, 42, 0.4); border-radius: 8px; border: 1px solid var(--card-border); padding: 8px 0;">
        <svg viewBox="0 0 ${width} ${height}" style="width: 100%; min-width: 720px; height: auto; display: block;" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <filter id="diagram-glow" x="-10%" y="-10%" width="120%" height="120%">
                    <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.35"/>
                </filter>
                <marker id="arrow-wg" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#a78bfa" />
                </marker>
                <marker id="arrow-wan" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
                </marker>
                <marker id="arrow-routed" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#34d399" />
                </marker>
                <style>
                    .wireguard-link { stroke-dasharray: 6 4; animation: topoWgFlow 1.5s linear infinite; }
                    @keyframes topoWgFlow { from { stroke-dashoffset: 20; } to { stroke-dashoffset: 0; } }
                    .diagram-node:hover rect { stroke-width: 2.2px; filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.5)); }
                    .diagram-link-badge:hover rect { fill: #1e293b; stroke-width: 2px; }
                </style>
            </defs>
            <g class="diagram-edges">${edgesSvg}</g>
            <g class="diagram-nodes">${nodesSvg}</g>
        </svg>
    </div>
    `;
};
