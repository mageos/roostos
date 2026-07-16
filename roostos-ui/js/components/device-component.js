const DEVICE_TEMPLATE = /* html */ `
    <div id="devices-view" class="view-pane">
        <div class="filter-row">
            <label class="checkbox-container">
                <input type="checkbox" id="filter-online-only" onchange="filterDevices()">
                <span>Show connected online devices only</span>
            </label>
            
            <div style="flex-grow: 1;"></div>
            
            <div class="form-group" style="margin-bottom: 0; min-width: 200px;">
                <select id="filter-location" onchange="filterDevices()">
                    <option value="all">All Locations (Rooms)</option>
                    <!-- Location options generated dynamically -->
                </select>
            </div>
        </div>
        
        <div class="filter-row">
            <span style="font-size: 13px; font-weight: 600; color: var(--text-secondary);">Filter by Tags:</span>
            <div id="tag-filters" class="tag-filter-container">
                <!-- Dynamic tag filter pills go here -->
            </div>
        </div>

        <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
            <button class="btn btn-primary" onclick="showAddDeviceForm('top')">+ Add Device</button>
        </div>
        <div class="device-table-container">
            <table>
                <thead>
                    <tr>
                        <th>Device Name</th>
                        <th>MAC Address</th>
                        <th>IP / Owner</th>
                        <th>Room / Tags</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="device-table-body">
                    <tr>
                        <td colspan="6" class="empty-state">Loading registered client devices registry...</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
            <button class="btn btn-primary" onclick="showAddDeviceForm('bottom')">+ Add Device</button>
        </div>
        
        <div style="margin-top: 40px;">
            <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--text-primary);">Unregistered Connected Devices</h3>
            <div class="device-table-container">
                <table>
                    <thead>
                        <tr>
                            <th>MAC Address</th>
                            <th>Current IP</th>
                            <th>Interface / Hostname</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="unregistered-device-table-body">
                        <tr>
                            <td colspan="4" class="empty-state">No unregistered devices connected.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
`;

class DeviceComponent {
    constructor() {
        this.template = DEVICE_TEMPLATE;
    }

    mount(container) {
        container.insertAdjacentHTML('beforeend', this.template);
        this.registerGlobals();
    }

    registerGlobals() {
        window.renderDevicesList = () => this.renderDevicesList();
        window.filterDevices = () => this.renderDevicesList();
        window.populateFilters = (d) => this.populateFilters(d);
        window.toggleTagFilter = (t) => this.toggleTagFilter(t);
        window.closeInlineForm = () => this.closeInlineForm();
        window.saveInlineDevice = (e) => this.saveInlineDevice(e);
        window.showAddDeviceForm = (pos) => this.showAddDeviceForm(pos);
        window.editDevice = (mac, name, owner, location, tags, upnp, staticIp, maxUpload, maxDownload) => 
            this.editDevice(mac, name, owner, location, tags, upnp, staticIp, maxUpload, maxDownload);
        window.deleteDevice = (mac) => this.deleteDevice(mac);
        window.registerUnrecognizedDevice = (mac, ip, hostname) => this.registerUnrecognizedDevice(mac, ip, hostname);
    }

    render(devicesData) {
        this.populateFilters(window.allDevices);
        this.renderDevicesList();
    }

    populateFilters(devices) {
        const tags = new Set();
        devices.forEach(d => (d.tags || []).forEach(t => tags.add(t)));
        
        const tagContainer = document.getElementById("tag-filters");
        if (tagContainer) {
            const currentSelected = new Set(selectedTags);
            tagContainer.innerHTML = Array.from(tags).map(tag => {
                const isSelected = currentSelected.has(tag);
                return `<span class="tag-badge ${isSelected ? 'selected' : ''}" onclick="toggleTagFilter('${escapeJs(tag)}')">${escapeHtml(tag)}</span>`;
            }).join("");
        }

        const locations = new Set();
        devices.forEach(d => { if (d.location) locations.add(d.location); });
        
        const locationSelect = document.getElementById("filter-location");
        if (locationSelect) {
            const currentLoc = locationSelect.value;
            locationSelect.innerHTML = '<option value="all">All Locations (Rooms)</option>' + 
                Array.from(locations).map(loc => `<option value="${escapeHtml(loc)}">${escapeHtml(loc)}</option>`).join("");
            
            if (Array.from(locations).includes(currentLoc)) {
                locationSelect.value = currentLoc;
            }
        }
    }

