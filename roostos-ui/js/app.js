// RoostOS Management Console - Modular Shell & Router Coordinator
import { store } from './state.js';
import { checkAuth, logout } from './auth.js';

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

import { renderZoneDiagramSvg } from './components/zone-diagram-svg.js';

let activeHouseholdTab = 'home';
let activeAdminTab = 'cockpit';

const householdNavItems = [
    { id: 'home', label: 'Home', icon: '🏡' },
    { id: 'topology', label: 'Network Map', icon: '🗺️' },
    { id: 'family', label: 'Family', icon: '👨‍👩‍👧' },
    { id: 'devices', label: 'Devices', icon: '📱' },
    { id: 'wifi', label: 'Wi-Fi', icon: '📶' },
    { id: 'safety', label: 'Safety', icon: '🛡️' }
];

const adminNavItems = [
    { id: 'cockpit', label: 'Cockpit', icon: '⚡' },
    { id: 'topology', label: 'Topology & Zones', icon: '🗺️' },
    { id: 'network', label: 'Network', icon: '🔌' },
    { id: 'dhcp', label: 'DHCP', icon: '📡' },
    { id: 'firewall', label: 'Firewall', icon: '🛡️' },
    { id: 'dns', label: 'DNS', icon: '🔍' },
    { id: 'system', label: 'Fleet', icon: '🖥️' }
];

export async function initApp() {
    await checkAuth();
    renderAppShell();
    store.subscribe(() => renderActiveView());

    // Initial background sync with FastAPI backend
    store.syncWithBackend();

    // Auto-refresh pulse every 10s
    setInterval(() => {
        store.syncWithBackend();
    }, 10000);

    // Initialize real-time SSE stream if available
    initServerEventStream();
}

