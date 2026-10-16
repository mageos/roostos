// Prototype Explorer Shell Coordinator & Navigation Router
import { store } from './state.js';

import { renderHouseholdHome } from './concept1/c1-household-home.js';
import { renderHouseholdFamily } from './concept1/c1-household-family.js';
import { renderHouseholdDevices } from './concept1/c1-household-devices.js';
import { renderHouseholdWifi } from './concept1/c1-household-wifi.js';
import { renderHouseholdSafety } from './concept1/c1-household-safety.js';
import { renderAdminCockpit } from './concept1/c1-admin-cockpit.js';
import { renderAdminNetwork } from './concept1/c1-admin-network.js';
import { renderAdminDhcp } from './concept1/c1-admin-dhcp.js';
import { renderAdminFirewall } from './concept1/c1-admin-firewall.js';
import { renderAdminDns } from './concept1/c1-admin-dns.js';
import { renderAdminSystem } from './concept1/c1-admin-system.js';

import { renderTopologyView } from './concept2/c2-topology.js';
import { renderDirectoryView } from './concept2/c2-directory.js';
import { renderProtectionView } from './concept2/c2-protection.js';
import { renderConnectivityView } from './concept2/c2-connectivity.js';
import { renderFleetView } from './concept2/c2-fleet.js';

let activeC1Tab = 'home';
let activeC2Tab = 'topology';

export function initExplorerShell() {
    renderToolbar();
    renderAppShell();
    store.subscribe(() => renderActiveView());
}

function renderToolbar() {
    const tb = document.getElementById('explorer-toolbar');
    if (!tb) return;

    tb.innerHTML = `
        <div class="explorer-brand">
            <span style="font-size: 20px;">🦅</span>
            <div>
                <strong>RoostOS UI Redesign Explorer</strong>
                <div style="font-size: 11px; color: #94a3b8;">Interactive Prototype & Architecture Evaluation</div>
            </div>
        </div>

        <div class="explorer-controls">
            <div class="segmented-group">
                <button class="seg-btn ${store.currentConcept === 'concept1' ? 'active' : ''}" id="btn-concept1">🏠 Concept 1: Dual-Persona</button>
                <button class="seg-btn ${store.currentConcept === 'concept2' ? 'active' : ''}" id="btn-concept2">🌐 Concept 2: Unified Topology</button>
            </div>

            ${store.currentConcept === 'concept1' ? `
                <div class="segmented-group">
                    <button class="seg-btn ${store.concept1Persona === 'household' ? 'active persona-household' : ''}" id="btn-p-household">🏡 Household Hub</button>
                    <button class="seg-btn ${store.concept1Persona === 'admin' ? 'active persona-admin' : ''}" id="btn-p-admin">⚡ SysAdmin Console</button>
                </div>
            ` : `
                <div class="segmented-group">
                    <button class="seg-btn ${store.concept2Density === 'standard' ? 'active' : ''}" id="btn-d-standard">🌿 Standard View</button>
                    <button class="seg-btn ${store.concept2Density === 'expert' ? 'active persona-admin' : ''}" id="btn-d-expert">🛠️ Expert Inspector</button>
                </div>
            `}

            <div class="segmented-group">
                <button class="seg-btn ${store.deviceMode === 'responsive' ? 'active' : ''}" id="btn-vm-desktop">💻 Desktop</button>
                <button class="seg-btn ${store.deviceMode === 'tablet' ? 'active' : ''}" id="btn-vm-tablet">📟 Tablet</button>
                <button class="seg-btn ${store.deviceMode === 'mobile' ? 'active' : ''}" id="btn-vm-mobile">📱 Mobile</button>
            </div>

            <button class="seg-btn" id="btn-theme-toggle" style="background: #1e293b; border: 1px solid #334155; padding: 5px 10px;">🌓 Theme</button>
        </div>
    `;

    tb.querySelector('#btn-concept1')?.addEventListener('click', () => { store.currentConcept = 'concept1'; renderToolbar(); renderAppShell(); });
    tb.querySelector('#btn-concept2')?.addEventListener('click', () => { store.currentConcept = 'concept2'; renderToolbar(); renderAppShell(); });
    tb.querySelector('#btn-p-household')?.addEventListener('click', () => { store.concept1Persona = 'household'; activeC1Tab = 'home'; renderToolbar(); renderAppShell(); });
    tb.querySelector('#btn-p-admin')?.addEventListener('click', () => { store.concept1Persona = 'admin'; activeC1Tab = 'cockpit'; renderToolbar(); renderAppShell(); });
    tb.querySelector('#btn-d-standard')?.addEventListener('click', () => { store.concept2Density = 'standard'; renderToolbar(); renderActiveView(); });
    tb.querySelector('#btn-d-expert')?.addEventListener('click', () => { store.concept2Density = 'expert'; renderToolbar(); renderActiveView(); });
    tb.querySelector('#btn-vm-desktop')?.addEventListener('click', () => updateDeviceMode('responsive'));
    tb.querySelector('#btn-vm-tablet')?.addEventListener('click', () => updateDeviceMode('tablet'));
    tb.querySelector('#btn-vm-mobile')?.addEventListener('click', () => updateDeviceMode('mobile'));
    tb.querySelector('#btn-theme-toggle')?.addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme') || 'light';
        document.documentElement.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
    });
}

