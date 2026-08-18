// Standalone RoostOS Web Console Controller & REST API Integration

// Global State (exposed on window for modular components and test bindings)
window.allDevices = [];
window.activeLeases = [];
window.selectedTags = new Set();
window.allOwners = [];
window.allLocations = [];
window.networkSettings = {};
window.wifiSettings = {};
window.vpnSettings = [];
window.metricsHistory = [];
window.MAX_HISTORY_POINTS = 40;
window.activeVpnPlugins = [];
window.localDnsRecords = [
    { domain: "roost-router.lan", ip: "192.168.1.1", type: "A" },
    { domain: "nas.lan", ip: "192.168.1.15", type: "A" }
];
window.allBuildingsList = [];

// Dynamic Extension registry
window.RoostOS = {
    extensions: [],
    vpnHandlers: {},
    registerExtension(ext) {
        if (this.extensions.some(e => e.id === ext.id)) return;
        this.extensions.push(ext);
        
        const nav = document.querySelector(".sidebar-nav");
        const btn = document.createElement("button");
        btn.className = "nav-item";
        btn.textContent = ext.title;
        btn.onclick = () => {
            document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            document.querySelectorAll(".view-pane").forEach(p => p.classList.remove("active"));
            
            let pane = document.getElementById(`ext-view-${ext.id}`);
            if (!pane) {
                pane = document.createElement("div");
                pane.id = `ext-view-${ext.id}`;
                pane.className = "view-pane";
                document.querySelector(".view-container").appendChild(pane);
            }
            pane.classList.add("active");
            document.getElementById("view-title").textContent = ext.title;
            ext.render(pane);
        };
        
        const pluginsBtn = Array.from(nav.querySelectorAll("button")).find(b => b.textContent === "Plugins");
        if (pluginsBtn) {
            nav.insertBefore(btn, pluginsBtn);
        } else {
            nav.appendChild(btn);
        }
    },
    registerVpnFormHandler(type, handler) {
        this.vpnHandlers[type] = handler;
    },
    getVpnFormHandler(type) {
        return this.vpnHandlers[type];
    },
    getVpnTypes() {
        return Object.keys(this.vpnHandlers);
    }
};

// 1. Text Escaping and Common Helpers
window.escapeHtml = function(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#039;");
};