    toggleTagFilter(tag) {
        if (selectedTags.has(tag)) {
            selectedTags.delete(tag);
        } else {
            selectedTags.add(tag);
        }
        if (window.loadDashboard) window.loadDashboard();
    }

    renderDevicesList() {
        const tableBody = document.getElementById("device-table-body");
        if (!tableBody) return;
        const onlineOnlyEl = document.getElementById("filter-online-only");
        const locationFilterEl = document.getElementById("filter-location");
        const onlineOnly = onlineOnlyEl ? onlineOnlyEl.checked : false;
        const locationFilter = locationFilterEl ? locationFilterEl.value : "all";

        const filtered = window.allDevices.filter(dev => {
            const isOnline = window.activeLeases.some(l => l.mac.toLowerCase() === dev.mac.toLowerCase());
            if (onlineOnly && !isOnline) return false;
            if (locationFilter !== "all" && dev.location !== locationFilter) return false;
            
            if (selectedTags.size > 0) {
                const devTags = dev.tags || [];
                if (!Array.from(selectedTags).some(t => devTags.includes(t))) return false;
            }
            return true;
        });

        if (filtered.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" class="empty-state">No matching registered devices found.</td></tr>';
        } else {
            tableBody.innerHTML = filtered.map(dev => {
                const isOnline = window.activeLeases.some(l => l.mac.toLowerCase() === dev.mac.toLowerCase());
                const tagsHtml = (dev.tags || []).map(t => `<span class="badge badge-offline" style="margin-right: 4px;">${escapeHtml(t)}</span>`).join("");
                
                return `
                    <tr>
                        <td><strong>${escapeHtml(dev.name)}</strong></td>
                        <td><code>${escapeHtml(dev.mac.toUpperCase())}</code></td>
                        <td>${escapeHtml(dev.static_ip || "DHCP")} <br><span style="font-size: 11px; color: var(--text-secondary);">Owner: ${escapeHtml(dev.owner || "None")}</span>${(dev.max_download_kbps || dev.max_upload_kbps) ? `<br><span style="font-size: 11px; color: var(--accent-blue); font-weight: 500;">Limits: ↓${dev.max_download_kbps || '∞'} kbps | ↑${dev.max_upload_kbps || '∞'} kbps</span>` : ''}</td>
                        <td>${escapeHtml(dev.location || "-")} <br> ${tagsHtml}</td>
                        <td><span class="badge ${isOnline ? 'badge-online' : 'badge-offline'}">${isOnline ? 'ONLINE' : 'OFFLINE'}</span></td>
                        <td>
                            <button class="btn btn-secondary" onclick="editDevice('${dev.mac}', '${escapeJs(dev.name)}', '${escapeJs(dev.owner || "")}', '${escapeJs(dev.location || "")}', '${escapeJs((dev.tags || []).join(","))}', ${dev.upnp_trusted || false}, '${escapeJs(dev.static_ip || "")}', ${dev.max_upload_kbps || 'null'}, ${dev.max_download_kbps || 'null'})">Edit</button>
                            <button class="btn btn-danger" onclick="deleteDevice('${dev.mac}')">Delete</button>
                        </td>
                    </tr>
                `;
            }).join("");
        }

        // Render Unregistered Devices list
        const registeredMacs = new Set(window.allDevices.map(d => d.mac.toLowerCase()));
        const seenMacs = new Set();
        const unregistered = [];

        // 1. Add active ARP devices
        (window.activeArp || []).forEach(d => {
            const mac = d.mac.toLowerCase();
            if (!registeredMacs.has(mac) && !seenMacs.has(mac)) {
                seenMacs.add(mac);
                unregistered.push({
                    mac: d.mac,
                    ip: d.ip,
                    hostname: "Active IP client",
                    interface: d.interface
                });
            }
        });

        // 2. Add active DHCP leases
        (window.activeLeases || []).forEach(l => {
            const mac = l.mac.toLowerCase();
            if (!registeredMacs.has(mac) && !seenMacs.has(mac)) {
                seenMacs.add(mac);
                unregistered.push({
                    mac: l.mac,
                    ip: l.ip,
                    hostname: l.hostname || "Unknown",
                    interface: "-"
                });
            }
        });

        const unregTableBody = document.getElementById("unregistered-device-table-body");
        if (unregTableBody) {
            if (unregistered.length === 0) {
                unregTableBody.innerHTML = '<tr><td colspan="4" class="empty-state">No unregistered devices connected.</td></tr>';
            } else {
                unregTableBody.innerHTML = unregistered.map(dev => `
                    <tr>
                        <td><code>${escapeHtml(dev.mac.toUpperCase())}</code></td>
                        <td>${escapeHtml(dev.ip)}</td>
                        <td>${escapeHtml(dev.hostname)} ${dev.interface !== "-" ? `<br><span style="font-size: 11px; color: var(--text-secondary);">Interface: ${escapeHtml(dev.interface)}</span>` : ""}</td>
                        <td>
                            <button class="btn btn-primary" onclick="registerUnrecognizedDevice('${dev.mac}', '${dev.ip}', '${escapeJs(dev.hostname)}')">Register</button>
                        </td>
                    </tr>
                `).join("");
            }
        }
    }