function updateDeviceMode(mode) {
    store.deviceMode = mode;
    const stage = document.getElementById('viewport-stage');
    if (stage) stage.className = `viewport-stage mode-${mode}`;
    renderToolbar();
}

const c1HouseholdNav = [
    { id: 'home', label: 'Home', icon: '🏡' },
    { id: 'topology', label: 'Network Map', icon: '🗺️' },
    { id: 'family', label: 'Family', icon: '👨‍👩‍👧' },
    { id: 'devices', label: 'Devices', icon: '📱' },
    { id: 'wifi', label: 'Wi-Fi', icon: '📶' },
    { id: 'safety', label: 'Safety', icon: '🛡️' }
];

const c1AdminNav = [
    { id: 'cockpit', label: 'Cockpit', icon: '⚡' },
    { id: 'topology', label: 'Topology & Zones', icon: '🗺️' },
    { id: 'network', label: 'Network', icon: '🔌' },
    { id: 'dhcp', label: 'DHCP', icon: '📡' },
    { id: 'firewall', label: 'Firewall', icon: '🛡️' },
    { id: 'dns', label: 'DNS', icon: '🔍' },
    { id: 'system', label: 'Fleet', icon: '🖥️' }
];

const c2Nav = [
    { id: 'topology', label: 'Topology', icon: '🌐' },
    { id: 'directory', label: 'Directory', icon: '👥' },
    { id: 'protection', label: 'Protection', icon: '🛡️' },
    { id: 'connectivity', label: 'Connect', icon: '🔌' },
    { id: 'fleet', label: 'Fleet', icon: '🖥️' }
];