function renderAppShell() {
    const frame = document.getElementById('roost-app-frame');
    if (!frame) return;

    const isHousehold = store.concept1Persona === 'household';
    const navItems = isHousehold ? householdNavItems : adminNavItems;
    const activeTab = isHousehold ? activeHouseholdTab : activeAdminTab;

    const desktopNavHtml = `
        <div class="c1-nav-tabs">
            ${navItems.map(n => `
                <button class="c1-nav-link ${activeTab === n.id ? 'active' : ''}" data-tab="${n.id}">
                    ${n.icon} ${n.label}
                </button>
            `).join('')}
        </div>
    `;

    const mobileNavHtml = `
        <div class="mobile-nav-items">
            ${navItems.map(n => `
                <button class="mobile-nav-btn ${activeTab === n.id ? 'active' : ''}" data-tab="${n.id}">
                    <span class="mobile-nav-icon">${n.icon}</span>
                    <span>${n.label}</span>
                </button>
            `).join('')}
        </div>
    `;

    const workspaceSelectorHtml = `
        <div class="workspace-selector-wrap">
            <button class="workspace-badge-btn" id="workspace-toggle-btn" title="Switch between Household Hub and SysAdmin Console">
                <span>${isHousehold ? '🏡 Household Hub' : '⚡ SysAdmin Console'}</span>
                <span style="font-size: 8px;">▼</span>
            </button>
            <div class="workspace-dropdown-menu" id="workspace-dropdown-menu" style="display: none;">
                <div class="workspace-menu-item ${isHousehold ? 'active' : ''}" data-persona="household">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-main);">🏡 Household Hub</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Family screentime, bedtimes, Wi-Fi & safety</div>
                </div>
                <div class="workspace-menu-item ${!isHousehold ? 'active' : ''}" data-persona="admin">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text-main);">⚡ SysAdmin Console</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Dense telemetry, Kea DHCP, nftables, DNS & fleet</div>
                </div>
            </div>
        </div>
    `;

    frame.innerHTML = `
        <header class="roost-header">
            <div style="display: flex; align-items: center; gap: 12px;">
                <a href="#" class="brand-badge" id="brand-home-link">
                    <span class="brand-dot"></span>
                    <span>RoostOS</span>
                </a>
                ${workspaceSelectorHtml}
            </div>

            ${desktopNavHtml}

            <div style="display: flex; align-items: center; gap: 10px;">
                <button id="theme-toggle-btn" class="btn btn-secondary btn-sm" title="Toggle Light / Dark theme" style="padding: 4px 8px; font-size: 12px;">
                    🌓
                </button>
                <button id="logout-btn" class="btn btn-secondary btn-sm" title="Log out" style="padding: 4px 8px; font-size: 12px;">
                    🚪
                </button>
                <div class="system-status-pill" style="font-size: 12px; color: var(--text-muted); font-weight: 500;">
                    ${isHousehold ? '👨‍👩‍👧 Family Mode' : '⚡ SysAdmin'}
                </div>
            </div>
        </header>

        <main class="roost-main" id="view-mount-point"></main>

        <nav class="mobile-bottom-nav">
            ${mobileNavHtml}
        </nav>
    `;

    // Dropdown Persona Switcher listeners
    const wsBtn = frame.querySelector('#workspace-toggle-btn');
    const wsMenu = frame.querySelector('#workspace-dropdown-menu');
    if (wsBtn && wsMenu) {
        wsBtn.onclick = (e) => {
            e.stopPropagation();
            wsMenu.style.display = wsMenu.style.display === 'none' ? 'flex' : 'none';
        };
        wsMenu.querySelectorAll('[data-persona]').forEach(item => {
            item.onclick = () => {
                store.concept1Persona = item.dataset.persona;
                wsMenu.style.display = 'none';
                renderAppShell();
            };
        });
    }

    document.addEventListener('click', () => {
        if (wsMenu) wsMenu.style.display = 'none';
    });

    // Theme toggle handler
    const themeBtn = frame.querySelector('#theme-toggle-btn');
    if (themeBtn) {
        themeBtn.onclick = () => {
            const cur = document.documentElement.getAttribute('data-theme') || 'light';
            const next = cur === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('roostos_theme', next);
        };
    }

    // Logout handler
    const logoutBtn = frame.querySelector('#logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = () => logout();
    }

    // Brand link resets to home/cockpit
    const brandLink = frame.querySelector('#brand-home-link');
    if (brandLink) {
        brandLink.onclick = (e) => {
            e.preventDefault();
            if (store.concept1Persona === 'household') {
                activeHouseholdTab = 'home';
            } else {
                activeAdminTab = 'cockpit';
            }
            renderAppShell();
        };
    }

    // Tab navigation event listeners (desktop + mobile)
    frame.querySelectorAll('[data-tab]').forEach(btn => {
        btn.onclick = () => {
            const targetTab = btn.dataset.tab;
            if (store.concept1Persona === 'household') {
                activeHouseholdTab = targetTab;
            } else {
                activeAdminTab = targetTab;
            }
            renderAppShell();
        };
    });

    // Internal navigation bridge
    window.c1SwitchTab = (tab) => {
        if (store.concept1Persona === 'household') {
            activeHouseholdTab = tab;
        } else {
            activeAdminTab = tab;
        }
        renderAppShell();
    };

    renderActiveView();
}

function renderActiveView() {
    const mount = document.getElementById('view-mount-point');
    if (!mount) return;

    if (store.concept1Persona === 'household') {
        const householdViews = {
            home: renderHouseholdHome,
            topology: renderZoneDiagramSvg,
            family: renderHouseholdFamily,
            devices: renderHouseholdDevices,
            wifi: renderHouseholdWifi,
            safety: renderHouseholdSafety,
        };
        const renderer = householdViews[activeHouseholdTab] || renderHouseholdHome;
        renderer(mount);
    } else {
        const adminViews = {
            cockpit: renderAdminCockpit,
            topology: renderZoneDiagramSvg,
            network: renderAdminNetwork,
            dhcp: renderAdminDhcp,
            firewall: renderAdminFirewall,
            dns: renderAdminDns,
            system: renderAdminSystem,
        };
        const renderer = adminViews[activeAdminTab] || renderAdminCockpit;
        renderer(mount);
    }
}

function initServerEventStream() {
    if (typeof EventSource === 'undefined') return;
    try {
        const evt = new EventSource('/api/v1/events/stream');
        evt.onmessage = () => store.syncWithBackend();
        evt.addEventListener('device_connected', () => store.syncWithBackend());
        evt.addEventListener('devices_updated', () => store.syncWithBackend());
        evt.addEventListener('schedules_updated', () => store.syncWithBackend());
        evt.addEventListener('alert', () => store.syncWithBackend());
    } catch (e) {
        console.warn('Real-time SSE event stream could not be initialized:', e);
    }
}

// Auto-run bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('roostos_theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
    initApp();
});