    closeInlineForm() {
        const existing = document.getElementById("inline-edit-row");
        if (existing) {
            existing.remove();
        }
    }

    async saveInlineDevice(e) {
        e.preventDefault();
        const mac = document.getElementById("dev-mac").value.trim();
        const name = document.getElementById("dev-name").value.trim();
        const owner = document.getElementById("dev-owner").value.trim();
        const location = document.getElementById("dev-location").value.trim();
        const static_ip = document.getElementById("dev-static-ip").value.trim();
        const tags = document.getElementById("dev-tags").value.split(",").map(t => t.trim()).filter(t => t.length > 0);
        const upnp_trusted = document.getElementById("dev-upnp").checked;
        
        const maxUploadVal = document.getElementById("dev-max-upload").value;
        const maxDownloadVal = document.getElementById("dev-max-download").value;
        const max_upload_kbps = maxUploadVal ? parseInt(maxUploadVal, 10) : null;
        const max_download_kbps = maxDownloadVal ? parseInt(maxDownloadVal, 10) : null;

        try {
            const res = await window.deviceService.saveDevice({
                mac, name, owner, location, tags, static_ip, upnp_trusted, max_upload_kbps, max_download_kbps
            });
            if (res.ok) {
                this.closeInlineForm();
                if (window.loadDashboard) window.loadDashboard();
            } else {
                alert("Failed to save device. Verify MAC format and reference integrity.");
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    showAddDeviceForm(position) {
        this.closeInlineForm();

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
                    <div class="form-row-multi">
                        <div class="form-group" style="flex: 1;">
                            <label>Max Download Limit (kbps)</label>
                            <input type="number" id="dev-max-download" placeholder="Unlimited">
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label>Max Upload Limit (kbps)</label>
                            <input type="number" id="dev-max-upload" placeholder="Unlimited">
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
    }

    editDevice(mac, name, owner, location, tags, upnp, staticIp, maxUpload, maxDownload) {
        this.closeInlineForm();

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
                    <div class="form-row-multi">
                        <div class="form-group" style="flex: 1;">
                            <label>Max Download Limit (kbps)</label>
                            <input type="number" id="dev-max-download" value="${maxDownload !== null && maxDownload !== undefined ? maxDownload : ''}" placeholder="Unlimited">
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label>Max Upload Limit (kbps)</label>
                            <input type="number" id="dev-max-upload" value="${maxUpload !== null && maxUpload !== undefined ? maxUpload : ''}" placeholder="Unlimited">
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
    }

    async deleteDevice(mac) {
        if (confirm(`Are you sure you want to delete profile for MAC ${mac}?`)) {
            try {
                const res = await window.deviceService.deleteDevice(mac);
                if (res.ok) {
                    if (window.loadDashboard) window.loadDashboard();
                } else {
                    alert("Failed to delete device.");
                }
            } catch (err) {
                alert(`Error: ${err.message}`);
            }
        }
    }

    registerUnrecognizedDevice(mac, ip, hostname) {
        this.showAddDeviceForm('top');
        const macInput = document.getElementById("dev-mac");
        const nameInput = document.getElementById("dev-name");
        const ipInput = document.getElementById("dev-static-ip");
        
        if (macInput) {
            macInput.value = mac;
            macInput.readOnly = true;
            macInput.style.opacity = "0.7";
        }
        if (nameInput) {
            nameInput.value = hostname && hostname !== "Unknown" && hostname !== "Active IP client" ? hostname : `New Device (${mac.substring(12, 17)})`;
        }
        if (ipInput) {
            ipInput.value = ip;
        }
        const inlineRow = document.getElementById("inline-edit-row");
        if (inlineRow) {
            inlineRow.scrollIntoView({ behavior: "smooth" });
        }
    }
}

window.deviceComponent = new DeviceComponent();