function renderAppShell() {
    const frame = document.getElementById('roost-app-frame');
    if (!frame) return;

    const isC1 = store.currentConcept === 'concept1';
    const isHousehold = isC1 && store.concept1Persona === 'household';
    const navItems = isC1 ? (isHousehold ? c1HouseholdNav : c1AdminNav) : c2Nav;
    const activeTab = isC1 ? activeC1Tab : activeC2Tab;
    const attrKey = isC1 ? 'data-c1' : 'data-c2';

    const desktopNavHtml = `
        <div class="c1-nav-tabs ${!isC1 ? 'c2-nav-tabs' : ''}">
            ${navItems.map(n => `<button class="c1-nav-link ${activeTab === n.id ? 'active' : ''}" ${attrKey}="${n.id}">${n.icon} ${n.label}</button>`).join('')}
        </div>
    `;

    const mobileNavHtml = `
        <div class="mobile-nav-items">
            ${navItems.map(n => `<button class="mobile-nav-btn ${activeTab === n.id ? 'active' : ''}" ${attrKey}="${n.id}"><span class="mobile-nav-icon">${n.icon}</span><span>${n.label}</span></button>`).join('')}
        </div>
    `;

    const workspaceSelectorHtml = isC1 ? `
        <div class="workspace-selector-wrap">
            <button class="workspace-badge-btn" id="in-app-workspace-btn" title="Click to switch workspace">
                <span>${isHousehold ? '🏡 Household Hub' : '⚡ SysAdmin Console'}</span>
                <span style="font-size: 8px;">▼</span>
            </button>
            <div class="workspace-dropdown-menu" id="in-app-workspace-menu" style="display: none;">
                <div class="workspace-menu-item ${isHousehold ? 'active' : ''}" data-persona-choice="household">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-main);">🏡 Household Hub</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Family screentime, devices, Wi-Fi & safety</div>
                </div>
                <div class="workspace-menu-item ${!isHousehold ? 'active' : ''}" data-persona-choice="admin">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-main);">⚡ SysAdmin Console</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Telemetry, Kea DHCP, nftables, DNS & fleet</div>
                </div>
            </div>
        </div>
    ` : `
        <div class="workspace-selector-wrap">
            <button class="workspace-badge-btn" id="in-app-density-btn" title="Click to toggle density">
                <span>${store.concept2Density === 'expert' ? '🛠️ Expert Inspector' : '🌿 Standard View'}</span>
                <span style="font-size: 8px;">▼</span>
            </button>
            <div class="workspace-dropdown-menu" id="in-app-density-menu" style="display: none;">
                <div class="workspace-menu-item ${store.concept2Density === 'standard' ? 'active' : ''}" data-density-choice="standard">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-main);">🌿 Standard View</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Friendly cards, status and human names</div>
                </div>
                <div class="workspace-menu-item ${store.concept2Density === 'expert' ? 'active' : ''}" data-density-choice="expert">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-main);">🛠️ Expert Inspector</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Packet counters, MTU & raw configs</div>
                </div>
            </div>
        </div>
    `;

    frame.innerHTML = `
        <div class="phone-notch"></div>
        <header class="roost-header">
            <div style="display: flex; align-items: center; gap: 12px;">
                <a href="#" class="brand-badge"><span class="brand-dot"></span><span>RoostOS</span></a>
                ${workspaceSelectorHtml}
            </div>
            ${desktopNavHtml}
            <div style="font-size: 12px; color: var(--text-muted); font-weight: 500;">
                ${isC1 ? (isHousehold ? 'Family: Dad' : 'Root SysAdmin') : (store.concept2Density === 'expert' ? 'Expert Mode' : 'Standard')}
            </div>
        </header>
        <main class="roost-main" id="view-mount-point"></main>
        <nav class="mobile-bottom-nav">${mobileNavHtml}</nav>
    `;

    // Dropdown toggle & selection handlers
    const wsBtn = frame.querySelector('#in-app-workspace-btn');
    const wsMenu = frame.querySelector('#in-app-workspace-menu');
    if (wsBtn && wsMenu) {
        wsBtn.onclick = (e) => { e.stopPropagation(); wsMenu.style.display = wsMenu.style.display === 'none' ? 'flex' : 'none'; };
        wsMenu.querySelectorAll('[data-persona-choice]').forEach(item => {
            item.onclick = () => {
                store.concept1Persona = item.dataset.personaChoice;
                activeC1Tab = store.concept1Persona === 'household' ? 'home' : 'cockpit';
                renderToolbar();
                renderAppShell();
            };
        });
    }

    const densBtn = frame.querySelector('#in-app-density-btn');
    const densMenu = frame.querySelector('#in-app-density-menu');
    if (densBtn && densMenu) {
        densBtn.onclick = (e) => { e.stopPropagation(); densMenu.style.display = densMenu.style.display === 'none' ? 'flex' : 'none'; };
        densMenu.querySelectorAll('[data-density-choice]').forEach(item => {
            item.onclick = () => {
                store.concept2Density = item.dataset.densityChoice;
                renderToolbar();
                renderAppShell();
            };
        });
    }

    document.onclick = () => {
        if (wsMenu) wsMenu.style.display = 'none';
        if (densMenu) densMenu.style.display = 'none';
    };

    frame.querySelectorAll('[data-c1]').forEach(btn => {
        btn.onclick = () => { activeC1Tab = btn.dataset.c1; renderAppShell(); };
    });
    frame.querySelectorAll('[data-c2]').forEach(btn => {
        btn.onclick = () => { activeC2Tab = btn.dataset.c2; renderAppShell(); };
    });

    window.c1SwitchTab = (tab) => { activeC1Tab = tab; renderAppShell(); };
    renderActiveView();
}

function renderActiveView() {
    const mount = document.getElementById('view-mount-point');
    if (!mount) return;

    if (store.currentConcept === 'concept1') {
        if (store.concept1Persona === 'household') {
            const views = { home: renderHouseholdHome, topology: renderTopologyView, family: renderHouseholdFamily, devices: renderHouseholdDevices, wifi: renderHouseholdWifi, safety: renderHouseholdSafety };
            (views[activeC1Tab] || renderHouseholdHome)(mount);
        } else {
            const views = { cockpit: renderAdminCockpit, topology: renderTopologyView, network: renderAdminNetwork, dhcp: renderAdminDhcp, firewall: renderAdminFirewall, dns: renderAdminDns, system: renderAdminSystem };
            (views[activeC1Tab] || renderAdminCockpit)(mount);
        }
    } else {
        const views = { topology: renderTopologyView, directory: renderDirectoryView, protection: renderProtectionView, connectivity: renderConnectivityView, fleet: renderFleetView };
        (views[activeC2Tab] || renderTopologyView)(mount);
    }
}