window.escapeJs = function(str) {
    if (!str) return "";
    return str.replace(/\\/g, "\\\\")
              .replace(/'/g, "\\'")
              .replace(/"/g, '\\"')
              .replace(/\n/g, "\\n")
              .replace(/\r/g, "\\r");
};

window.formatSpeed = function(bytesPerSec) {
    if (bytesPerSec === undefined || bytesPerSec === null || isNaN(bytesPerSec)) return "0 B/s";
    if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`;
    if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
    return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`;
};

// 2. Tab Routing & Views Switcher
window.switchView = function(viewId) {
    document.querySelectorAll(".nav-item").forEach(btn => {
        btn.classList.remove("active");
        if (btn.id === `nav-${viewId}`) {
            btn.classList.add("active");
        }
    });

    const activeBtn = document.getElementById(`nav-${viewId}`);
    if (activeBtn) {
        const parentSection = activeBtn.closest(".nav-section");
        if (parentSection && parentSection.classList.contains("collapsed")) {
            parentSection.classList.remove("collapsed");
            const sectionName = parentSection.id.replace("section-", "");
            localStorage.setItem(`roostos_section_${sectionName}_collapsed`, "false");
        }
    }

    document.querySelectorAll(".view-pane").forEach(pane => {
        pane.classList.remove("active");
    });
    const activePane = document.getElementById(`${viewId}-view`);
    if (activePane) activePane.classList.add("active");

    const titleEl = document.getElementById("view-title");
    const categoryEl = document.getElementById("breadcrumb-category");
    const titles = {
        status: "Status Dashboard",
        networks: "Networks & Interfaces",
        dhcp: "DHCP Server Status",
        vpn: "VPN Connection Tunnels",
        firewall: "Firewall Rules & NAT",
        parental: "Parental Controls & Bedtimes",
        dns: "DNS Resolver Settings",
        people: "Family Profiles & Operator Logins",
        locations: "Buildings & Rooms",
        devices: "Registered Devices",
        plugins: "Hosted Sidecar Plugins",
        system: "System Administration"
    };

    const categories = {
        status: "Overview",
        networks: "Connectivity",
        dhcp: "Connectivity",
        vpn: "Connectivity",
        firewall: "Security",
        parental: "Security",
        dns: "Security",
        people: "Management",
        locations: "Management",
        devices: "Management",
        plugins: "Management",
        system: "Management"
    };

    if (titleEl) titleEl.textContent = titles[viewId] || (viewId.charAt(0).toUpperCase() + viewId.slice(1) + " Dashboard");
    if (categoryEl) categoryEl.textContent = categories[viewId] || "Overview";

    if (["status", "dhcp", "vpn", "firewall", "parental", "dns", "system", "people"].includes(viewId)) {
        window.switchSubTab(viewId, "basic");
    }

    window.loadDashboard();
};

window.switchSubTab = function(viewId, tabName) {
    const viewContainer = document.getElementById(`${viewId}-view`);
    if (!viewContainer) return;

    const tabHeader = viewContainer.querySelector(".view-tabs-header");
    if (tabHeader) {
        tabHeader.querySelectorAll(".tab-btn").forEach(btn => {
            btn.classList.remove("active");
            if (btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(`'${tabName}'`)) {
                btn.classList.add("active");
            }
        });
    }

    const basicPane = viewContainer.querySelector(".basic-pane");
    const advPane = viewContainer.querySelector(".advanced-pane");
    const qosPane = viewContainer.querySelector(".qos-pane");

    if (basicPane && advPane) {
        basicPane.classList.remove("active");
        advPane.classList.remove("active");
        if (qosPane) qosPane.classList.remove("active");

        if (tabName === "basic") {
            basicPane.classList.add("active");
        } else if (tabName === "advanced") {
            advPane.classList.add("active");
        } else if (tabName === "qos" && qosPane) {
            qosPane.classList.add("active");
        }
    }
};

window.toggleSidebarSection = function(sectionName) {
    const sectionEl = document.getElementById(`section-${sectionName}`);
    if (!sectionEl) return;
    const isCollapsed = sectionEl.classList.toggle("collapsed");
    localStorage.setItem(`roostos_section_${sectionName}_collapsed`, isCollapsed ? "true" : "false");
};

window.initSidebarCollapse = function() {
    ["connectivity", "security", "management"].forEach(section => {
        const sectionEl = document.getElementById(`section-${section}`);
        if (!sectionEl) return;
        const saved = localStorage.getItem(`roostos_section_${section}_collapsed`);
        if (saved === "true") {
            sectionEl.classList.add("collapsed");
        } else {
            sectionEl.classList.remove("collapsed");
        }
    });
};

// 3. Theme Engine
window.loadSavedTheme = function() {
    const savedTheme = localStorage.getItem("roostos_theme") || "auto";
    const selectEl = document.getElementById("theme-select");
    if (selectEl) selectEl.value = savedTheme;
    window.changeTheme(savedTheme);
};

window.changeTheme = function(theme) {
    localStorage.setItem("roostos_theme", theme);
    const doc = document.documentElement;
    if (theme === "dark") {
        doc.classList.add("dark-theme");
        doc.classList.remove("light-theme");
    } else if (theme === "light") {
        doc.classList.add("light-theme");
        doc.classList.remove("dark-theme");
    } else {
        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        if (isDark) {
            doc.classList.add("dark-theme");
            doc.classList.remove("light-theme");
        } else {
            doc.classList.add("light-theme");
            doc.classList.remove("dark-theme");
        }
    }
};

// 4. API Operations & Global Data Coordinating Pipeline
window.loadDashboard = async function() {
    try {
        // Fetch User profile details first
        await loadUserProfile();

        // Fetch System details
        const sysData = await window.systemService.fetchSystemSettings();
        
        // Push statistics to history queue
        const cpuVal = parseFloat(sysData.cpu_load || 0.0);
        const ramVal = parseFloat(sysData.ram_usage || 0.0);
        const rxVal = parseFloat(sysData.rx_rate || 0.0);
        const txVal = parseFloat(sysData.tx_rate || 0.0);

        metricsHistory.push({
            cpu: isNaN(cpuVal) ? 0.0 : cpuVal,
            ram: isNaN(ramVal) ? 0.0 : ramVal,
            rx: isNaN(rxVal) ? 0.0 : rxVal,
            tx: isNaN(txVal) ? 0.0 : txVal
        });

        if (metricsHistory.length > MAX_HISTORY_POINTS) {
            metricsHistory.shift();
        }

        // Render dashboard system updates
        window.statusComponent.render(sysData);
        window.systemComponent.render(sysData);

        const versionEl = document.getElementById("footer-version");
        if (versionEl && sysData.version) {
            versionEl.textContent = sysData.version;
        }

        // Fetch Devices & DHCP status
        const devData = await window.deviceService.fetchDevices();
        allDevices = devData.devices || [];
        activeLeases = devData.active_leases || [];
        allOwners = Array.from(new Set(allDevices.map(d => d.owner).filter(Boolean)));
        allLocations = Array.from(new Set(allDevices.map(d => d.location).filter(Boolean)));

        // Compile metrics
        const connectedEl = document.getElementById("metric-connected");
        if (connectedEl) connectedEl.textContent = (devData.active_arp || []).length;

        window.deviceComponent.render();
        window.dhcpComponent.render();

        // Fetch Networks (bridges, interfaces, VLANs, Wi-Fi APs)
        await window.networkService.fetchConfig();
        window.networkComponent.render();

        // Fetch Schedules & Firewall Rules
        const schedData = await window.securityService.fetchSchedules();
        window.parentalComponent.render(schedData.schedules || []);

        // Fetch Firewall Input Rules and render alongside port forwards
        try {
            const fwRules = await window.securityService.fetchFirewallRules();
            window.firewallComponent.renderWithRules(schedData.port_forwards || [], fwRules);
        } catch (e) {
            window.firewallComponent.render(schedData.port_forwards || []);
        }

        // Fetch DNS Configurations
        const dnsData = await window.securityService.fetchDnsConfig();
        window.dnsComponent.render(dnsData);

        // Fetch operator logins
        const users = await window.securityService.fetchUsers();
        window.peopleComponent.renderUsersList(users);

        // Fetch Buildings & Rooms
        const buildings = await window.systemService.fetchBuildings();
        window.allBuildingsList = buildings;
        const rooms = await window.systemService.fetchRooms();
        window.locationsComponent.render(buildings, rooms);

        // Fetch sidecar Plugins
        const plugins = await window.systemService.fetchPlugins();
        window.pluginsComponent.render(plugins);

        // Refresh canvas graphs
        window.statusComponent.drawCharts();

    } catch (e) {
        console.error("Dashboard orchestration refresh error: ", e);
    }
};

async function loadUserProfile() {
    try {
        const res = await window.authService.apiFetch("/api/auth/me");
        if (res.ok) {
            const user = await res.json();
            const nameEl = document.getElementById("user-display-name");
            const roleEl = document.getElementById("user-display-role");
            if (nameEl) nameEl.textContent = user.username || "-";
            if (roleEl) {
                roleEl.textContent = user.role || "-";
                if (user.role === "admin") {
                    roleEl.style.background = "rgba(16, 185, 129, 0.1)";
                    roleEl.style.borderColor = "rgba(16, 185, 129, 0.3)";
                    roleEl.style.color = "#10b981";
                } else if (user.role === "parent") {
                    roleEl.style.background = "rgba(99, 102, 241, 0.1)";
                    roleEl.style.borderColor = "rgba(99, 102, 241, 0.3)";
                    roleEl.style.color = "#6366f1";
                } else {
                    roleEl.style.background = "rgba(255, 255, 255, 0.05)";
                    roleEl.style.borderColor = "rgba(255, 255, 255, 0.1)";
                    roleEl.style.color = "var(--text-secondary)";
                }
            }
        }
    } catch (e) {
        console.error("Error loading user profile:", e);
    }
}

// Initialization and Event listeners binding
function init() {
    // 1. Mount Component templates into empty index.html view-container
    const viewContainer = document.querySelector(".view-container");
    if (viewContainer) {
        window.statusComponent.mount(viewContainer);
        window.networkComponent.mount(viewContainer);
        window.dhcpComponent.mount(viewContainer);
        window.vpnComponent.mount(viewContainer);
        window.deviceComponent.mount(viewContainer);
        window.firewallComponent.mount(viewContainer);
        window.parentalComponent.mount(viewContainer);
        window.dnsComponent.mount(viewContainer);
        window.peopleComponent.mount(viewContainer);
        window.locationsComponent.mount(viewContainer);
        window.systemComponent.mount(viewContainer);
        window.pluginsComponent.mount(viewContainer);
    }

    // 2. Setup theme settings
    window.loadSavedTheme();
    window.initSidebarCollapse();

    // 3. Populate default viewport dashboard info and switch to status view
    window.switchView('status');
    
    // Start periodic status refresh (every 5 seconds)
    setInterval(() => {
        const active = document.activeElement;
        const isFocused = active && (active.tagName === 'INPUT' || active.tagName === 'SELECT' || active.tagName === 'TEXTAREA');
        const hasOpenForms = document.querySelector('table tbody input, table tbody select, .editing-row, .inline-form, #inline-edit-row');
        if (isFocused || hasOpenForms) {
            return;
        }
        window.loadDashboard();
    }, 5000);
}

// Entrypoint
document.addEventListener("DOMContentLoaded", () => {
    if (window.authService.handleAuthentication()) {
        init();
    }
});
