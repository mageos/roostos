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
        edge: "Edge Gateway & Ingress",
        firewall: "Firewall Rules & NAT",
        parental: "Parental Controls & Bedtimes",
        dns: "DNS Resolver Settings",
        people: "Family Profiles & Operator Logins",
        locations: "Buildings & Rooms",
        devices: "Registered Devices",
        catalog: "Application Catalog & Extensions",
        plugins: "Hosted Sidecar Plugins",
        cluster: "Cluster Fleet Management",
        system: "System Administration"
    };

    const categories = {
        status: "Overview",
        networks: "Connectivity",
        dhcp: "Connectivity",
        vpn: "Connectivity",
        edge: "Connectivity",
        firewall: "Security",
        parental: "Security",
        dns: "Security",
        people: "Management",
        locations: "Management",
        devices: "Management",
        catalog: "Management",
        plugins: "Management",
        cluster: "Management",
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

        // Feed devices to roost-device-list
        const devElem = document.getElementById("device-list-elem");
        if (devElem && devElem.setDevices) {
            devElem.setDevices(allDevices);
        } else if (window.deviceComponent && window.deviceComponent.render) {
            window.deviceComponent.render();
        }

        // Feed leases to roost-dhcp-management
        const dhcpElem = document.getElementById("dhcp-mgmt-elem");
        if (dhcpElem && dhcpElem.setData) {
            dhcpElem.setData(devData.reservations || [], activeLeases, devData.dhcp_config || {});
        } else if (window.dhcpComponent && window.dhcpComponent.render) {
            window.dhcpComponent.render();
        }

        // Fetch Networks (bridges, interfaces, VLANs, Wi-Fi APs)
        await window.networkService.fetchConfig();
        const netElem = document.getElementById("net-view-elem");
        if (netElem && netElem.render) {
            netElem.render();
        } else if (window.networkComponent && window.networkComponent.render) {
            window.networkComponent.render();
        }

        // Fetch Schedules & Firewall Rules
        const schedData = await window.securityService.fetchSchedules();
        const parentalTbody = document.getElementById("parental-tbody");
        if (parentalTbody && schedData.schedules) {
            if (schedData.schedules.length === 0) {
                parentalTbody.innerHTML = '<tr><td colspan="6" class="empty-state">No active schedules configured.</td></tr>';
            } else {
                parentalTbody.innerHTML = schedData.schedules.map(s => `
                    <tr>
                        <td><strong>${s.name || s.id}</strong></td>
                        <td><code>${s.target || "-"}</code></td>
                        <td>${(s.days || []).join(", ") || "All"}</td>
                        <td>${s.start_time || "00:00"} - ${s.end_time || "23:59"}</td>
                        <td>${s.daily_limit_minutes ? s.daily_limit_minutes + " mins" : "Unlimited"}</td>
                        <td><span class="badge ${s.enabled !== false ? 'badge-success' : 'badge-secondary'}">${s.enabled !== false ? 'Active' : 'Disabled'}</span></td>
                    </tr>
                `).join("");
            }
        }
        if (window.parentalComponent && window.parentalComponent.render) {
            window.parentalComponent.render(schedData.schedules || []);
        }

        // Fetch Firewall Rules
        try {
            const fwRules = await window.securityService.fetchFirewallRules();
            const fwElem = document.getElementById("firewall-rules-elem");
            if (fwElem && fwElem.setRules) {
                fwElem.setRules(fwRules, schedData.port_forwards || []);
            } else if (window.firewallComponent && window.firewallComponent.renderWithRules) {
                window.firewallComponent.renderWithRules(schedData.port_forwards || [], fwRules);
            }
        } catch (_) {}

        // Fetch DNS Configurations
        const dnsData = await window.securityService.fetchDnsConfig();
        const dnsUpstreams = document.getElementById("dns-upstreams");
        if (dnsUpstreams && dnsData.upstream_servers) {
            dnsUpstreams.textContent = dnsData.upstream_servers.join(", ");
        }
        if (window.dnsComponent && window.dnsComponent.render) {
            window.dnsComponent.render(dnsData);
        }

        // Fetch operator logins & household members
        const users = await window.securityService.fetchUsers();
        const userElem = document.getElementById("user-list-elem");
        if (userElem && userElem.setUsers) {
            userElem.setUsers(users || []);
        }
        try {
            const peopleList = await window.systemService.fetchPeople();
            const peopleElem = document.getElementById("people-list-elem");
            if (peopleElem && peopleElem.setPeople) {
                peopleElem.setPeople(peopleList || []);
            }
        } catch (_) {}
        if (window.peopleComponent && window.peopleComponent.renderUsersList) {
            window.peopleComponent.renderUsersList(users);
        }

        // Fetch Buildings & Rooms
        const buildings = await window.systemService.fetchBuildings();
        window.allBuildingsList = buildings;
        const rooms = await window.systemService.fetchRooms();
        const bldTbody = document.getElementById("buildings-tbody");
        if (bldTbody && buildings) {
            bldTbody.innerHTML = buildings.length === 0 
                ? '<tr><td colspan="3" class="empty-state">No buildings configured.</td></tr>'
                : buildings.map(b => `<tr><td><code>${b.id}</code></td><td><strong>${b.name}</strong></td><td>${b.description || "-"}</td></tr>`).join("");
        }
        const rmTbody = document.getElementById("rooms-tbody");
        if (rmTbody && rooms) {
            rmTbody.innerHTML = rooms.length === 0
                ? '<tr><td colspan="3" class="empty-state">No rooms configured.</td></tr>'
                : rooms.map(r => `<tr><td><code>${r.id}</code></td><td><strong>${r.name}</strong></td><td>${r.building || "-"}</td></tr>`).join("");
        }
        if (window.locationsComponent && window.locationsComponent.render) {
            window.locationsComponent.render(buildings, rooms);
        }

        // Fetch sidecar Plugins
        const plugins = await window.systemService.fetchPlugins();
        const plgTbody = document.getElementById("plugins-tbody");
        if (plgTbody && plugins) {
            plgTbody.innerHTML = plugins.length === 0
                ? '<tr><td colspan="4" class="empty-state">No sidecar plugins currently active.</td></tr>'
                : plugins.map(p => `<tr><td><strong>${p.name || p.id}</strong></td><td>${p.version || "-"}</td><td><span class="badge ${p.enabled ? 'badge-success' : 'badge-secondary'}">${p.enabled ? 'Running' : 'Stopped'}</span></td><td>${p.endpoint || "-"}</td></tr>`).join("");
        }
        if (window.pluginsComponent && window.pluginsComponent.render) {
            window.pluginsComponent.render(plugins);
        }

        // Refresh canvas graphs
        if (window.statusComponent && window.statusComponent.drawCharts) {
            window.statusComponent.drawCharts();
        }

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
        if (window.statusComponent && window.statusComponent.mount) {
            window.statusComponent.mount(viewContainer);
        }

        // Networks
        const networksPane = document.createElement("div");
        networksPane.id = "networks-view";
        networksPane.className = "view-pane";
        networksPane.innerHTML = "<roost-network-view id=\"net-view-elem\"></roost-network-view>";
        viewContainer.appendChild(networksPane);

        // DHCP
        const dhcpPane = document.createElement("div");
        dhcpPane.id = "dhcp-view";
        dhcpPane.className = "view-pane";
        dhcpPane.innerHTML = "<roost-dhcp-management id=\"dhcp-mgmt-elem\"></roost-dhcp-management>";
        viewContainer.appendChild(dhcpPane);

        // VPN
        const vpnPane = document.createElement("div");
        vpnPane.id = "vpn-view";
        vpnPane.className = "view-pane";
        vpnPane.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3>VPN Connections & Tunnels</h3>
                    <span class="badge badge-info">WireGuard / OpenVPN</span>
                </div>
                <p class="text-secondary" style="font-size:13px; margin: 12px 0;">
                    Secure encrypted site-to-site and client tunnels configured on this node.
                </p>
                <div id="vpn-list-container" class="table-responsive">
                    <table class="data-table">
                        <thead>
                            <tr><th>Tunnel</th><th>Type</th><th>Endpoint</th><th>Local IP</th><th>Status</th></tr>
                        </thead>
                        <tbody id="vpn-tbody">
                            <tr><td colspan="5" class="empty-state">No active VPN tunnels configured.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        viewContainer.appendChild(vpnPane);

        // Edge Gateway
        const edgePane = document.createElement("div");
        edgePane.id = "edge-view";
        edgePane.className = "view-pane";
        edgePane.innerHTML = "<roost-edge-gateway id=\"edge-gateway-elem\"></roost-edge-gateway>";
        viewContainer.appendChild(edgePane);

        // Devices
        const devicesPane = document.createElement("div");
        devicesPane.id = "devices-view";
        devicesPane.className = "view-pane";
        devicesPane.innerHTML = "<roost-device-list id=\"device-list-elem\"></roost-device-list>";
        viewContainer.appendChild(devicesPane);

        // Firewall
        const firewallPane = document.createElement("div");
        firewallPane.id = "firewall-view";
        firewallPane.className = "view-pane";
        firewallPane.innerHTML = "<roost-firewall-rules id=\"firewall-rules-elem\"></roost-firewall-rules>";
        viewContainer.appendChild(firewallPane);

        // Parental Controls
        const parentalPane = document.createElement("div");
        parentalPane.id = "parental-view";
        parentalPane.className = "view-pane";
        parentalPane.innerHTML = `
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header table-action-bar">
                    <div>
                        <h3>Parental Controls & Bedtime Schedules</h3>
                        <p class="text-secondary" style="font-size:12px;">Enforce time-based access windows, curfews, and daily allowances</p>
                    </div>
                </div>
                <div class="table-responsive">
                    <table class="data-table">
                        <thead>
                            <tr><th>Schedule Name</th><th>Target</th><th>Days Active</th><th>Time Window</th><th>Daily Allowance</th><th>Status</th></tr>
                        </thead>
                        <tbody id="parental-tbody">
                            <tr><td colspan="6" class="empty-state">No active bedtime or access schedules configured.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        viewContainer.appendChild(parentalPane);

        // DNS
        const dnsPane = document.createElement("div");
        dnsPane.id = "dns-view";
        dnsPane.className = "view-pane";
        dnsPane.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3>DNS Resolver Settings</h3>
                    <span class="badge badge-info">Local DNS</span>
                </div>
                <p class="text-secondary" style="font-size:13px; margin: 12px 0;">
                    Local caching DNS resolver and upstream DNS-over-HTTPS / TLS forwarding configuration.
                </p>
                <div class="grid-3-col" style="gap: 16px; margin-top: 12px;">
                    <div class="stat-item"><span class="stat-label">Local DNS Listen IP:</span><span class="stat-value" id="dns-local-ip">127.0.0.1</span></div>
                    <div class="stat-item"><span class="stat-label">Upstream Servers:</span><span class="stat-value" id="dns-upstreams">1.1.1.1, 8.8.8.8</span></div>
                    <div class="stat-item"><span class="stat-label">DNS Filter Status:</span><span class="stat-value badge badge-success" id="dns-blocking-status">Active</span></div>
                </div>
            </div>
        `;
        viewContainer.appendChild(dnsPane);

        // People & Users
        const peoplePane = document.createElement("div");
        peoplePane.id = "people-view";
        peoplePane.className = "view-pane";
        peoplePane.innerHTML = `
            <roost-people-list id="people-list-elem"></roost-people-list>
            <div style="margin-top: 24px;">
                <roost-user-list id="user-list-elem"></roost-user-list>
            </div>
        `;
        viewContainer.appendChild(peoplePane);

        // Locations
        const locationsPane = document.createElement("div");
        locationsPane.id = "locations-view";
        locationsPane.className = "view-pane";
        locationsPane.innerHTML = `
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header table-action-bar">
                    <div>
                        <h3>Buildings & Campus Areas</h3>
                        <p class="text-secondary" style="font-size:12px;">Physical structures grouped by access policies</p>
                    </div>
                </div>
                <div class="table-responsive">
                    <table class="data-table">
                        <thead><tr><th>ID</th><th>Building Name</th><th>Description</th></tr></thead>
                        <tbody id="buildings-tbody">
                            <tr><td colspan="3" class="empty-state">No buildings configured.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <div class="card-header table-action-bar">
                    <div>
                        <h3>Rooms & Zones</h3>
                        <p class="text-secondary" style="font-size:12px;">Rooms and network ports mapped to physical locations</p>
                    </div>
                </div>
                <div class="table-responsive">
                    <table class="data-table">
                        <thead><tr><th>ID</th><th>Room Name</th><th>Building</th></tr></thead>
                        <tbody id="rooms-tbody">
                            <tr><td colspan="3" class="empty-state">No rooms configured.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        viewContainer.appendChild(locationsPane);

        // System
        if (window.systemComponent && window.systemComponent.mount) {
            window.systemComponent.mount(viewContainer);
        }

        // App Catalog
        const catalogPane = document.createElement("div");
        catalogPane.id = "catalog-view";
        catalogPane.className = "view-pane";
        catalogPane.innerHTML = "<roost-app-catalog></roost-app-catalog>";
        viewContainer.appendChild(catalogPane);

        // Cluster Fleet Management
        const clusterPane = document.createElement("div");
        clusterPane.id = "cluster-view";
        clusterPane.className = "view-pane";
        clusterPane.innerHTML = "<roost-cluster-management id=\"cluster-mgmt-elem\"></roost-cluster-management>";
        viewContainer.appendChild(clusterPane);

        // Plugins
        const pluginsPane = document.createElement("div");
        pluginsPane.id = "plugins-view";
        pluginsPane.className = "view-pane";
        pluginsPane.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3>Installed Sidecar Plugins</h3>
                    <span class="badge badge-info">Extensibility</span>
                </div>
                <p class="text-secondary" style="font-size:13px; margin: 12px 0;">
                    Manage installed dockerized plugins and ecosystem microservices.
                </p>
                <div class="table-responsive">
                    <table class="data-table">
                        <thead><tr><th>Plugin</th><th>Version</th><th>Status</th><th>Endpoint</th></tr></thead>
                        <tbody id="plugins-tbody">
                            <tr><td colspan="4" class="empty-state">No sidecar plugins currently active.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        viewContainer.appendChild(pluginsPane);
    }

    // 2. Setup theme settings
    window.loadSavedTheme();
    window.initSidebarCollapse();

    // 3. Populate default viewport dashboard info and switch to status view
    window.switchView('status');
    if (window.setupWizard) {
        window.setupWizard.checkAndPromptSetup();
    }
    
    // Start periodic status refresh (every 10 seconds fallback)
    setInterval(() => {
        const active = document.activeElement;
        const isFocused = active && (active.tagName === 'INPUT' || active.tagName === 'SELECT' || active.tagName === 'TEXTAREA');
        const hasOpenForms = document.querySelector('table tbody input, table tbody select, .editing-row, .inline-form, #inline-edit-row');
        if (isFocused || hasOpenForms) {
            return;
        }
        window.loadDashboard();
        if (window.updateAlertsBadge) window.updateAlertsBadge();
    }, 10000);

    // Initialize real-time Server-Sent Events (SSE) telemetry
    window.initEventStream();
    if (window.updateAlertsBadge) window.updateAlertsBadge();
}

window.initEventStream = function() {
    if (typeof EventSource === "undefined") return;
    try {
        const evtSource = new EventSource("/api/v1/events/stream");
        evtSource.addEventListener("device_connected", () => window.loadDashboard());
        evtSource.addEventListener("unknown_device", () => window.loadDashboard());
        evtSource.addEventListener("upnp_request", () => window.loadDashboard());
        evtSource.addEventListener("devices_updated", () => window.loadDashboard());
        evtSource.addEventListener("schedules_updated", () => window.loadDashboard());
        evtSource.addEventListener("bypass_expired", () => window.loadDashboard());
        evtSource.addEventListener("alert", () => {
            if (window.updateAlertsBadge) window.updateAlertsBadge();
        });
    } catch (e) {
        console.warn("Real-time SSE event stream could not be initialized:", e);
    }
};

// Entrypoint
document.addEventListener("DOMContentLoaded", () => {
    if (window.authService.handleAuthentication()) {
        init();
    }
});
