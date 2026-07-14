// Standalone RoostOS Web Console Controller & REST API Integration

// Global State
let allDevices = [];
let activeLeases = [];
let selectedTags = new Set();
let allOwners = [];
let allLocations = [];
let networkSettings = {};
let wifiSettings = {};
let vpnSettings = [];
let metricsHistory = [];
const MAX_HISTORY_POINTS = 40;
let activeVpnPlugins = [];
let localDnsRecords = [
    { domain: "roost-router.lan", ip: "192.168.1.1", type: "A" },
    { domain: "nas.lan", ip: "192.168.1.15", type: "A" }
];

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
    }
};

// 1. Auth & Session Management (OAuth2 Auth Code Flow)
function handleAuthentication() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const token = localStorage.getItem("roostos_token");

    if (code) {
        // Exchange authorization code for access token
        fetch("/oauth/token", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: new URLSearchParams({
                grant_type: "authorization_code",
                code: code,
                redirect_uri: window.location.origin + "/",
                client_id: "roostos-ui"
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Token exchange failed");
            return res.json();
        })
        .then(data => {
            if (data.access_token) {
                localStorage.setItem("roostos_token", data.access_token);
                // Clean URL query parameters
                window.history.replaceState({}, document.title, window.location.pathname);
                init();
            }
        })
        .catch(err => {
            console.error(err);
            alert("Authentication failed. Redirecting to login...");
            redirectToLogin();
        });
        return false;
    }

    if (!token) {
        redirectToLogin();
        return false;
    }

    return true;
}

function redirectToLogin() {
    const redirectUri = encodeURIComponent(window.location.origin + "/");
    window.location.href = `/oauth/authorize?client_id=roostos-ui&redirect_uri=${redirectUri}`;
}

function logout() {
    localStorage.removeItem("roostos_token");
    redirectToLogin();
}

// Helper to make authenticated API requests
async function apiFetch(url, options = {}) {
    const token = localStorage.getItem("roostos_token");
    options.headers = options.headers || {};
    if (token) {
        options.headers["Authorization"] = `Bearer ${token}`;
    }
    
    const response = await fetch(url, options);
    if (response.status === 401) {
        localStorage.removeItem("roostos_token");
        redirectToLogin();
        throw new Error("Unauthorized session. Redirecting to login...");
    }
    return response;
}


// 2. Tab Routing & Views Switcher
function switchView(viewId) {
    // Update Nav buttons state
    document.querySelectorAll(".nav-item").forEach(btn => {
        btn.classList.remove("active");
        if (btn.id === `nav-${viewId}`) {
            btn.classList.add("active");
        }
    });

    // Ensure parent section is expanded
    const activeBtn = document.getElementById(`nav-${viewId}`);
    if (activeBtn) {
        const parentSection = activeBtn.closest(".nav-section");
        if (parentSection && parentSection.classList.contains("collapsed")) {
            parentSection.classList.remove("collapsed");
            const sectionName = parentSection.id.replace("section-", "");
            localStorage.setItem(`roostos_section_${sectionName}_collapsed`, "false");
        }
    }

    // Update View Panes state
    document.querySelectorAll(".view-pane").forEach(pane => {
        pane.classList.remove("active");
    });
    const activePane = document.getElementById(`${viewId}-view`);
    if (activePane) activePane.classList.add("active");

    // Update Header Title
    const titleEl = document.getElementById("view-title");
    const titles = {
        status: "Status Dashboard",
        networks: "Networks & WiFi APs",
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
    titleEl.textContent = titles[viewId] || (viewId.charAt(0).toUpperCase() + viewId.slice(1) + " Dashboard");

    // Default to basic sub-tab if this view has sub-tabs
    if (["networks", "dhcp", "vpn", "firewall", "parental", "dns", "system", "people"].includes(viewId)) {
        switchSubTab(viewId, "basic");
    }

    // Refresh view data
    loadDashboard();
}

window.switchSubTab = function(viewId, tabName) {
    const viewContainer = document.getElementById(`${viewId}-view`);
    if (!viewContainer) return;

    // Update active tab button style
    const tabHeader = viewContainer.querySelector(".view-tabs-header");
    if (tabHeader) {
        tabHeader.querySelectorAll(".tab-btn").forEach(btn => {
            btn.classList.remove("active");
            if (btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(`'${tabName}'`)) {
                btn.classList.add("active");
            }
        });
    }

    // Toggle panes
    const basicPane = viewContainer.querySelector(".basic-pane");
    const advPane = viewContainer.querySelector(".advanced-pane");
    if (basicPane && advPane) {
        if (tabName === "basic") {
            basicPane.classList.add("active");
            advPane.classList.remove("active");
        } else {
            basicPane.classList.remove("active");
            advPane.classList.add("active");
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
function loadSavedTheme() {
    const savedTheme = localStorage.getItem("roostos_theme") || "auto";
    const selectEl = document.getElementById("theme-select");
    if (selectEl) selectEl.value = savedTheme;
    changeTheme(savedTheme);
}

function changeTheme(theme) {
    localStorage.setItem("roostos_theme", theme);
    const doc = document.documentElement;
    if (theme === "auto") {
        doc.removeAttribute("data-theme");
    } else {
        doc.setAttribute("data-theme", theme);
    }
}


// 4. API Operations & Data Loading
async function loadDashboard() {
    try {
        // Fetch System details
        const sysRes = await apiFetch("/api/system");
        if (sysRes.ok) {
            const sysData = await sysRes.json();
            document.getElementById("stat-hostname").textContent = sysData.hostname || "-";
            document.getElementById("stat-domain").textContent = sysData.domain || "-";
            document.getElementById("sys-hostname").value = sysData.hostname || "";
            document.getElementById("sys-domain").value = sysData.domain || "";
            const regInput = document.getElementById("sys-registry");
            if (regInput) regInput.value = sysData.docker_registry || "";
            
            // Populate real-time system stats
            const cpuEl = document.getElementById("stat-cpu");
            if (cpuEl) cpuEl.textContent = sysData.cpu_load || "0.0%";
            
            const ramEl = document.getElementById("stat-ram");
            if (ramEl) ramEl.textContent = sysData.ram_usage || "0.0%";
            
            const uptimeEl = document.getElementById("metric-uptime");
            if (uptimeEl) uptimeEl.textContent = sysData.uptime || "-";
            
            const wanEl = document.getElementById("stat-wan-ip");
            if (wanEl) wanEl.textContent = sysData.wan_ip || "-";
            
            const lanEl = document.getElementById("stat-lan-ip");
            if (lanEl) lanEl.textContent = sysData.lan_ip || "-";

            const versionEl = document.getElementById("footer-version");
            if (versionEl) versionEl.textContent = `v${sysData.version || "0.1.0"}`;

            // Parse rates & percentages
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

            const legendRates = document.getElementById("traffic-legend-rates");
            if (legendRates) {
                legendRates.textContent = `Rx: ${formatSpeed(rxVal)} | Tx: ${formatSpeed(txVal)}`;
            }

            if (typeof drawCharts === "function") {
                drawCharts();
            }

            // Render Warnings Alert Banner
            const warningsContainer = document.getElementById("system-warnings-container");
            if (warningsContainer) {
                const warnings = sysData.warnings || [];
                if (warnings.length > 0) {
                    warningsContainer.style.display = "block";
                    warningsContainer.innerHTML = warnings.map(w => `
                        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; padding: 12px 16px; border-radius: 6px; margin-bottom: 10px; font-size: 13px; display: flex; align-items: center; gap: 8px;">
                            <svg style="width: 16px; height: 16px; fill: currentColor; flex-shrink: 0;" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                            <span><strong>System Alert:</strong> ${escapeHtml(w)}</span>
                        </div>
                    `).join("");
                } else {
                    warningsContainer.style.display = "none";
                    warningsContainer.innerHTML = "";
                }
            }
        }

        // Fetch Devices and DHCP Leases
        const devRes = await apiFetch("/api/devices");
        if (devRes.ok) {
            const devData = await devRes.json();
            allDevices = devData.devices || [];
            activeLeases = devData.active_leases || [];
            
            // Compile unique list of owners and locations for form options
            allOwners = Array.from(new Set(allDevices.map(d => d.owner).filter(Boolean)));
            allLocations = Array.from(new Set(allDevices.map(d => d.location).filter(Boolean)));

            // Compile metrics
            document.getElementById("metric-connected").textContent = activeLeases.length;
            
            // Build tag filters and location selector options on first load
            populateFilters(allDevices);
            renderDevicesList();
        }

        // Fetch People
        const peopleRes = await apiFetch("/api/people");
        let allBuildings = [];
        if (peopleRes.ok) {
            const peopleData = await peopleRes.json();
            allOwners = peopleData.people || [];
            renderPeopleList(allOwners);
        }

        // Fetch Buildings
        const bldRes = await apiFetch("/api/buildings");
        if (bldRes.ok) {
            const bldData = await bldRes.json();
            allBuildings = bldData.buildings || [];
            renderBuildingsList(allBuildings);
            populateBuildingDropdowns(allBuildings);
        }

        // Fetch Rooms
        const roomsRes = await apiFetch("/api/rooms");
        if (roomsRes.ok) {
            const roomsData = await roomsRes.json();
            allLocations = roomsData.rooms || [];
            renderRoomsList(allLocations);
        }

        // Fetch Schedules & NAT
        const schedRes = await apiFetch("/api/schedules");
        if (schedRes.ok) {
            const schedData = await schedRes.json();
            renderSchedules(schedData.schedules || []);
            renderNATRules(schedData.port_forwards || []);
            
            // Calculate blocked devices count
            const blockedCount = allDevices.filter(d => d.quarantined).length; // or calculate based on blocked schedules
            document.getElementById("metric-blocked").textContent = blockedCount;
        }

        // Fetch Network settings (interfaces, wifi, vpns)
        const netRes = await apiFetch("/api/network");
        if (netRes.ok) {
            const netData = await netRes.json();
            networkSettings = netData.network || {};
            wifiSettings = netData.wifi || {};
            vpnSettings = netData.vpns || [];

            renderNetworks();
            if (typeof renderInterfaces === 'function') renderInterfaces();
            renderWifiSettings(wifiSettings);
            renderVPNsList(vpnSettings);
        }

        // Fetch Plugins list
        const plugRes = await apiFetch("/api/plugins");
        if (plugRes.ok) {
            const plugData = await plugRes.json();
            renderPluginsList(plugData.plugins || []);
            
            // Dynamically populate VPN type select options based on enabled VPN provider plugins
            const vpnPlugins = (plugData.plugins || []).filter(p => 
                p.enabled && 
                p.known_services && 
                (p.known_services.includes("vpnServer") || p.known_services.includes("vpnClient"))
            );
            activeVpnPlugins = vpnPlugins;
            
            const vpnTypeSelect = document.getElementById("vpn-type");
            if (vpnTypeSelect) {
                const currentSelectedValue = vpnTypeSelect.value;
                if (vpnPlugins.length === 0) {
                    vpnTypeSelect.innerHTML = '<option value="">No enabled VPN plugins</option>';
                    vpnTypeSelect.disabled = true;
                } else {
                    vpnTypeSelect.disabled = false;
                    vpnTypeSelect.innerHTML = vpnPlugins.map(p => 
                        `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`
                    ).join("");
                    // Keep previous selection if still available
                    if (currentSelectedValue && vpnPlugins.some(p => p.id === currentSelectedValue)) {
                        vpnTypeSelect.value = currentSelectedValue;
                    }
                }
                updateVpnProtocolFields();
            }

            // Dynamically load ui.js files for enabled plugins that have ui_entrypoint
            for (const p of (plugData.plugins || [])) {
                if (p.enabled && p.ui_entrypoint) {
                    const scriptId = `script-plugin-${p.id}`;
                    if (!document.getElementById(scriptId)) {
                        const script = document.createElement("script");
                        script.id = scriptId;
                        script.src = `/plugins/${p.id}/ui.js`;
                        document.body.appendChild(script);
                    }
                }
            }
        }

        // Fetch Operator Users
        const usersRes = await apiFetch("/api/users");
        if (usersRes.ok) {
            const usersData = await usersRes.json();
            renderUsersList(usersData.users || []);
        }

        // Fetch DNS Config
        const dnsRes = await apiFetch("/api/dns/config");
        if (dnsRes.ok) {
            const dnsData = await dnsRes.json();
            const fInput = document.getElementById("dns-forwarders");
            if (fInput) fInput.value = (dnsData.forwarders || []).join(", ");
            const aCheckbox = document.getElementById("dns-adblock-enabled");
            if (aCheckbox) aCheckbox.checked = dnsData.ad_blocking_enabled || false;
        }

        // Render new reorganized views
        renderDHCPView();
        renderLocalDnsRecords();
    } catch (err) {
        console.error("Dashboard reload failed:", err);
    }
}


// 5. Dynamic Filters Populate
function populateFilters(devices) {
    // 1. Compile Unique Tags list
    const tags = new Set();
    devices.forEach(d => (d.tags || []).forEach(t => tags.add(t)));
    
    const tagContainer = document.getElementById("tag-filters");
    const currentSelected = new Set(selectedTags);
    
    tagContainer.innerHTML = Array.from(tags).map(tag => {
        const isSelected = currentSelected.has(tag);
        return `<span class="tag-badge ${isSelected ? 'selected' : ''}" onclick="toggleTagFilter('${escapeJs(tag)}')">${escapeHtml(tag)}</span>`;
    }).join("");

    // 2. Compile unique Location Options
    const locations = new Set();
    devices.forEach(d => { if (d.location) locations.add(d.location); });
    
    const locationSelect = document.getElementById("filter-location");
    const currentLoc = locationSelect.value;
    
    locationSelect.innerHTML = '<option value="all">All Locations (Rooms)</option>' + 
        Array.from(locations).map(loc => `<option value="${escapeHtml(loc)}">${escapeHtml(loc)}</option>`).join("");
    
    // Preserve selection
    if (Array.from(locations).includes(currentLoc)) {
        locationSelect.value = currentLoc;
    }
}

window.toggleTagFilter = function(tag) {
    if (selectedTags.has(tag)) {
        selectedTags.delete(tag);
    } else {
        selectedTags.add(tag);
    }
    loadDashboard();
};


// 6. Rendering Logic
function renderDevicesList() {
    const tableBody = document.getElementById("device-table-body");
    const onlineOnly = document.getElementById("filter-online-only").checked;
    const locationFilter = document.getElementById("filter-location").value;

    // Filter Devices
    const filtered = allDevices.filter(dev => {
        // Online filter
        const isOnline = activeLeases.some(l => l.mac.toLowerCase() === dev.mac.toLowerCase());
        if (onlineOnly && !isOnline) return false;
        
        // Location filter
        if (locationFilter !== "all" && dev.location !== locationFilter) return false;
        
        // Tag filters
        if (selectedTags.size > 0) {
            const devTags = dev.tags || [];
            if (!Array.from(selectedTags).some(t => devTags.includes(t))) return false;
        }
        
        return true;
    });

    if (filtered.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" class="empty-state">No matching registered devices found.</td></tr>';
        return;
    }

    tableBody.innerHTML = filtered.map(dev => {
        const isOnline = activeLeases.some(l => l.mac.toLowerCase() === dev.mac.toLowerCase());
        const tagsHtml = (dev.tags || []).map(t => `<span class="badge badge-offline" style="margin-right: 4px;">${escapeHtml(t)}</span>`).join("");
        
        return `
            <tr>
                <td><strong>${escapeHtml(dev.name)}</strong></td>
                <td><code>${escapeHtml(dev.mac.toUpperCase())}</code></td>
                <td>${escapeHtml(dev.static_ip || "DHCP")} <br><span style="font-size: 11px; color: var(--text-secondary);">Owner: ${escapeHtml(dev.owner || "None")}</span></td>
                <td>${escapeHtml(dev.location || "-")} <br> ${tagsHtml}</td>
                <td><span class="badge ${isOnline ? 'badge-online' : 'badge-offline'}">${isOnline ? 'ONLINE' : 'OFFLINE'}</span></td>
                <td>
                    <button class="btn btn-secondary" onclick="editDevice('${dev.mac}', '${escapeJs(dev.name)}', '${escapeJs(dev.owner || "")}', '${escapeJs(dev.location || "")}', '${escapeJs((dev.tags || []).join(","))}', ${dev.upnp_trusted || false}, '${escapeJs(dev.static_ip || "")}')">Edit</button>
                    <button class="btn btn-danger" onclick="deleteDevice('${dev.mac}')">Delete</button>
                </td>
            </tr>
        `;
    }).join("");
}

function renderSchedules(schedules) {
    const tableBody = document.getElementById("schedules-table-body");
    if (schedules.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No schedule rules configured.</td></tr>';
        return;
    }
    tableBody.innerHTML = schedules.map(s => `
        <tr>
            <td><strong>${escapeHtml(s.name)}</strong></td>
            <td>${s.targets.map(t => escapeHtml(t.person || t.location || t.mac || "")).join(", ")}</td>
            <td>${(s.days || []).join(", ")} <br> <span style="font-size: 11px; color: var(--text-secondary);">${s.start_time || ""} - ${s.end_time || ""}</span></td>
            <td>${s.daily_limit ? `${s.daily_limit} mins` : "None"}</td>
            <td><span class="badge badge-online">ACTIVE</span></td>
        </tr>
    `).join("");
}

function renderNATRules(rules) {
    const tableBody = document.getElementById("nat-table-body");
    if (rules.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No port forwarding rules defined.</td></tr>';
        return;
    }
    tableBody.innerHTML = rules.map(r => `
        <tr>
            <td><strong>${escapeHtml(r.name)}</strong></td>
            <td><code>${escapeHtml(r.protocol.toUpperCase())}</code></td>
            <td>${r.external_port}</td>
            <td>${escapeHtml(r.internal_ip)}</td>
            <td>${r.internal_port}</td>
        </tr>
    `).join("");
}

// 7. Form Handlers & Operations bindings
function setupEventListeners() {
    // System Config Form
    const sysForm = document.getElementById("system-config-form");
    sysForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const hostname = document.getElementById("sys-hostname").value.trim();
        const domain = document.getElementById("sys-domain").value.trim();
        const regInput = document.getElementById("sys-registry");
        const docker_registry = regInput ? regInput.value.trim() : null;
        
        try {
            const res = await apiFetch("/api/system", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ hostname, domain, timezone: "UTC", docker_registry })
            });
            if (res.ok) {
                alert("System configurations applied successfully!");
                loadDashboard();
            } else {
                alert("Failed to apply settings.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });

    // (Device Form handled inline now)

    // Bypass Form
    const bypassForm = document.getElementById("bypass-form");
    bypassForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const mac = document.getElementById("bypass-mac").value.trim();
        const duration_minutes = parseInt(document.getElementById("bypass-duration").value, 10);
        
        try {
            const res = await apiFetch("/api/schedules/bypass", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mac, duration_minutes })
            });
            if (res.ok) {
                alert(`Bypass extension granted to ${mac} for ${duration_minutes} minutes.`);
                bypassForm.reset();
                loadDashboard();
            } else {
                alert("Failed to grant bypass.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });

    // Backup download form
    const backupForm = document.getElementById("backup-form");
    backupForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const passphrase = document.getElementById("backup-passphrase").value;
        try {
            const res = await apiFetch("/api/backups", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ passphrase })
            });
            if (res.ok) {
                const data = await res.json();
                alert(`Backup created successfully at path: ${data.backup_path}`);
            } else {
                alert("Failed to create backup.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });

    // Reboot button
    const rebootBtn = document.getElementById("reboot-btn");
    rebootBtn.addEventListener("click", async () => {
        if (confirm("Are you sure you want to reboot the router host?")) {
            try {
                // Mock endpoint or actual D-Bus reboot triggers can be added
                alert("Reboot command sent to host system.");
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    });
}

// Helpers
window.filterDevices = function() {
    renderDevicesList();
};

window.closeInlineForm = function() {
    const existing = document.getElementById("inline-edit-row");
    if (existing) {
        existing.remove();
    }
};

window.saveInlineDevice = async function(e) {
    e.preventDefault();
    const mac = document.getElementById("dev-mac").value.trim();
    const name = document.getElementById("dev-name").value.trim();
    const owner = document.getElementById("dev-owner").value.trim();
    const location = document.getElementById("dev-location").value.trim();
    const static_ip = document.getElementById("dev-static-ip").value.trim();
    const tags = document.getElementById("dev-tags").value.split(",").map(t => t.trim()).filter(t => t.length > 0);
    const upnp_trusted = document.getElementById("dev-upnp").checked;
    
    try {
        const res = await apiFetch("/api/devices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mac, name, owner, location, tags, static_ip, upnp_trusted })
        });
        if (res.ok) {
            closeInlineForm();
            loadDashboard();
        } else {
            alert("Failed to save device. Verify MAC format and reference integrity.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.showAddDeviceForm = function(position) {
    closeInlineForm();

    const tableBody = document.getElementById("device-table-body");
    const formRow = document.createElement("tr");
    formRow.id = "inline-edit-row";
    formRow.innerHTML = `
        <td colspan="6" style="background: rgba(0, 0, 0, 0.02); padding: 24px;">
            <form id="inline-device-form" onsubmit="saveInlineDevice(event)">
                <h3 style="font-size: 14px; margin-bottom: 16px; font-weight: 600;">Add New Device Profile</h3>
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1;">
                        <label>MAC Address</label>
                        <input type="text" id="dev-mac" placeholder="aa:bb:cc:dd:ee:ff" required autofocus>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Device Name</label>
                        <input type="text" id="dev-name" placeholder="New Laptop" required>
                    </div>
                </div>
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1;">
                        <label>Owner (Person)</label>
                        <select id="dev-owner">
                            <option value="">None</option>
                            ${allOwners.map(o => {
                                const id = typeof o === "string" ? o : o.id;
                                const name = typeof o === "string" ? o : o.name;
                                return `<option value="${escapeHtml(id)}">${escapeHtml(name)}</option>`;
                            }).join("")}
                        </select>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Location (Room)</label>
                        <select id="dev-location">
                            <option value="">None</option>
                            ${allLocations.map(l => {
                                const id = typeof l === "string" ? l : l.id;
                                const name = typeof l === "string" ? l : l.name;
                                return `<option value="${escapeHtml(id)}">${escapeHtml(name)}</option>`;
                            }).join("")}
                        </select>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Static IP Assignment</label>
                        <input type="text" id="dev-static-ip" placeholder="Optional">
                    </div>
                </div>
                <div class="form-row-multi flex-align-center" style="align-items: center; justify-content: space-between; margin-bottom: 20px;">
                    <div class="form-group" style="flex: 1; margin-bottom: 0; margin-right: 20px;">
                        <label>Tags (comma-separated)</label>
                        <input type="text" id="dev-tags" placeholder="mobile, tags">
                    </div>
                    <label class="checkbox-container" style="margin-top: 20px;">
                        <input type="checkbox" id="dev-upnp">
                        <span>Trust UPnP</span>
                    </label>
                </div>
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button type="button" class="btn btn-secondary" onclick="closeInlineForm()">Cancel</button>
                    <button type="submit" class="btn btn-success">Add Device</button>
                </div>
            </form>
        </td>
    `;

    if (position === "top") {
        tableBody.insertBefore(formRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(formRow);
    }
    formRow.scrollIntoView({ behavior: "smooth" });
};

window.editDevice = function(mac, name, owner, location, tags, upnp, staticIp) {
    closeInlineForm();

    const tableBody = document.getElementById("device-table-body");
    const rows = Array.from(tableBody.querySelectorAll("tr"));
    const targetRow = rows.find(r => r.innerHTML.toLowerCase().includes(mac.toLowerCase()));
    if (!targetRow) return;

    const formRow = document.createElement("tr");
    formRow.id = "inline-edit-row";
    formRow.innerHTML = `
        <td colspan="6" style="background: rgba(0, 0, 0, 0.02); padding: 24px;">
            <form id="inline-device-form" onsubmit="saveInlineDevice(event)">
                <h3 style="font-size: 14px; margin-bottom: 16px; font-weight: 600;">Edit Device: ${escapeHtml(name)}</h3>
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1;">
                        <label>MAC Address</label>
                        <input type="text" id="dev-mac" value="${escapeHtml(mac)}" readonly style="opacity: 0.7;">
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Device Name</label>
                        <input type="text" id="dev-name" value="${escapeHtml(name)}" required autofocus>
                    </div>
                </div>
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1;">
                        <label>Owner (Person)</label>
                        <select id="dev-owner">
                            <option value="">None</option>
                            ${allOwners.map(o => {
                                const id = typeof o === "string" ? o : o.id;
                                const name = typeof o === "string" ? o : o.name;
                                return `<option value="${escapeHtml(id)}" ${id === owner ? 'selected' : ''}>${escapeHtml(name)}</option>`;
                            }).join("")}
                        </select>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Location (Room)</label>
                        <select id="dev-location">
                            <option value="">None</option>
                            ${allLocations.map(l => {
                                const id = typeof l === "string" ? l : l.id;
                                const name = typeof l === "string" ? l : l.name;
                                return `<option value="${escapeHtml(id)}" ${id === location ? 'selected' : ''}>${escapeHtml(name)}</option>`;
                            }).join("")}
                        </select>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>Static IP</label>
                        <input type="text" id="dev-static-ip" value="${escapeHtml(staticIp)}" placeholder="Optional">
                    </div>
                </div>
                <div class="form-row-multi flex-align-center" style="align-items: center; justify-content: space-between; margin-bottom: 20px;">
                    <div class="form-group" style="flex: 1; margin-bottom: 0; margin-right: 20px;">
                        <label>Tags (comma-separated)</label>
                        <input type="text" id="dev-tags" value="${escapeHtml(tags)}">
                    </div>
                    <label class="checkbox-container" style="margin-top: 20px;">
                        <input type="checkbox" id="dev-upnp" ${upnp ? 'checked' : ''}>
                        <span>Trust UPnP</span>
                    </label>
                </div>
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button type="button" class="btn btn-secondary" onclick="closeInlineForm()">Cancel</button>
                    <button type="submit" class="btn btn-success">Save Profile</button>
                </div>
            </form>
        </td>
    `;
    targetRow.parentNode.insertBefore(formRow, targetRow.nextSibling);
    formRow.scrollIntoView({ behavior: "smooth" });
};

window.deleteDevice = async function(mac) {
    if (confirm(`Are you sure you want to delete profile for MAC ${mac}?`)) {
        try {
            const res = await apiFetch(`/api/devices/${mac}`, { method: "DELETE" });
            if (res.ok) {
                loadDashboard();
            } else {
                alert("Failed to delete device.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeJs(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// 8. Network View Rendering & Callbacks
window.toggleWanIpInput = function(cb) {
    const ipGroup = document.getElementById("wan-ip-group");
    if (ipGroup) {
        ipGroup.style.display = cb.checked ? "none" : "block";
    }
};

function renderNetworks() {
    const tableBody = document.getElementById("networks-table-body");
    if (!networkSettings) return;

    const interfaces = networkSettings.interfaces || [];
    const bridges = networkSettings.bridges || [];
    const vlans = networkSettings.vlans || [];

    let rows = [];

    // 1. WAN Interface(s)
    interfaces.filter(i => i.role === "wan").forEach(wan => {
        rows.push({
            id: `wan-${wan.name}`,
            role: "Internet (WAN)",
            name: wan.name,
            type: "Internet",
            gateway: wan.dhcp ? "DHCP Client" : (wan.ip || "Static IP"),
            adapters: `<span class="badge badge-online">${escapeHtml(wan.name)}</span>`,
            actions: `<button class="btn btn-secondary btn-sm" onclick="editNetworkInline('wan', '${escapeJs(wan.name)}')">Edit</button>`,
            rawData: wan
        });
    });

    // 2. Bridges
    bridges.forEach(br => {
        const bound = interfaces.filter(i => i.bridge === br.name).map(i => i.name);
        const boundBadges = bound.length > 0 
            ? bound.map(n => `<span class="badge badge-outline">${escapeHtml(n)}</span>`).join(" ") 
            : `<span style="color: var(--text-secondary); font-size: 12px;">None</span>`;

        rows.push({
            id: `bridge-${br.name}`,
            role: `Local Bridge (${escapeHtml(br.name)})`,
            name: br.name,
            type: "Bridge",
            gateway: escapeHtml(br.ip),
            adapters: boundBadges,
            actions: `
                <button class="btn btn-secondary btn-sm" onclick="editNetworkInline('bridge', '${escapeJs(br.name)}')">Edit</button>
                ${br.name !== 'br0' ? `<button class="btn btn-secondary btn-sm" style="color: var(--accent-red);" onclick="deleteNetwork('bridge', '${escapeJs(br.name)}')">Delete</button>` : ''}
            `,
            rawData: br
        });
    });

    // 3. VLANs
    vlans.forEach(vl => {
        const isolateLabel = vl.isolate ? '<span style="color: var(--accent-red); font-size: 11px; margin-left: 6px;">(Isolated)</span>' : '';
        rows.push({
            id: `vlan-${vl.name}`,
            role: `VLAN (${escapeHtml(vl.name)})`,
            name: vl.name,
            type: `VLAN ${isolateLabel}`,
            gateway: escapeHtml(vl.ip),
            adapters: `<span class="badge badge-outline">${escapeHtml(vl.interface)} (VLAN ${vl.id})</span>`,
            actions: `
                <button class="btn btn-secondary btn-sm" onclick="editNetworkInline('vlan', '${escapeJs(vl.name)}')">Edit</button>
                <button class="btn btn-secondary btn-sm" style="color: var(--accent-red);" onclick="deleteNetwork('vlan', '${escapeJs(vl.name)}')">Delete</button>
            `,
            rawData: vl
        });
    });

    if (rows.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No networks configured.</td></tr>';
        return;
    }

    tableBody.innerHTML = rows.map(r => `
        <tr id="row-${r.id}">
            <td><strong>${r.role}</strong></td>
            <td>${r.type}</td>
            <td><code>${r.gateway}</code></td>
            <td>${r.adapters}</td>
            <td class="table-actions">${r.actions}</td>
        </tr>
    `).join("");
}

window.editNetworkInline = function(type, name) {
    const rowEl = document.getElementById(`row-${type}-${name}`);
    if (!rowEl) return;

    const interfaces = networkSettings.interfaces || [];
    const bridges = networkSettings.bridges || [];
    const vlans = networkSettings.vlans || [];

    if (type === 'wan') {
        const rawData = interfaces.find(i => i.name === name) || {};
        rowEl.innerHTML = `
            <td colspan="5">
                <form onsubmit="saveNetworkInline('wan', '${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%;">
                    <div class="form-group" style="margin: 0; flex: 1;">
                        <label style="margin: 0; font-size: 11px;">Physical Adapter</label>
                        <select name="wan_interface" class="theme-select" style="padding: 4px 8px; width: 100%;">
                            ${interfaces.map(i => `<option value="${i.name}" ${i.name === name ? 'selected' : ''}>${i.name}</option>`).join("")}
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                        <input type="checkbox" name="wan_dhcp" ${rawData.dhcp ? 'checked' : ''} onchange="toggleWanIpInput(this)">
                        <label style="margin: 0; font-size: 11px;">DHCP Client</label>
                    </div>
                    <div class="form-group" id="wan-ip-group" style="margin: 0; flex: 1; display: ${rawData.dhcp ? 'none' : 'block'};">
                        <label style="margin: 0; font-size: 11px;">Static IP / CIDR</label>
                        <input type="text" name="wan_ip" value="${escapeHtml(rawData.ip || '')}" placeholder="192.168.100.2/24" style="padding: 4px 8px; width: 100%;">
                    </div>
                    <div style="display: flex; gap: 8px; margin-top: 14px;">
                        <button type="submit" class="btn btn-primary btn-sm">Save</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="renderNetworks()">Cancel</button>
                    </div>
                </form>
            </td>
        `;
    } else if (type === 'bridge') {
        const rawData = bridges.find(b => b.name === name) || {};
        rowEl.innerHTML = `
            <td colspan="5">
                <form onsubmit="saveNetworkInline('bridge', '${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
                    <div style="display: flex; gap: 16px; align-items: center;">
                        <div class="form-group" style="margin: 0; flex: 1;">
                            <label style="margin: 0; font-size: 11px;">Gateway IP / Subnet</label>
                            <input type="text" name="bridge_ip" value="${escapeHtml(rawData.ip || '')}" required style="padding: 4px 8px; width: 100%;">
                        </div>
                        <div style="display: flex; gap: 8px; margin-top: 14px;">
                            <button type="submit" class="btn btn-primary btn-sm">Save</button>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="renderNetworks()">Cancel</button>
                        </div>
                    </div>
                    <div>
                        <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 6px;">Attach Physical Adapters:</label>
                        <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                            ${interfaces.map(i => {
                                const isBoundToThis = i.bridge === name;
                                return `
                                    <label class="checkbox-container" style="font-size: 12px;">
                                        <input type="checkbox" name="bound_adapters" value="${i.name}" ${isBoundToThis ? 'checked' : ''}>
                                        <span>${i.name}</span>
                                    </label>
                                `;
                            }).join("")}
                        </div>
                    </div>
                </form>
            </td>
        `;
    } else if (type === 'vlan') {
        const rawData = vlans.find(v => v.name === name) || {};
        rowEl.innerHTML = `
            <td colspan="5">
                <form onsubmit="saveNetworkInline('vlan', '${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap;">
                    <div class="form-group" style="margin: 0; flex: 1; min-width: 150px;">
                        <label style="margin: 0; font-size: 11px;">Gateway IP / Subnet</label>
                        <input type="text" name="vlan_ip" value="${escapeHtml(rawData.ip || '')}" required style="padding: 4px 8px; width: 100%;">
                    </div>
                    <div class="form-group" style="margin: 0; width: 80px;">
                        <label style="margin: 0; font-size: 11px;">VLAN ID</label>
                        <input type="number" name="vlan_id" value="${rawData.id || 10}" required style="padding: 4px 8px; width: 100%;">
                    </div>
                    <div class="form-group" style="margin: 0; flex: 1; min-width: 120px;">
                        <label style="margin: 0; font-size: 11px;">Parent Interface</label>
                        <select name="vlan_parent" class="theme-select" style="padding: 4px 8px; width: 100%;">
                            ${interfaces.map(i => `<option value="${i.name}" ${i.name === rawData.interface ? 'selected' : ''}>${i.name}</option>`).join("")}
                        </select>
                    </div>
                    <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                        <input type="checkbox" name="vlan_isolate" ${rawData.isolate ? 'checked' : ''}>
                        <label style="margin: 0; font-size: 11px;">Isolate Network</label>
                    </div>
                    <div style="display: flex; gap: 8px; margin-top: 14px;">
                        <button type="submit" class="btn btn-primary btn-sm">Save</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="renderNetworks()">Cancel</button>
                    </div>
                </form>
            </td>
        `;
    }
};

window.saveNetworkInline = async function(type, name, event) {
    event.preventDefault();
    const form = event.target;
    
    let interfaces = JSON.parse(JSON.stringify(networkSettings.interfaces || []));
    let bridges = JSON.parse(JSON.stringify(networkSettings.bridges || []));
    let vlans = JSON.parse(JSON.stringify(networkSettings.vlans || []));
    
    if (type === 'wan') {
        const selectedIf = form.elements['wan_interface'].value;
        const isDhcp = form.elements['wan_dhcp'].checked;
        const staticIp = form.elements['wan_ip'] ? form.elements['wan_ip'].value : "";
        
        interfaces.forEach(i => {
            if (i.name === name) {
                i.role = "lan";
                i.dhcp = false;
                i.ip = null;
            }
        });
        
        const targetIf = interfaces.find(i => i.name === selectedIf);
        if (targetIf) {
            targetIf.role = "wan";
            targetIf.dhcp = isDhcp;
            targetIf.ip = isDhcp ? null : staticIp;
            targetIf.bridge = null;
        } else {
            interfaces.push({
                name: selectedIf,
                role: "wan",
                dhcp: isDhcp,
                ip: isDhcp ? null : staticIp
            });
        }
    } else if (type === 'bridge') {
        const newIp = form.elements['bridge_ip'].value;
        
        // Extract checked bound_adapters
        let checkedAdapters = [];
        if (form.elements['bound_adapters']) {
            if (form.elements['bound_adapters'].value && !form.elements['bound_adapters'].length) {
                // Single element case
                if (form.elements['bound_adapters'].checked) checkedAdapters.push(form.elements['bound_adapters'].value);
            } else {
                checkedAdapters = Array.from(form.elements['bound_adapters'])
                    .filter(cb => cb.checked)
                    .map(cb => cb.value);
            }
        }
            
        const targetBr = bridges.find(b => b.name === name);
        if (targetBr) {
            targetBr.ip = newIp;
        }
        
        interfaces.forEach(i => {
            if (checkedAdapters.includes(i.name)) {
                i.bridge = name;
                i.role = "lan";
            } else if (i.bridge === name) {
                i.bridge = null;
            }
        });
    } else if (type === 'vlan') {
        const newIp = form.elements['vlan_ip'].value;
        const newId = parseInt(form.elements['vlan_id'].value, 10);
        const parentIf = form.elements['vlan_parent'].value;
        const isolate = form.elements['vlan_isolate'].checked;
        
        const targetVl = vlans.find(v => v.name === name);
        if (targetVl) {
            targetVl.ip = newIp;
            targetVl.id = newId;
            targetVl.interface = parentIf;
            targetVl.isolate = isolate;
        }
    }
    
    await sendNetworkConfigUpdate(interfaces, bridges, vlans);
};

window.showAddNetworkForm = function(position) {
    const tableBody = document.getElementById("networks-table-body");
    const interfaces = networkSettings.interfaces || [];

    const addRowHtml = `
        <tr id="temp-add-network-row">
            <td colspan="5">
                <form id="add-network-form" onsubmit="saveNewNetwork(event)" class="inline-edit-form" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
                    <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
                        <div class="form-group" style="margin: 0; width: 120px;">
                            <label style="margin: 0; font-size: 11px;">Network Type</label>
                            <select id="new_net_type" onchange="toggleNewNetworkFields(this.value)" class="theme-select" style="padding: 4px 8px; width: 100%;">
                                <option value="bridge">Bridge</option>
                                <option value="vlan">VLAN</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin: 0; flex: 1;">
                            <label style="margin: 0; font-size: 11px;">Network Name / ID</label>
                            <input type="text" id="new_net_name" required placeholder="e.g. br1 or vlan-guest" style="padding: 4px 8px; width: 100%;">
                        </div>
                        <div class="form-group" style="margin: 0; flex: 1;">
                            <label style="margin: 0; font-size: 11px;">Gateway IP / Subnet</label>
                            <input type="text" id="new_net_ip" required placeholder="e.g. 192.168.2.1/24" style="padding: 4px 8px; width: 100%;">
                        </div>
                        
                        <div class="form-group vlan-only-field" style="margin: 0; width: 80px; display: none;">
                            <label style="margin: 0; font-size: 11px;">VLAN ID</label>
                            <input type="number" id="new_vlan_id" placeholder="10" style="padding: 4px 8px; width: 100%;">
                        </div>
                        <div class="form-group vlan-only-field" style="margin: 0; flex: 1; min-width: 120px; display: none;">
                            <label style="margin: 0; font-size: 11px;">Parent Interface</label>
                            <select id="new_vlan_parent" class="theme-select" style="padding: 4px 8px; width: 100%;">
                                ${interfaces.map(i => `<option value="${i.name}">${i.name}</option>`).join("")}
                            </select>
                        </div>
                        <div class="form-group vlan-only-field" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px; display: none;">
                            <input type="checkbox" id="new_vlan_isolate" checked>
                            <label style="margin: 0; font-size: 11px;">Isolate Network</label>
                        </div>

                        <div style="display: flex; gap: 8px; margin-top: 14px;">
                            <button type="submit" class="btn btn-primary btn-sm">Save</button>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="cancelAddNetwork()">Cancel</button>
                        </div>
                    </div>

                    <div id="bridge-adapters-section">
                        <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 6px;">Attach Physical Adapters:</label>
                        <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                            ${interfaces.map(i => `
                                <label class="checkbox-container" style="font-size: 12px;">
                                    <input type="checkbox" name="new_bound_adapters" value="${i.name}">
                                    <span>${i.name}</span>
                                </label>
                            `).join("")}
                        </div>
                    </div>
                </form>
            </td>
        </tr>
    `;

    const existing = document.getElementById("temp-add-network-row");
    if (existing) existing.remove();

    if (position === "top") {
        tableBody.insertAdjacentHTML("afterbegin", addRowHtml);
    } else {
        tableBody.insertAdjacentHTML("beforeend", addRowHtml);
    }
};

window.toggleNewNetworkFields = function(type) {
    const vlanFields = document.querySelectorAll(".vlan-only-field");
    const bridgeSection = document.getElementById("bridge-adapters-section");
    
    if (type === "vlan") {
        vlanFields.forEach(el => el.style.display = "block");
        if (bridgeSection) bridgeSection.style.display = "none";
    } else {
        vlanFields.forEach(el => el.style.display = "none");
        if (bridgeSection) bridgeSection.style.display = "block";
    }
};

window.cancelAddNetwork = function() {
    const row = document.getElementById("temp-add-network-row");
    if (row) row.remove();
};

window.saveNewNetwork = async function(event) {
    event.preventDefault();
    const type = document.getElementById("new_net_type").value;
    const name = document.getElementById("new_net_name").value.trim();
    const ip = document.getElementById("new_net_ip").value.trim();
    
    let interfaces = JSON.parse(JSON.stringify(networkSettings.interfaces || []));
    let bridges = JSON.parse(JSON.stringify(networkSettings.bridges || []));
    let vlans = JSON.parse(JSON.stringify(networkSettings.vlans || []));
    
    if (type === 'bridge') {
        if (bridges.some(b => b.name === name)) {
            alert("A bridge with this name already exists.");
            return;
        }
        
        bridges.push({ name, ip });
        
        const boundAdaptersEls = document.getElementsByName("new_bound_adapters");
        let checkedAdapters = [];
        if (boundAdaptersEls) {
            checkedAdapters = Array.from(boundAdaptersEls)
                .filter(cb => cb.checked)
                .map(cb => cb.value);
        }
            
        interfaces.forEach(i => {
            if (checkedAdapters.includes(i.name)) {
                i.bridge = name;
                i.role = "lan";
            }
        });
    } else if (type === 'vlan') {
        if (vlans.some(v => v.name === name)) {
            alert("A VLAN with this name already exists.");
            return;
        }
        const vlanId = parseInt(document.getElementById("new_vlan_id").value || "10", 10);
        const parentIf = document.getElementById("new_vlan_parent").value;
        const isolate = document.getElementById("new_vlan_isolate").checked;
        
        vlans.push({
            name,
            id: vlanId,
            interface: parentIf,
            ip,
            isolate
        });
    }
    
    await sendNetworkConfigUpdate(interfaces, bridges, vlans);
};

window.deleteNetwork = async function(type, name) {
    if (!confirm(`Are you sure you want to delete the network "${name}"?`)) {
        return;
    }
    
    let interfaces = JSON.parse(JSON.stringify(networkSettings.interfaces || []));
    let bridges = JSON.parse(JSON.stringify(networkSettings.bridges || []));
    let vlans = JSON.parse(JSON.stringify(networkSettings.vlans || []));
    
    if (type === 'bridge') {
        bridges = bridges.filter(b => b.name !== name);
        interfaces.forEach(i => {
            if (i.bridge === name) {
                i.bridge = null;
            }
        });
    } else if (type === 'vlan') {
        vlans = vlans.filter(v => v.name !== name);
    }
    
    await sendNetworkConfigUpdate(interfaces, bridges, vlans);
};

async function sendNetworkConfigUpdate(interfaces, bridges, vlans) {
    try {
        const updatedNetwork = {
            ...networkSettings,
            interfaces,
            bridges,
            vlans
        };
        
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: updatedNetwork,
                wifi: wifiSettings,
                vpns: vpnSettings
            })
        });
        
        if (res.ok) {
            alert("Network configuration saved successfully!");
            loadDashboard();
        } else {
            alert("Failed to save network configuration.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

function renderWifiSettings(wifi) {
    const apsContainer = document.getElementById("wifi-aps-container");
    const aps = wifi.access_points || [];
    
    apsContainer.innerHTML = aps.map((ap, index) => `
        <div class="wifi-ap-row" style="margin-bottom: 24px;">
            <h4 style="font-size: 13px; margin-bottom: 12px; font-weight: 600; color: var(--text-secondary);">Access Point #${index + 1} (${escapeHtml(ap.interface)})</h4>
            <div class="form-row-multi">
                <div class="form-group" style="flex: 1;">
                    <label>SSID (Network Name)</label>
                    <input type="text" class="wifi-ap-ssid" data-index="${index}" value="${escapeHtml(ap.ssid)}" required>
                </div>
                <div class="form-group" style="flex: 1;">
                    <label>WiFi Passphrase</label>
                    <input type="password" class="wifi-ap-pass" data-index="${index}" value="${escapeHtml(ap.passphrase)}" required>
                </div>
                <div class="form-group" style="flex: 1;">
                    <label>Security Protocol</label>
                    <select class="wifi-ap-sec" data-index="${index}">
                        <option value="wpa3" ${ap.security === 'wpa3' ? 'selected' : ''}>WPA3 Personal</option>
                        <option value="wpa2" ${ap.security === 'wpa2' ? 'selected' : ''}>WPA2 Personal</option>
                    </select>
                </div>
            </div>
        </div>
    `).join("");
    
    const mesh = wifi.mesh || {};
    document.getElementById("wifi-mesh-enabled").checked = mesh.enabled || false;
    document.getElementById("wifi-mesh-ssid").value = mesh.ssid || "";
    document.getElementById("wifi-mesh-pass").value = mesh.passphrase || "";
}

function renderVPNsList(vpns) {
    const tableBody = document.getElementById("vpns-table-body");
    if (!vpns || vpns.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No VPN tunnels configured.</td></tr>';
        return;
    }
    tableBody.innerHTML = vpns.map(v => `
        <tr id="vpn-row-${v.id}">
            <td><strong>${escapeHtml(v.name)}</strong></td>
            <td><code>${escapeHtml(v.type.toUpperCase())}</code></td>
            <td>${escapeHtml(v.role.toUpperCase())}</td>
            <td><span class="badge ${v.enabled ? 'badge-online' : 'badge-offline'}">${v.enabled ? 'ENABLED' : 'DISABLED'}</span></td>
            <td>
                <button class="btn btn-secondary" onclick="toggleVpnEnabled('${escapeJs(v.id)}')">${v.enabled ? 'Disable' : 'Enable'}</button>
                <button class="btn btn-secondary" onclick="editVpnInline('${escapeJs(v.id)}')">Edit</button>
                <button class="btn btn-danger" onclick="deleteVpnProfile('${escapeJs(v.id)}')">Delete</button>
            </td>
        </tr>
    `).join("");
}

window.saveWifiSettings = async function(e) {
    e.preventDefault();
    const aps = wifiSettings.access_points || [];
    
    document.querySelectorAll(".wifi-ap-ssid").forEach(input => {
        const idx = parseInt(input.dataset.index, 10);
        aps[idx].ssid = input.value.trim();
    });
    document.querySelectorAll(".wifi-ap-pass").forEach(input => {
        const idx = parseInt(input.dataset.index, 10);
        aps[idx].passphrase = input.value;
    });
    document.querySelectorAll(".wifi-ap-sec").forEach(select => {
        const idx = parseInt(select.dataset.index, 10);
        aps[idx].security = select.value;
    });
    
    const mesh = {
        enabled: document.getElementById("wifi-mesh-enabled").checked,
        interface: wifiSettings.mesh?.interface || "wlan1",
        ssid: document.getElementById("wifi-mesh-ssid").value.trim(),
        passphrase: document.getElementById("wifi-mesh-pass").value,
        frequency: wifiSettings.mesh?.frequency || 5180
    };
    
    const updatedWifi = {
        access_points: aps,
        mesh: mesh
    };
    
    try {
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: networkSettings,
                wifi: updatedWifi,
                vpns: vpnSettings
            })
        });
        if (res.ok) {
            alert("WiFi and Mesh configurations saved successfully!");
            loadDashboard();
        } else {
            alert("Failed to save WiFi settings.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.showAddVpnForm = function() {
    const container = document.getElementById("vpn-add-container");
    const btn = document.getElementById("add-vpn-btn");
    if (container.style.display === "none") {
        container.style.display = "block";
        btn.textContent = "Cancel";
        btn.classList.replace("btn-primary", "btn-secondary");
        updateVpnProtocolFields();
    } else {
        container.style.display = "none";
        btn.textContent = "+ Add VPN Profile";
        btn.classList.replace("btn-secondary", "btn-primary");
    }
};

window.updateVpnProtocolFields = function() {
    const type = document.getElementById("vpn-type").value;
    const container = document.getElementById("vpn-protocol-fields");
    const handler = window.RoostOS.getVpnFormHandler(type);
    if (handler) {
        handler.renderConfigFields(container, {});
    } else {
        container.innerHTML = `<p style="font-size: 13px; color: var(--text-secondary);">No configuration fields registered for type: ${type}</p>`;
    }
};

window.addVpnProfile = async function(e) {
    e.preventDefault();
    const id = document.getElementById("vpn-id").value.trim();
    const name = document.getElementById("vpn-name").value.trim();
    const type = document.getElementById("vpn-type").value;
    const role = document.getElementById("vpn-role").value;
    
    if (vpnSettings.some(v => v.id === id)) {
        alert("A VPN profile with this ID already registered.");
        return;
    }

    const handler = window.RoostOS.getVpnFormHandler(type);
    const config = handler ? handler.serializeConfig() : {};
    
    const newVpn = {
        id, name, type, role, enabled: false, config
    };
    vpnSettings.push(newVpn);
    
    try {
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: networkSettings,
                wifi: wifiSettings,
                vpns: vpnSettings
            })
        });
        if (res.ok) {
            alert("VPN tunnel profile added successfully!");
            document.getElementById("vpn-add-form").reset();
            showAddVpnForm();
            loadDashboard();
        } else {
            alert("Failed to save VPN profile.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.editVpnInline = function(id) {
    const vpn = vpnSettings.find(v => v.id === id);
    if (!vpn) return;
    
    const row = document.getElementById(`vpn-row-${id}`);
    row.innerHTML = `
        <td colspan="5">
            <form onsubmit="saveVpnInline(event, '${escapeJs(id)}')" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
                <div class="form-row-multi">
                    <div class="form-group" style="flex: 1; margin-bottom: 0;">
                        <label>Profile Name</label>
                        <input type="text" id="edit-vpn-name-${id}" value="${escapeHtml(vpn.name)}" required>
                    </div>
                    <div class="form-group" style="flex: 1; margin-bottom: 0;">
                        <label>Role</label>
                        <select id="edit-vpn-role-${id}">
                            <option value="client" ${vpn.role === 'client' ? 'selected' : ''}>Client (Outbound)</option>
                            <option value="server" ${vpn.role === 'server' ? 'selected' : ''}>Server (Accept incoming)</option>
                        </select>
                    </div>
                </div>
                <div id="edit-vpn-protocol-fields-${id}" style="margin-top: 10px; margin-bottom: 10px;"></div>
                <div style="display: flex; gap: 12px;">
                    <button type="submit" class="btn btn-success">Save</button>
                    <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
                </div>
            </form>
        </td>
    `;
    
    const handler = window.RoostOS.getVpnFormHandler(vpn.type);
    if (handler) {
        handler.renderConfigFields(document.getElementById(`edit-vpn-protocol-fields-${id}`), vpn.config);
    }
};

window.saveVpnInline = async function(e, id) {
    e.preventDefault();
    const vpn = vpnSettings.find(v => v.id === id);
    if (!vpn) return;
    
    const name = document.getElementById(`edit-vpn-name-${id}`).value.trim();
    const role = document.getElementById(`edit-vpn-role-${id}`).value;
    
    const handler = window.RoostOS.getVpnFormHandler(vpn.type);
    const config = handler ? handler.serializeConfig() : {};
    
    vpn.name = name;
    vpn.role = role;
    vpn.config = config;
    
    try {
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: networkSettings,
                wifi: wifiSettings,
                vpns: vpnSettings
            })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to update VPN profile.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.toggleVpnEnabled = async function(id) {
    const vpn = vpnSettings.find(v => v.id === id);
    if (!vpn) return;
    vpn.enabled = !vpn.enabled;
    
    try {
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: networkSettings,
                wifi: wifiSettings,
                vpns: vpnSettings
            })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            vpn.enabled = !vpn.enabled;
            alert("Failed to toggle VPN tunnel.");
        }
    } catch (err) {
        vpn.enabled = !vpn.enabled;
        alert(`Error: ${err.message}`);
    }
};

window.deleteVpnProfile = async function(id) {
    if (confirm(`Are you sure you want to delete VPN profile '${id}'?`)) {
        const idx = vpnSettings.findIndex(v => v.id === id);
        if (idx === -1) return;
        const removed = vpnSettings.splice(idx, 1)[0];
        
        try {
            const res = await apiFetch("/api/network", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    network: networkSettings,
                    wifi: wifiSettings,
                    vpns: vpnSettings
                })
            });
            if (res.ok) {
                loadDashboard();
            } else {
                vpnSettings.splice(idx, 0, removed);
                alert("Failed to delete VPN profile.");
            }
        } catch (err) {
            vpnSettings.splice(idx, 0, removed);
            alert(`Error: ${err.message}`);
        }
    }
};

// 9. Plugins management rendering & callbacks
function renderPluginsList(plugins) {
    const coreTableBody = document.getElementById("plugins-core-table-body");
    const extraTableBody = document.getElementById("plugins-extra-table-body");
    
    const coreServices = ["dnsServer", "dnsFilter", "vpnServer", "vpnClient"];
    
    const corePlugins = (plugins || []).filter(p => 
        p.known_services && p.known_services.some(s => coreServices.includes(s))
    );
    const extraPlugins = (plugins || []).filter(p => 
        !p.known_services || !p.known_services.some(s => coreServices.includes(s))
    );

    window.expandedPlugins = window.expandedPlugins || new Set();

    const mapPluginRow = p => {
        const isExpanded = window.expandedPlugins.has(p.id);
        const displayStyle = isExpanded ? 'table-row' : 'none';
        
        let containerRows = "";
        if (p.container_statuses && p.container_statuses.length > 0) {
            containerRows = p.container_statuses.map(c => {
                let badgeClass = "badge-offline";
                if (c.status === "Running") badgeClass = "badge-online";
                else if (c.status === "Errored") badgeClass = "badge-danger";
                else if (c.status === "Missing") badgeClass = "badge-offline";
                
                return `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; border-bottom: 1px solid var(--border-color); font-size: 13px;">
                        <div>
                            <strong>${escapeHtml(c.name)}</strong> 
                            <span style="color: var(--text-secondary); font-size: 11px; margin-left: 8px;">(${escapeHtml(c.image)})</span>
                        </div>
                        <span class="badge ${badgeClass}">${escapeHtml(c.status.toUpperCase())}</span>
                    </div>
                `;
            }).join("");
        } else {
            containerRows = `<div style="padding: 12px; color: var(--text-secondary); font-size: 13px;">No containers defined in this plugin.</div>`;
        }

        return `
            <tr>
                <td><code>${escapeHtml(p.id)}</code></td>
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td>${escapeHtml(p.network_mode.toUpperCase())}</td>
                <td><span class="badge ${p.enabled ? 'badge-online' : 'badge-offline'}">${p.enabled ? 'RUNNING' : 'STOPPED'}</span></td>
                <td>
                    <button class="btn btn-secondary" onclick="togglePluginDetails('${escapeJs(p.id)}')">${isExpanded ? 'Hide Details' : 'Details'}</button>
                    <button class="btn btn-secondary" onclick="togglePluginEnabled('${escapeJs(p.id)}', ${!p.enabled})">${p.enabled ? 'Stop' : 'Start'}</button>
                    <button class="btn btn-danger" onclick="deletePlugin('${escapeJs(p.id)}')">Delete</button>
                </td>
            </tr>
            <tr id="plugin-details-${escapeHtml(p.id)}" style="display: ${displayStyle}; background: rgba(255, 255, 255, 0.01);">
                <td colspan="5" style="padding: 0;">
                    <div style="padding: 16px; border-top: 1px solid var(--border-color);">
                        <h4 style="margin: 0 0 12px 0; font-size: 13px; color: var(--text-primary);">Expected Containers</h4>
                        <div style="border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-card); overflow: hidden;">
                            ${containerRows}
                        </div>
                    </div>
                </td>
            </tr>
        `;
    };

    if (coreTableBody) {
        if (corePlugins.length === 0) {
            coreTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No core services currently active.</td></tr>';
        } else {
            coreTableBody.innerHTML = corePlugins.map(mapPluginRow).join("");
        }
    }

    if (extraTableBody) {
        if (extraPlugins.length === 0) {
            extraTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No extra hosted applications.</td></tr>';
        } else {
            extraTableBody.innerHTML = extraPlugins.map(mapPluginRow).join("");
        }
    }
}

window.togglePluginDetails = function(pluginId) {
    window.expandedPlugins = window.expandedPlugins || new Set();
    const el = document.getElementById(`plugin-details-${pluginId}`);
    if (el) {
        if (el.style.display === 'none') {
            el.style.display = 'table-row';
            window.expandedPlugins.add(pluginId);
        } else {
            el.style.display = 'none';
            window.expandedPlugins.delete(pluginId);
        }
        // Reload dashboard to update the button labels ("Details" vs "Hide Details") instantly
        loadDashboard();
    }
};

window.togglePluginEnabled = async function(id, enabled) {
    try {
        const res = await apiFetch(`/api/plugins/${id}/toggle`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to toggle plugin state.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.deletePlugin = async function(id) {
    if (confirm(`Are you sure you want to delete plugin '${id}'?`)) {
        try {
            const res = await apiFetch(`/api/plugins/${id}`, {
                method: "DELETE"
            });
            if (res.ok) {
                loadDashboard();
            } else {
                alert("Failed to delete plugin.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};

window.installCustomPlugin = async function(e) {
    e.preventDefault();
    const id = document.getElementById("plug-id").value.trim();
    const name = document.getElementById("plug-name").value.trim();
    const image = document.getElementById("plug-image").value.trim();
    const network_mode = document.getElementById("plug-netmode").value;
    const ui_entrypoint = document.getElementById("plug-ui-entrypoint").value.trim() || null;
    
    try {
        const res = await apiFetch("/api/plugins", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name, image, network_mode, ui_entrypoint })
        });
        if (res.ok) {
            alert(`Plugin '${name}' registered and starting...`);
            document.getElementById("plugin-install-form").reset();
            loadDashboard();
        } else {
            alert("Failed to install plugin.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.switchPluginInstallTab = function(tab) {
    const zipForm = document.getElementById("plugin-zip-form");
    const yamlForm = document.getElementById("plugin-manifest-form");
    const manualForm = document.getElementById("plugin-install-form");
    const zipBtn = document.getElementById("btn-tab-zip");
    const yamlBtn = document.getElementById("btn-tab-yaml");
    const manualBtn = document.getElementById("btn-tab-manual");
    
    zipForm.style.display = tab === "zip" ? "block" : "none";
    yamlForm.style.display = tab === "yaml" ? "block" : "none";
    manualForm.style.display = tab === "manual" ? "block" : "none";
    
    zipBtn.className = tab === "zip" ? "btn btn-primary" : "btn btn-secondary";
    yamlBtn.className = tab === "yaml" ? "btn btn-primary" : "btn btn-secondary";
    manualBtn.className = tab === "manual" ? "btn btn-primary" : "btn btn-secondary";
};

window.installPluginViaZip = async function(e) {
    e.preventDefault();
    const fileInput = document.getElementById("plug-zip-file");
    if (!fileInput.files || fileInput.files.length === 0) {
        alert("Please select a ZIP file to upload.");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    try {
        const res = await apiFetch("/api/plugins/upload", {
            method: "POST",
            body: formData
        });
        if (res.ok) {
            alert("Plugin package installed successfully!");
            document.getElementById("plugin-zip-form").reset();
            loadDashboard();
        } else {
            const errData = await res.json();
            alert(`Failed to install ZIP package: ${errData.detail || 'check logs'}`);
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.installPluginViaManifest = async function(e) {
    e.preventDefault();
    const manifest_yaml = document.getElementById("plug-yaml").value;
    
    try {
        const res = await apiFetch("/api/plugins/manifest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ manifest_yaml })
        });
        if (res.ok) {
            alert("Plugin registered and loaded from manifest successfully!");
            document.getElementById("plugin-manifest-form").reset();
            loadDashboard();
        } else {
            const errData = await res.json();
            alert(`Failed to install manifest: ${errData.detail || 'check logs'}`);
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

// 10. People & Locations Management Callbacks
let currentPeople = [];
let currentBuildings = [];
let currentRooms = [];

function renderPeopleList(people) {
    currentPeople = people;
    const tableBody = document.getElementById("people-table-body");
    if (!people || people.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No family member profiles configured.</td></tr>';
        return;
    }
    tableBody.innerHTML = people.map(p => `
        <tr id="person-row-${p.id}">
            <td><code>${escapeHtml(p.id)}</code></td>
            <td><strong>${escapeHtml(p.name)}</strong></td>
            <td><span class="badge badge-online">${escapeHtml(p.dns_profile || 'none').toUpperCase()}</span></td>
            <td>
                <button class="btn btn-secondary" onclick="editPersonInline('${escapeJs(p.id)}')">Edit</button>
                <button class="btn btn-danger" onclick="deletePerson('${escapeJs(p.id)}')">Delete</button>
            </td>
        </tr>
    `).join("");
}

window.showAddPersonForm = function(position) {
    const tableBody = document.getElementById("people-table-body");
    const emptyRow = tableBody.querySelector(".empty-state");
    if (emptyRow) tableBody.innerHTML = "";

    const addRow = document.createElement("tr");
    addRow.id = "person-row-new";
    addRow.innerHTML = `
        <td colspan="4">
            <form onsubmit="saveNewPersonInline(event)" style="display: flex; gap: 12px; align-items: center; width: 100%;">
                <input type="text" id="new-person-id" placeholder="ID (e.g. alice)" required style="flex: 1;">
                <input type="text" id="new-person-name" placeholder="Display Name" required style="flex: 1;">
                <select id="new-person-dns" style="flex: 1;">
                    <option value="none">None (Default)</option>
                    <option value="adult">Adult (Unfiltered)</option>
                    <option value="teen">Teen Filter</option>
                    <option value="child">Child Filter</option>
                </select>
                <button type="submit" class="btn btn-success">Save</button>
                <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
            </form>
        </td>
    `;
    if (position === "top") {
        tableBody.insertBefore(addRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(addRow);
    }
};

window.saveNewPersonInline = async function(e) {
    e.preventDefault();
    const id = document.getElementById("new-person-id").value.trim();
    const name = document.getElementById("new-person-name").value.trim();
    const dns_profile = document.getElementById("new-person-dns").value;
    
    try {
        const res = await apiFetch("/api/people", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name, dns_profile })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to add family member.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.editPersonInline = function(id) {
    const person = currentPeople.find(p => p.id === id);
    if (!person) return;
    
    const row = document.getElementById(`person-row-${id}`);
    row.innerHTML = `
        <td colspan="4">
            <form onsubmit="savePersonInline(event, '${escapeJs(id)}')" style="display: flex; gap: 12px; align-items: center; width: 100%;">
                <span style="font-family: monospace; font-weight: bold; flex: 1;">${escapeHtml(id)}</span>
                <input type="text" id="edit-person-name-${id}" value="${escapeHtml(person.name)}" required placeholder="Display Name" style="flex: 1;">
                <select id="edit-person-dns-${id}" style="flex: 1;">
                    <option value="none" ${person.dns_profile === 'none' || !person.dns_profile ? 'selected' : ''}>None (Default)</option>
                    <option value="adult" ${person.dns_profile === 'adult' ? 'selected' : ''}>Adult (Unfiltered)</option>
                    <option value="teen" ${person.dns_profile === 'teen' ? 'selected' : ''}>Teen Filter</option>
                    <option value="child" ${person.dns_profile === 'child' ? 'selected' : ''}>Child Filter</option>
                </select>
                <button type="submit" class="btn btn-success">Save</button>
                <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
            </form>
        </td>
    `;
};

window.savePersonInline = async function(e, id) {
    e.preventDefault();
    const name = document.getElementById(`edit-person-name-${id}`).value.trim();
    const dns_profile = document.getElementById(`edit-person-dns-${id}`).value;
    
    try {
        const res = await apiFetch("/api/people", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name, dns_profile })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to update family member.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.deletePerson = async function(id) {
    if (confirm(`Are you sure you want to delete family profile '${id}'?`)) {
        try {
            const res = await apiFetch(`/api/people/${id}`, { method: "DELETE" });
            if (res.ok) {
                loadDashboard();
            } else {
                alert("Failed to delete person.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};

function renderBuildingsList(buildings) {
    currentBuildings = buildings;
    const tableBody = document.getElementById("buildings-table-body");
    if (!buildings || buildings.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3" class="empty-state">No buildings configured.</td></tr>';
        return;
    }
    tableBody.innerHTML = buildings.map(b => `
        <tr id="building-row-${b.id}">
            <td><code>${escapeHtml(b.id)}</code></td>
            <td><strong>${escapeHtml(b.name)}</strong></td>
            <td>
                <button class="btn btn-secondary" onclick="editBuildingInline('${escapeJs(b.id)}')">Edit</button>
                <button class="btn btn-danger" onclick="deleteBuilding('${escapeJs(b.id)}')">Delete</button>
            </td>
        </tr>
    `).join("");
}

window.showAddBuildingForm = function(position) {
    const tableBody = document.getElementById("buildings-table-body");
    const emptyRow = tableBody.querySelector(".empty-state");
    if (emptyRow) tableBody.innerHTML = "";

    const addRow = document.createElement("tr");
    addRow.id = "building-row-new";
    addRow.innerHTML = `
        <td colspan="3">
            <form onsubmit="saveNewBuildingInline(event)" style="display: flex; gap: 12px; align-items: center; width: 100%;">
                <input type="text" id="new-bld-id" placeholder="ID (e.g. main)" required style="flex: 1;">
                <input type="text" id="new-bld-name" placeholder="Building Name" required style="flex: 1;">
                <button type="submit" class="btn btn-success">Save</button>
                <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
            </form>
        </td>
    `;
    if (position === "top") {
        tableBody.insertBefore(addRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(addRow);
    }
};

window.saveNewBuildingInline = async function(e) {
    e.preventDefault();
    const id = document.getElementById("new-bld-id").value.trim();
    const name = document.getElementById("new-bld-name").value.trim();
    
    try {
        const res = await apiFetch("/api/buildings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to add building.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.editBuildingInline = function(id) {
    const bld = currentBuildings.find(b => b.id === id);
    if (!bld) return;
    
    const row = document.getElementById(`building-row-${id}`);
    row.innerHTML = `
        <td colspan="3">
            <form onsubmit="saveBuildingInline(event, '${escapeJs(id)}')" style="display: flex; gap: 12px; align-items: center; width: 100%;">
                <span style="font-family: monospace; font-weight: bold; flex: 1;">${escapeHtml(id)}</span>
                <input type="text" id="edit-bld-name-${id}" value="${escapeHtml(bld.name)}" required placeholder="Building Name" style="flex: 1;">
                <button type="submit" class="btn btn-success">Save</button>
                <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
            </form>
        </td>
    `;
};

window.saveBuildingInline = async function(e, id) {
    e.preventDefault();
    const name = document.getElementById(`edit-bld-name-${id}`).value.trim();
    
    try {
        const res = await apiFetch("/api/buildings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to update building.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.deleteBuilding = async function(id) {
    if (confirm(`Are you sure you want to delete building '${id}'?`)) {
        try {
            const res = await apiFetch(`/api/buildings/${id}`, { method: "DELETE" });
            if (res.ok) {
                loadDashboard();
            } else {
                alert("Failed to delete building.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};

function populateBuildingDropdowns(buildings) {
    // Left for potential custom uses
}

function renderRoomsList(rooms) {
    currentRooms = rooms;
    const tableBody = document.getElementById("rooms-table-body");
    if (!rooms || rooms.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No rooms configured.</td></tr>';
        return;
    }
    tableBody.innerHTML = rooms.map(r => `
        <tr id="room-row-${r.id}">
            <td><code>${escapeHtml(r.id)}</code></td>
            <td><strong>${escapeHtml(r.name)}</strong></td>
            <td><code>${escapeHtml(r.building)}</code></td>
            <td>
                <button class="btn btn-secondary" onclick="editRoomInline('${escapeJs(r.id)}')">Edit</button>
                <button class="btn btn-danger" onclick="deleteRoom('${escapeJs(r.id)}')">Delete</button>
            </td>
        </tr>
    `).join("");
}

window.showAddRoomForm = function(position) {
    const tableBody = document.getElementById("rooms-table-body");
    const emptyRow = tableBody.querySelector(".empty-state");
    if (emptyRow) tableBody.innerHTML = "";

    const addRow = document.createElement("tr");
    addRow.id = "room-row-new";
    addRow.innerHTML = `
        <td colspan="4">
            <form onsubmit="saveNewRoomInline(event)" style="display: flex; gap: 12px; align-items: center; width: 100%;">
                <input type="text" id="new-rm-id" placeholder="ID (e.g. kitchen)" required style="flex: 1;">
                <input type="text" id="new-rm-name" placeholder="Room Name" required style="flex: 1;">
                <select id="new-rm-building" style="flex: 1;">
                    ${currentBuildings.map(b => `<option value="${escapeHtml(b.id)}">${escapeHtml(b.name)}</option>`).join("")}
                </select>
                <button type="submit" class="btn btn-success">Save</button>
                <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
            </form>
        </td>
    `;
    if (position === "top") {
        tableBody.insertBefore(addRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(addRow);
    }
};

window.saveNewRoomInline = async function(e) {
    e.preventDefault();
    const id = document.getElementById("new-rm-id").value.trim();
    const name = document.getElementById("new-rm-name").value.trim();
    const building = document.getElementById("new-rm-building").value;
    
    try {
        const res = await apiFetch("/api/rooms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name, building })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to add room.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.editRoomInline = function(id) {
    const rm = currentRooms.find(r => r.id === id);
    if (!rm) return;
    
    const row = document.getElementById(`room-row-${id}`);
    row.innerHTML = `
        <td colspan="4">
            <form onsubmit="saveRoomInline(event, '${escapeJs(id)}')" style="display: flex; gap: 12px; align-items: center; width: 100%;">
                <span style="font-family: monospace; font-weight: bold; flex: 1;">${escapeHtml(id)}</span>
                <input type="text" id="edit-rm-name-${id}" value="${escapeHtml(rm.name)}" required placeholder="Room Name" style="flex: 1;">
                <select id="edit-rm-building-${id}" style="flex: 1;">
                    ${currentBuildings.map(b => `<option value="${escapeHtml(b.id)}" ${b.id === rm.building ? 'selected' : ''}>${escapeHtml(b.name)}</option>`).join("")}
                </select>
                <button type="submit" class="btn btn-success">Save</button>
                <button type="button" class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
            </form>
        </td>
    `;
};

window.saveRoomInline = async function(e, id) {
    e.preventDefault();
    const name = document.getElementById(`edit-rm-name-${id}`).value.trim();
    const building = document.getElementById(`edit-rm-building-${id}`).value;
    
    try {
        const res = await apiFetch("/api/rooms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, name, building })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to update room.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.deleteRoom = async function(id) {
    if (confirm(`Are you sure you want to delete room '${id}'?`)) {
        try {
            const res = await apiFetch(`/api/rooms/${id}`, { method: "DELETE" });
            if (res.ok) {
                loadDashboard();
            } else {
                alert("Failed to delete room.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};


// ==========================================
// DHCP Server View Rendering & Operations
// ==========================================
window.renderDHCPView = function() {
    const activeBody = document.getElementById("dhcp-active-leases-body");
    const staticBody = document.getElementById("dhcp-static-reservations-body");
    if (!activeBody || !staticBody) return;

    const staticDevices = allDevices.filter(d => d.static_ip);

    document.getElementById("dhcp-lease-count").textContent = activeLeases.length;
    document.getElementById("dhcp-static-count").textContent = staticDevices.length;

    // Render active dynamic leases
    if (activeLeases.length === 0) {
        activeBody.innerHTML = '<tr><td colspan="5" class="empty-state">No active dynamic leases found.</td></tr>';
    } else {
        activeBody.innerHTML = activeLeases.map(l => {
            const isStatic = allDevices.some(d => d.mac.toLowerCase() === l.mac.toLowerCase() && d.static_ip);
            return `
                <tr>
                    <td><code>${escapeHtml(l.ip)}</code></td>
                    <td><code>${escapeHtml(l.mac.toUpperCase())}</code></td>
                    <td>${escapeHtml(l.hostname || "-")}</td>
                    <td><span class="badge badge-online">DYNAMIC ACTIVE</span></td>
                    <td>
                        ${isStatic ? '<span style="font-size: 11px; color: var(--text-secondary);">Already Static</span>' : 
                        `<button class="btn btn-secondary" onclick="promoteToStatic('${escapeJs(l.mac)}', '${escapeJs(l.ip)}', '${escapeJs(l.hostname || "Device")}')">Make Static</button>`}
                    </td>
                </tr>
            `;
        }).join("");
    }

    // Render static reservations
    if (staticDevices.length === 0) {
        staticBody.innerHTML = '<tr><td colspan="4" class="empty-state">No static reservations configured.</td></tr>';
    } else {
        staticBody.innerHTML = staticDevices.map(d => `
            <tr id="dhcp-static-row-${d.mac.replace(/:/g, "-")}">
                <td><code>${escapeHtml(d.mac.toUpperCase())}</code></td>
                <td><strong>${escapeHtml(d.name)}</strong></td>
                <td><code>${escapeHtml(d.static_ip)}</code></td>
                <td>
                    <button class="btn btn-secondary" onclick="editStaticDhcpInline('${escapeJs(d.mac)}')">Edit</button>
                    <button class="btn btn-danger" onclick="deleteStaticDhcp('${escapeJs(d.mac)}')">Delete</button>
                </td>
            </tr>
        `).join("");
    }

    // Render DHCP Address Pools & Scopes under the Advanced tab
    renderDhcpScopes();
};

window.renderDhcpScopes = function() {
    const scopesBody = document.getElementById("dhcp-scopes-table-body");
    if (!scopesBody) return;

    const bridges = networkSettings.bridges || [];
    const vlans = networkSettings.vlans || [];
    const allScopes = [];

    // Gather bridges
    bridges.forEach(b => {
        allScopes.push({
            type: "bridge",
            name: b.name,
            ip: b.ip,
            dhcp_enabled: b.dhcp_enabled !== false,
            dhcp_pool_start: b.dhcp_pool_start || "",
            dhcp_pool_end: b.dhcp_pool_end || ""
        });
    });

    // Gather VLANs
    vlans.forEach(v => {
        allScopes.push({
            type: "vlan",
            name: v.name,
            ip: v.ip,
            dhcp_enabled: v.dhcp_enabled !== false,
            dhcp_pool_start: v.dhcp_pool_start || "",
            dhcp_pool_end: v.dhcp_pool_end || ""
        });
    });

    if (allScopes.length === 0) {
        scopesBody.innerHTML = '<tr><td colspan="5" class="empty-state">No network interfaces configured.</td></tr>';
        return;
    }

    scopesBody.innerHTML = allScopes.map(s => {
        const idStr = `${s.type}-${s.name}`;
        const serviceStatus = s.dhcp_enabled 
            ? `<span class="badge badge-online">DHCP ENABLED</span>` 
            : `<span class="badge badge-offline">DHCP DISABLED</span>`;
            
        const rangeText = (s.dhcp_pool_start && s.dhcp_pool_end) 
            ? `<code>${escapeHtml(s.dhcp_pool_start)} - ${escapeHtml(s.dhcp_pool_end)}</code>` 
            : `<span style="font-size: 11px; color: var(--text-secondary);">Default (.100 - .250)</span>`;

        return `
            <tr id="dhcp-scope-row-${idStr}">
                <td><strong>${escapeHtml(s.name)}</strong> <span style="font-size:11px; text-transform:uppercase; color:var(--text-secondary);">(${s.type})</span></td>
                <td><code>${escapeHtml(s.ip)}</code></td>
                <td>${serviceStatus}</td>
                <td>${rangeText}</td>
                <td>
                    <button class="btn btn-secondary" onclick="editDhcpScopeInline('${escapeJs(s.type)}', '${escapeJs(s.name)}')">Edit</button>
                </td>
            </tr>
        `;
    }).join("");
};

window.editDhcpScopeInline = function(type, name) {
    const idStr = `${type}-${name}`;
    const rowEl = document.getElementById(`dhcp-scope-row-${idStr}`);
    if (!rowEl) return;

    const bridges = networkSettings.bridges || [];
    const vlans = networkSettings.vlans || [];
    const scope = (type === "bridge") 
        ? bridges.find(b => b.name === name) 
        : vlans.find(v => v.name === name);

    if (!scope) return;

    const enabled = scope.dhcp_enabled !== false;
    const start = scope.dhcp_pool_start || "";
    const end = scope.dhcp_pool_end || "";

    rowEl.innerHTML = `
        <td><strong>${escapeHtml(name)}</strong> <span style="font-size:11px; text-transform:uppercase; color:var(--text-secondary);">(${type})</span></td>
        <td><code>${escapeHtml(scope.ip)}</code></td>
        <td>
            <label class="checkbox-container" style="margin: 0;">
                <input type="checkbox" id="edit-scope-enabled-${idStr}" ${enabled ? "checked" : ""}>
                <span>Enabled</span>
            </label>
        </td>
        <td>
            <div style="display: flex; gap: 8px; align-items: center;">
                <input type="text" id="edit-scope-start-${idStr}" value="${escapeHtml(start)}" placeholder="e.g. 192.168.1.100" style="max-width: 140px; margin: 0; padding: 4px 8px;">
                <span>to</span>
                <input type="text" id="edit-scope-end-${idStr}" value="${escapeHtml(end)}" placeholder="e.g. 192.168.1.200" style="max-width: 140px; margin: 0; padding: 4px 8px;">
            </div>
        </td>
        <td>
            <button class="btn btn-success" onclick="saveDhcpScopeInline('${escapeJs(type)}', '${escapeJs(name)}')">Save</button>
            <button class="btn btn-secondary" onclick="renderDhcpScopes()">Cancel</button>
        </td>
    `;
};

window.saveDhcpScopeInline = async function(type, name) {
    const idStr = `${type}-${name}`;
    const enabled = document.getElementById(`edit-scope-enabled-${idStr}`).checked;
    const startVal = document.getElementById(`edit-scope-start-${idStr}`).value.trim();
    const endVal = document.getElementById(`edit-scope-end-${idStr}`).value.trim();

    const updatedBridges = (networkSettings.bridges || []).map(b => {
        if (type === "bridge" && b.name === name) {
            return {
                ...b,
                dhcp_enabled: enabled,
                dhcp_pool_start: startVal || null,
                dhcp_pool_end: endVal || null
            };
        }
        return b;
    });

    const updatedVlans = (networkSettings.vlans || []).map(v => {
        if (type === "vlan" && v.name === name) {
            return {
                ...v,
                dhcp_enabled: enabled,
                dhcp_pool_start: startVal || null,
                dhcp_pool_end: endVal || null
            };
        }
        return v;
    });

    try {
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: {
                    interfaces: networkSettings.interfaces || [],
                    bridges: updatedBridges,
                    vlans: updatedVlans,
                    gateways: networkSettings.gateways || []
                },
                wifi: wifiSettings,
                vpns: vpnSettings
            })
        });

        if (res.ok) {
            alert("DHCP scope updated successfully!");
            loadDashboard();
        } else {
            const errData = await res.json();
            alert(`Failed to save DHCP scope: ${errData.detail || "Server error"}`);
        }
    } catch (err) {
        alert(`Error saving DHCP scope: ${err.message}`);
    }
};

window.promoteToStatic = async function(mac, ip, hostname) {
    let device = allDevices.find(d => d.mac.toLowerCase() === mac.toLowerCase());
    if (device) {
        device.static_ip = ip;
    } else {
        device = {
            mac: mac,
            name: hostname || "Promoted Lease",
            owner: "",
            location: "",
            tags: ["personal"],
            static_ip: ip,
            upnp_trusted: false
        };
    }
    
    try {
        const res = await apiFetch("/api/devices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(device)
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to promote lease to static.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.editStaticDhcpInline = function(mac) {
    const trId = `dhcp-static-row-${mac.replace(/:/g, "-")}`;
    const row = document.getElementById(trId);
    if (!row) return;
    
    const device = allDevices.find(d => d.mac === mac);
    if (!device) return;
    
    row.innerHTML = `
        <td><code>${escapeHtml(device.mac.toUpperCase())}</code></td>
        <td><input type="text" id="edit-dhcp-name-${mac.replace(/:/g, "-")}" value="${escapeHtml(device.name)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td><input type="text" id="edit-dhcp-ip-${mac.replace(/:/g, "-")}" value="${escapeHtml(device.static_ip)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td>
            <button class="btn btn-success" onclick="saveStaticDhcpInline('${escapeJs(mac)}')">Save</button>
            <button class="btn btn-secondary" onclick="renderDHCPView()">Cancel</button>
        </td>
    `;
};

window.saveStaticDhcpInline = async function(mac) {
    const nameInput = document.getElementById(`edit-dhcp-name-${mac.replace(/:/g, "-")}`);
    const ipInput = document.getElementById(`edit-dhcp-ip-${mac.replace(/:/g, "-")}`);
    if (!nameInput || !ipInput) return;
    
    const newName = nameInput.value.trim();
    const newIp = ipInput.value.trim();
    if (!newName || !newIp) {
        alert("Friendly Name and Static IP Address are required.");
        return;
    }
    
    const device = allDevices.find(d => d.mac === mac);
    if (!device) return;
    
    const updatedDevice = {
        ...device,
        name: newName,
        static_ip: newIp
    };
    
    try {
        const res = await apiFetch("/api/devices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updatedDevice)
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to save static reservation. Check IP subnet format.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.showAddStaticDhcpForm = function(position) {
    const tableBody = document.getElementById("dhcp-static-reservations-body");
    if (!tableBody) return;
    
    const existing = document.getElementById("dhcp-static-add-row");
    if (existing) existing.remove();
    
    const addRow = document.createElement("tr");
    addRow.id = "dhcp-static-add-row";
    addRow.innerHTML = `
        <td><input type="text" id="add-dhcp-mac" placeholder="aa:bb:cc:dd:ee:ff" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td><input type="text" id="add-dhcp-name" placeholder="Laptop Name" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td><input type="text" id="add-dhcp-ip" placeholder="192.168.1.10" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td>
            <button class="btn btn-success" onclick="saveNewStaticDhcpInline()">Save</button>
            <button class="btn btn-secondary" onclick="document.getElementById('dhcp-static-add-row').remove()">Cancel</button>
        </td>
    `;
    
    if (position === "top") {
        tableBody.insertBefore(addRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(addRow);
    }
};

window.saveNewStaticDhcpInline = async function() {
    const macInput = document.getElementById("add-dhcp-mac");
    const nameInput = document.getElementById("add-dhcp-name");
    const ipInput = document.getElementById("add-dhcp-ip");
    if (!macInput || !nameInput || !ipInput) return;
    
    const mac = macInput.value.trim();
    const name = nameInput.value.trim();
    const ip = ipInput.value.trim();
    if (!mac || !name || !ip) {
        alert("All fields are required.");
        return;
    }
    
    const newDevice = {
        mac: mac,
        name: name,
        owner: "",
        location: "",
        tags: [],
        static_ip: ip,
        upnp_trusted: false
    };
    
    try {
        const res = await apiFetch("/api/devices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(newDevice)
        });
        if (res.ok) {
            loadDashboard();
        } else {
            alert("Failed to create static reservation. Check MAC and IP formats.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.deleteStaticDhcp = async function(mac) {
    const device = allDevices.find(d => d.mac === mac);
    if (!device) return;
    
    if (confirm(`Remove static IP reservation for ${device.name} (${mac})?`)) {
        const updatedDevice = {
            ...device,
            static_ip: ""
        };
        try {
            const res = await apiFetch("/api/devices", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedDevice)
            });
            if (res.ok) {
                loadDashboard();
            } else {
                alert("Failed to clear static IP reservation.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};


// ==========================================
// DNS Resolver View Rendering & Operations
// ==========================================
window.saveDnsConfig = async function(e) {
    e.preventDefault();
    const forwardersVal = document.getElementById("dns-forwarders").value.trim();
    const adblock = document.getElementById("dns-adblock-enabled").checked;
    
    const forwarders = forwardersVal.split(",")
                                     .map(s => s.trim())
                                     .filter(s => s.length > 0);
                                     
    try {
        const res = await apiFetch("/api/dns/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ forwarders, ad_blocking_enabled: adblock })
        });
        if (res.ok) {
            alert("DNS Resolver settings saved successfully!");
            loadDashboard();
        } else {
            alert("Failed to save DNS settings.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.renderLocalDnsRecords = function() {
    const tableBody = document.getElementById("dns-records-table-body");
    if (!tableBody) return;
    
    if (localDnsRecords.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No custom local DNS records configured.</td></tr>';
        return;
    }
    
    tableBody.innerHTML = localDnsRecords.map((r, index) => `
        <tr id="dns-record-row-${index}">
            <td><code>${escapeHtml(r.domain)}</code></td>
            <td><code>${escapeHtml(r.ip)}</code></td>
            <td><span class="badge badge-online">${escapeHtml(r.type)}</span></td>
            <td>
                <button class="btn btn-secondary" onclick="editLocalDnsInline(${index})">Edit</button>
                <button class="btn btn-danger" onclick="deleteLocalDnsRecord(${index})">Delete</button>
            </td>
        </tr>
    `).join("");
};

window.editLocalDnsInline = function(index) {
    const row = document.getElementById(`dns-record-row-${index}`);
    if (!row) return;
    const r = localDnsRecords[index];
    
    row.innerHTML = `
        <td><input type="text" id="edit-dns-domain-${index}" value="${escapeHtml(r.domain)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td><input type="text" id="edit-dns-ip-${index}" value="${escapeHtml(r.ip)}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td>
            <select id="edit-dns-type-${index}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px;">
                <option value="A" ${r.type === 'A' ? 'selected' : ''}>A</option>
                <option value="AAAA" ${r.type === 'AAAA' ? 'selected' : ''}>AAAA</option>
                <option value="CNAME" ${r.type === 'CNAME' ? 'selected' : ''}>CNAME</option>
            </select>
        </td>
        <td>
            <button class="btn btn-success" onclick="saveLocalDnsInline(${index})">Save</button>
            <button class="btn btn-secondary" onclick="renderLocalDnsRecords()">Cancel</button>
        </td>
    `;
};

window.saveLocalDnsInline = function(index) {
    const domain = document.getElementById(`edit-dns-domain-${index}`).value.trim();
    const ip = document.getElementById(`edit-dns-ip-${index}`).value.trim();
    const type = document.getElementById(`edit-dns-type-${index}`).value;
    
    if (!domain || !ip) {
        alert("Domain Name and IP Address are required.");
        return;
    }
    
    localDnsRecords[index] = { domain, ip, type };
    renderLocalDnsRecords();
};

window.showAddDnsRecordForm = function(position) {
    const tableBody = document.getElementById("dns-records-table-body");
    if (!tableBody) return;
    
    const existing = document.getElementById("dns-record-add-row");
    if (existing) existing.remove();
    
    const addRow = document.createElement("tr");
    addRow.id = "dns-record-add-row";
    addRow.innerHTML = `
        <td><input type="text" id="add-dns-domain" placeholder="server.lan" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td><input type="text" id="add-dns-ip" placeholder="192.168.1.20" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td>
            <select id="add-dns-type" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                <option value="A">A</option>
                <option value="AAAA">AAAA</option>
                <option value="CNAME">CNAME</option>
            </select>
        </td>
        <td>
            <button class="btn btn-success" onclick="saveNewLocalDnsInline()">Save</button>
            <button class="btn btn-secondary" onclick="document.getElementById('dns-record-add-row').remove()">Cancel</button>
        </td>
    `;
    
    if (position === "top") {
        tableBody.insertBefore(addRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(addRow);
    }
};

window.saveNewLocalDnsInline = function() {
    const domain = document.getElementById("add-dns-domain").value.trim();
    const ip = document.getElementById("add-dns-ip").value.trim();
    const type = document.getElementById("add-dns-type").value;
    
    if (!domain || !ip) {
        alert("All fields are required.");
        return;
    }
    
    localDnsRecords.push({ domain, ip, type });
    renderLocalDnsRecords();
};

window.deleteLocalDnsRecord = function(index) {
    if (confirm("Remove this local DNS record?")) {
        localDnsRecords.splice(index, 1);
        renderLocalDnsRecords();
    }
};


// ==========================================
// Operator User View Rendering & Operations
// ==========================================
let allUsers = [];

window.renderUsersList = function(users) {
    const tableBody = document.getElementById("users-table-body");
    if (!tableBody) return;
    
    allUsers = users || [];
    if (allUsers.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No operator user logins configured.</td></tr>';
        return;
    }
    
    tableBody.innerHTML = allUsers.map(u => `
        <tr id="user-row-${u.username}">
            <td><strong>${escapeHtml(u.username)}</strong></td>
            <td><span class="badge ${u.role === 'admin' ? 'badge-online' : 'badge-offline'}">${escapeHtml(u.role.toUpperCase())}</span></td>
            <td>${escapeHtml(u.person || "None Linked")}</td>
            <td>
                <button class="btn btn-secondary" onclick="editUserInline('${escapeJs(u.username)}')">Edit</button>
                <button class="btn btn-danger" onclick="deleteUser('${escapeJs(u.username)}')">Delete</button>
            </td>
        </tr>
    `).join("");
};

window.showAddUserForm = function(position) {
    const tableBody = document.getElementById("users-table-body");
    if (!tableBody) return;
    
    const existing = document.getElementById("user-add-row");
    if (existing) existing.remove();
    
    const addRow = document.createElement("tr");
    addRow.id = "user-add-row";
    addRow.innerHTML = `
        <td><input type="text" id="add-user-username" placeholder="username" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;"></td>
        <td>
            <select id="add-user-role" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                <option value="member">Member</option>
                <option value="parent">Parent</option>
                <option value="admin">Admin</option>
            </select>
        </td>
        <td>
            <select id="add-user-person" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                <option value="">None Linked</option>
                ${allOwners.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`).join("")}
            </select>
        </td>
        <td>
            <button class="btn btn-success" onclick="saveNewUserInline()">Save</button>
            <button class="btn btn-secondary" onclick="document.getElementById('user-add-row').remove()">Cancel</button>
        </td>
    `;
    
    if (position === "top") {
        tableBody.insertBefore(addRow, tableBody.firstChild);
    } else {
        tableBody.appendChild(addRow);
    }
};

window.saveNewUserInline = async function() {
    const username = document.getElementById("add-user-username").value.trim();
    const role = document.getElementById("add-user-role").value;
    const person = document.getElementById("add-user-person").value;
    
    if (!username) {
        alert("Username is required.");
        return;
    }
    
    try {
        const res = await apiFetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, role, person: person || null })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            const errData = await res.json();
            alert(`Failed: ${errData.detail || "Error occurred"}`);
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.editUserInline = function(username) {
    const row = document.getElementById(`user-row-${username}`);
    if (!row) return;
    const user = allUsers.find(u => u.username === username);
    if (!user) return;
    
    row.innerHTML = `
        <td><code>${escapeHtml(user.username)}</code></td>
        <td>
            <select id="edit-user-role-${username}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                <option value="member" ${user.role === 'member' ? 'selected' : ''}>Member</option>
                <option value="parent" ${user.role === 'parent' ? 'selected' : ''}>Parent</option>
                <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option>
            </select>
        </td>
        <td>
            <select id="edit-user-person-${username}" style="padding: 6px; border-radius: 4px; border: 1px solid var(--card-border); font-size: 13px; width: 100%;">
                <option value="">None Linked</option>
                ${allOwners.map(p => `<option value="${escapeHtml(p.id)}" ${p.id === user.person ? 'selected' : ''}>${escapeHtml(p.name)}</option>`).join("")}
            </select>
        </td>
        <td>
            <button class="btn btn-success" onclick="saveUserInline('${escapeJs(username)}')">Save</button>
            <button class="btn btn-secondary" onclick="loadDashboard()">Cancel</button>
        </td>
    `;
};

window.saveUserInline = async function(username) {
    const role = document.getElementById(`edit-user-role-${username}`).value;
    const person = document.getElementById(`edit-user-person-${username}`).value;
    
    try {
        const res = await apiFetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, role, person: person || null })
        });
        if (res.ok) {
            loadDashboard();
        } else {
            const errData = await res.json();
            alert(`Failed: ${errData.detail || "Error occurred"}`);
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};

window.deleteUser = async function(username) {
    if (confirm(`Are you sure you want to delete operator account '${username}'?`)) {
        try {
            const res = await apiFetch(`/api/users/${username}`, { method: "DELETE" });
            if (res.ok) {
                loadDashboard();
            } else {
                const errData = await res.json();
                alert(`Failed to delete user: ${errData.detail || "Error occurred"}`);
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }
};


// ==========================================
// Reorganized View Render Routing Toggles
// ==========================================
window.renderVPNView = function() {
    renderVPNsList(vpnSettings);
};

window.renderFirewallView = function() {
    // Renders custom blocks (mock table showcase)
    const tableBody = document.getElementById("ip-blocks-table-body");
    if (!tableBody) return;
    tableBody.innerHTML = `
        <tr>
            <td><strong>Block TikTok App</strong></td>
            <td>Outbound (LAN)</td>
            <td><code>10.0.10.0/24 -> Tik Tok Subnets</code></td>
            <td><span class="badge badge-online">ACTIVE</span></td>
            <td>
                <button class="btn btn-danger" onclick="alert('Demo enforcer blocks cannot be edited natively.')">Delete</button>
            </td>
        </tr>
    `;
};

window.renderParentalView = function() {
    // Access Schedule rules are already rendered by loadDashboard invoking renderSchedules
};

window.renderDNSView = function() {
    // DNS Config form is populated directly in loadDashboard
};

window.updateVpnProtocolFieldsInline = function() {
    const type = document.getElementById("add-vpn-type").value;
    const container = document.getElementById("add-vpn-protocol-fields");
    const handler = window.RoostOS.getVpnFormHandler(type);
    if (handler) {
        handler.renderConfigFields(container, {});
    } else {
        container.innerHTML = `<p style="font-size: 13px; color: var(--text-secondary);">No configuration fields registered for type: ${type}</p>`;
    }
};

window.addVpnProfileInline = async function(e) {
    e.preventDefault();
    const id = document.getElementById("add-vpn-id").value.trim();
    const name = document.getElementById("add-vpn-name").value.trim();
    const type = document.getElementById("add-vpn-type").value;
    const role = document.getElementById("add-vpn-role").value;
    
    if (vpnSettings.some(v => v.id === id)) {
        alert("A VPN profile with this ID already registered.");
        return;
    }

    const handler = window.RoostOS.getVpnFormHandler(type);
    const config = handler ? handler.serializeConfig() : {};
    
    const newVpn = {
        id, name, type, role, enabled: false, config
    };
    vpnSettings.push(newVpn);
    
    try {
        const res = await apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                network: networkSettings,
                wifi: wifiSettings,
                vpns: vpnSettings
            })
        });
        if (res.ok) {
            alert("VPN tunnel profile added successfully!");
            loadDashboard();
        } else {
            alert("Failed to save VPN profile.");
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
};


window.renderInterfaces = function() {
    const tableBody = document.getElementById("interfaces-table-body");
    if (!tableBody || !networkSettings) return;
    
    const interfaces = networkSettings.interfaces || [];
    if (interfaces.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No interfaces configured.</td></tr>';
        return;
    }
    
    tableBody.innerHTML = interfaces.map(i => `
        <tr id="row-interface-${i.name}">
            <td><strong>${escapeHtml(i.name)}</strong></td>
            <td><span class="badge ${i.role === 'wan' ? 'badge-online' : 'badge-outline'}">${i.role === 'wan' ? 'WAN' : 'LAN'}</span></td>
            <td>${i.dhcp ? 'Enabled' : 'Disabled'}</td>
            <td><code>${escapeHtml(i.bridge || 'None')}</code></td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editInterfaceInline('${escapeJs(i.name)}')">Edit</button>
                <button class="btn btn-secondary btn-sm" style="color: var(--accent-red);" onclick="deleteInterface('${escapeJs(i.name)}')">Delete</button>
            </td>
        </tr>
    `).join("");
};

window.editInterfaceInline = function(name) {
    const rowEl = document.getElementById(`row-interface-${name}`);
    if (!rowEl) return;
    
    const interfaces = networkSettings.interfaces || [];
    const bridges = networkSettings.bridges || [];
    const i = interfaces.find(item => item.name === name);
    if (!i) return;
    
    rowEl.innerHTML = `
        <td colspan="5">
            <form onsubmit="saveInterfaceInline('${escapeJs(name)}', event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap;">
                <div class="form-group" style="margin: 0; flex: 1; min-width: 120px;">
                    <label style="margin: 0; font-size: 11px;">Interface Name</label>
                    <input type="text" name="if_name" value="${escapeHtml(i.name)}" disabled style="padding: 4px 8px; width: 100%;">
                </div>
                <div class="form-group" style="margin: 0; flex: 1; min-width: 100px;">
                    <label style="margin: 0; font-size: 11px;">Role</label>
                    <select name="if_role" class="theme-select" style="padding: 4px 8px; width: 100%;" onchange="toggleInterfaceBridgeSelect(this)">
                        <option value="wan" ${i.role === 'wan' ? 'selected' : ''}>WAN</option>
                        <option value="lan" ${i.role === 'lan' ? 'selected' : ''}>LAN</option>
                    </select>
                </div>
                <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                    <input type="checkbox" name="if_dhcp" ${i.dhcp ? 'checked' : ''}>
                    <label style="margin: 0; font-size: 11px;">DHCP Client</label>
                </div>
                <div class="form-group" id="if-bridge-group" style="margin: 0; flex: 1; min-width: 120px; display: ${i.role === 'wan' ? 'none' : 'block'};">
                    <label style="margin: 0; font-size: 11px;">Bridge Binding</label>
                    <select name="if_bridge" class="theme-select" style="padding: 4px 8px; width: 100%;">
                        <option value="">None</option>
                        ${bridges.map(br => `<option value="${br.name}" ${i.bridge === br.name ? 'selected' : ''}>${br.name}</option>`).join("")}
                    </select>
                </div>
                <div style="display: flex; gap: 8px; margin-top: 14px;">
                    <button type="submit" class="btn btn-primary btn-sm">Save</button>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="renderInterfaces()">Cancel</button>
                </div>
            </form>
        </td>
    `;
};

window.saveInterfaceInline = async function(name, event) {
    event.preventDefault();
    const form = event.target;
    const role = form.if_role.value;
    const dhcp = form.if_dhcp.checked;
    const bridge = role === 'wan' ? null : (form.if_bridge.value || null);
    
    const i = networkSettings.interfaces.find(item => item.name === name);
    if (i) {
        i.role = role;
        i.dhcp = dhcp;
        i.bridge = bridge;
    }
    
    await sendNetworkConfigUpdate(networkSettings.interfaces, networkSettings.bridges, networkSettings.vlans);
    renderInterfaces();
    renderNetworks();
};

window.showAddInterfaceForm = function() {
    const tableBody = document.getElementById("interfaces-table-body");
    if (!tableBody) return;
    
    const existing = document.getElementById("interface-add-row");
    if (existing) existing.remove();
    
    const bridges = networkSettings.bridges || [];
    
    const addRow = document.createElement("tr");
    addRow.id = "interface-add-row";
    addRow.innerHTML = `
        <td colspan="5">
            <form onsubmit="saveNewInterface(event)" class="inline-edit-form" style="display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap;">
                <div class="form-group" style="margin: 0; flex: 1; min-width: 120px;">
                    <label style="margin: 0; font-size: 11px;">Interface Name</label>
                    <input type="text" name="if_name" required placeholder="e.g. eth3" style="padding: 4px 8px; width: 100%;">
                </div>
                <div class="form-group" style="margin: 0; flex: 1; min-width: 100px;">
                    <label style="margin: 0; font-size: 11px;">Role</label>
                    <select name="if_role" class="theme-select" style="padding: 4px 8px; width: 100%;" onchange="toggleInterfaceBridgeSelect(this)">
                        <option value="lan">LAN</option>
                        <option value="wan">WAN</option>
                    </select>
                </div>
                <div class="form-group" style="margin: 0; display: flex; align-items: center; gap: 6px; margin-top: 14px;">
                    <input type="checkbox" name="if_dhcp">
                    <label style="margin: 0; font-size: 11px;">DHCP Client</label>
                </div>
                <div class="form-group" id="if-bridge-group-new" style="margin: 0; flex: 1; min-width: 120px;">
                    <label style="margin: 0; font-size: 11px;">Bridge Binding</label>
                    <select name="if_bridge" class="theme-select" style="padding: 4px 8px; width: 100%;">
                        <option value="">None</option>
                        ${bridges.map(br => `<option value="${br.name}">${br.name}</option>`).join("")}
                    </select>
                </div>
                <div style="display: flex; gap: 8px; margin-top: 14px;">
                    <button type="submit" class="btn btn-primary btn-sm">Add</button>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('tr').remove()">Cancel</button>
                </div>
            </form>
        </td>
    `;
    
    tableBody.insertBefore(addRow, tableBody.firstChild);
};

window.saveNewInterface = async function(event) {
    event.preventDefault();
    const form = event.target;
    const name = form.if_name.value.trim();
    const role = form.if_role.value;
    const dhcp = form.if_dhcp.checked;
    const bridge = role === 'wan' ? null : (form.if_bridge.value || null);
    
    if (!networkSettings.interfaces) {
        networkSettings.interfaces = [];
    }
    
    if (networkSettings.interfaces.some(i => i.name === name)) {
        alert(`Interface with name "${name}" already exists.`);
        return;
    }
    
    networkSettings.interfaces.push({
        name: name,
        role: role,
        dhcp: dhcp,
        bridge: bridge
    });
    
    await sendNetworkConfigUpdate(networkSettings.interfaces, networkSettings.bridges, networkSettings.vlans);
    renderInterfaces();
    renderNetworks();
};

window.deleteInterface = async function(name) {
    if (!confirm(`Are you sure you want to delete interface ${name}?`)) return;
    networkSettings.interfaces = (networkSettings.interfaces || []).filter(i => i.name !== name);
    await sendNetworkConfigUpdate(networkSettings.interfaces, networkSettings.bridges, networkSettings.vlans);
    renderInterfaces();
    renderNetworks();
};

window.toggleInterfaceBridgeSelect = function(select) {
    const form = select.closest("form");
    const bridgeGroup = form.querySelector("#if-bridge-group") || form.querySelector("#if-bridge-group-new");
    if (bridgeGroup) {
        bridgeGroup.style.display = select.value === 'wan' ? 'none' : 'block';
    }
};

window.formatSpeed = function(bytesPerSec) {
    if (bytesPerSec === undefined || bytesPerSec === null || isNaN(bytesPerSec)) return "0 B/s";
    if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`;
    if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
    return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`;
};

window.drawCharts = function() {
    const trafficCanvas = document.getElementById("traffic-chart");
    const resourcesCanvas = document.getElementById("resources-chart");
    if (!trafficCanvas || !resourcesCanvas) return;

    if (metricsHistory.length === 0) return;

    const setupCanvas = (canvas) => {
        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        const ctx = canvas.getContext('2d');
        ctx.resetTransform();
        ctx.scale(dpr, dpr);
        return { ctx, width: rect.width, height: rect.height };
    };

    const drawGrid = (ctx, w, h, maxValStr) => {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);

        // Draw horizontal gridlines
        const lines = 4;
        for (let i = 0; i <= lines; i++) {
            const y = (i / lines) * (h - 20) + 10;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }
        ctx.setLineDash([]);

        // Label max Y value at the top left
        if (maxValStr) {
            ctx.fillStyle = "var(--text-secondary)";
            ctx.font = "9px monospace";
            ctx.fillText(maxValStr, 4, 15);
        }
    };

    // 1. Draw Traffic Chart
    const t = setupCanvas(trafficCanvas);
    const maxTraffic = Math.max(...metricsHistory.map(d => Math.max(d.rx, d.tx, 1024)));
    drawGrid(t.ctx, t.width, t.height, formatSpeed(maxTraffic));

    const drawPath = (ctx, w, h, dataKey, strokeStyle, fillGradientColor) => {
        ctx.beginPath();
        const points = metricsHistory.map((d, index) => {
            const x = (index / (MAX_HISTORY_POINTS - 1)) * w;
            const y = h - ((d[dataKey] / maxTraffic) * (h - 20)) - 10;
            return { x, y };
        });

        if (points.length === 0) return;

        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.strokeStyle = strokeStyle;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Fill area
        ctx.lineTo(points[points.length - 1].x, h);
        ctx.lineTo(points[0].x, h);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, fillGradientColor);
        grad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = grad;
        ctx.fill();
    };

    // Draw RX (Inbound) - Green
    drawPath(t.ctx, t.width, t.height, "rx", "#10b981", "rgba(16, 185, 129, 0.15)");
    // Draw TX (Outbound) - Blue
    drawPath(t.ctx, t.width, t.height, "tx", "#3b82f6", "rgba(59, 130, 246, 0.15)");

    // 2. Draw Resources Chart (CPU & RAM)
    const r = setupCanvas(resourcesCanvas);
    drawGrid(r.ctx, r.width, r.height, "100%");

    const drawResourcePath = (ctx, w, h, dataKey, strokeStyle) => {
        ctx.beginPath();
        const points = metricsHistory.map((d, index) => {
            const x = (index / (MAX_HISTORY_POINTS - 1)) * w;
            const y = h - ((d[dataKey] / 100) * (h - 20)) - 10;
            return { x, y };
        });

        if (points.length === 0) return;

        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.strokeStyle = strokeStyle;
        ctx.lineWidth = 2;
        ctx.stroke();
    };

    // Draw CPU - Purple
    drawResourcePath(r.ctx, r.width, r.height, "cpu", "#a855f7");
    // Draw RAM - Orange
    drawResourcePath(r.ctx, r.width, r.height, "ram", "#f97316");

    // Draw simple legends inside resources canvas
    r.ctx.font = "9px system-ui";
    r.ctx.fillStyle = "#a855f7";
    r.ctx.fillText("CPU", r.width - 65, 15);
    r.ctx.fillStyle = "#f97316";
    r.ctx.fillText("RAM", r.width - 35, 15);
};


async function loadUserProfile() {
    try {
        const res = await apiFetch("/api/auth/me");
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


window.runSystemHealthCheck = async function() {
    const btn = document.getElementById("run-health-btn");
    const resultsDiv = document.getElementById("health-results");
    if (!btn || !resultsDiv) return;

    btn.disabled = true;
    btn.textContent = "Running diagnostics...";
    resultsDiv.style.display = "block";
    resultsDiv.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--text-secondary);">Testing system interfaces and configurations...</div>`;

    try {
        const res = await apiFetch("/api/system/health");
        if (res.ok) {
            const data = await res.json();
            
            let html = "";
            
            const statusClass = data.status === "PASS" ? "badge-online" : "badge-danger";
            const statusText = data.status === "PASS" ? "SYSTEM HEALTHY" : "ISSUES DETECTED";
            
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 6px; margin-bottom: 16px;">
                    <span style="font-weight: 600; font-size: 14px;">Overall Health Status</span>
                    <span class="badge ${statusClass}" style="padding: 4px 12px; font-size: 12px;">${statusText}</span>
                </div>
            `;
            
            data.checks.forEach(c => {
                const checkStatusClass = c.status === "PASS" ? "color: #10b981;" : "color: #ef4444;";
                const checkIcon = c.status === "PASS" ? "✓" : "✗";
                
                html += `
                    <div style="padding: 12px; border: 1px solid var(--border-color); border-radius: 6px; margin-bottom: 8px; background: var(--bg-card);">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <strong style="font-size: 13px; color: var(--text-primary);">${escapeHtml(c.name)}</strong>
                            <span style="font-weight: bold; font-size: 13px; ${checkStatusClass}">${checkIcon} ${escapeHtml(c.status)}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.4;">${escapeHtml(c.message)}</div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
        } else {
            resultsDiv.innerHTML = `<div style="color: var(--accent-red); padding: 10px;">Failed to run health check. Server responded with error.</div>`;
        }
    } catch (err) {
        resultsDiv.innerHTML = `<div style="color: var(--accent-red); padding: 10px;">Error running diagnostics: ${escapeHtml(err.message)}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Run Diagnostics";
    }
};


// Initialization
function init() {
    loadSavedTheme();
    initSidebarCollapse();
    setupEventListeners();
    loadUserProfile();
    loadDashboard();
    
    // Start periodic status refresh (every 5 seconds)
    setInterval(() => {
        // Skip periodic auto-refresh if the user is currently editing or has open inline forms
        const active = document.activeElement;
        const isFocused = active && (active.tagName === 'INPUT' || active.tagName === 'SELECT' || active.tagName === 'TEXTAREA');
        const hasOpenForms = document.querySelector('table tbody input, table tbody select, .editing-row, .inline-form');
        if (isFocused || hasOpenForms) {
            return;
        }
        loadDashboard();
    }, 5000);
}

// Entrypoint
document.addEventListener("DOMContentLoaded", () => {
    if (handleAuthentication()) {
        init();
    }
});
