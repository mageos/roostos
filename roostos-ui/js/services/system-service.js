class SystemService {
    async fetchSystemSettings() {
        const res = await window.authService.apiFetch("/api/v1/system");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch system settings");
    }

    async saveSystemSettings(settings) {
        const res = await window.authService.apiFetch("/api/v1/system", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        });
        return res;
    }

    async fetchHealth() {
        const res = await window.authService.apiFetch("/api/v1/system/health");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch system health status");
    }

    async triggerBackup(passphrase) {
        const res = await window.authService.apiFetch("/api/v1/backups", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ passphrase })
        });
        return res;
    }

    async fetchPlugins() {
        const res = await window.authService.apiFetch("/api/v1/plugins");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch plugins");
    }

    async savePlugin(plugin) {
        const res = await window.authService.apiFetch("/api/v1/plugins", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(plugin)
        });
        return res;
    }

    async deletePlugin(id) {
        const res = await window.authService.apiFetch(`/api/v1/plugins/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async uploadPlugin(formData) {
        const res = await window.authService.apiFetch("/api/v1/plugins/upload", {
            method: "POST",
            body: formData // Note: no Content-Type header so the browser sets multipart/form-data boundary
        });
        return res;
    }

    async updatePluginManifest(id, manifestJson) {
        const res = await window.authService.apiFetch("/api/v1/plugins/manifest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, manifest: manifestJson })
        });
        return res;
    }

    // Additional generic endpoints for rooms, buildings, people
    async fetchPeople() {
        const res = await window.authService.apiFetch("/api/v1/people");
        if (res.ok) {
            window.allOwners = await res.json();
            return window.allOwners;
        }
        throw new Error("Failed to fetch people list");
    }

    async savePerson(person) {
        const res = await window.authService.apiFetch("/api/v1/people", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(person)
        });
        return res;
    }

    async deletePerson(id) {
        const res = await window.authService.apiFetch(`/api/v1/people/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchBuildings() {
        const res = await window.authService.apiFetch("/api/v1/buildings");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch buildings list");
    }

    async saveBuilding(building) {
        const res = await window.authService.apiFetch("/api/v1/buildings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(building)
        });
        return res;
    }

    async deleteBuilding(id) {
        const res = await window.authService.apiFetch(`/api/v1/buildings/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchRooms() {
        const res = await window.authService.apiFetch("/api/v1/rooms");
        if (res.ok) {
            window.allLocations = await res.json();
            return window.allLocations;
        }
        throw new Error("Failed to fetch rooms list");
    }

    async saveRoom(room) {
        const res = await window.authService.apiFetch("/api/v1/rooms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(room)
        });
        return res;
    }

    async deleteRoom(id) {
        const res = await window.authService.apiFetch(`/api/v1/rooms/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchServicesStatus() {
        const res = await window.authService.apiFetch("/api/v1/system/services");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch system services status");
    }

    async fetchLogs(service, limit) {
        const res = await window.authService.apiFetch(`/api/v1/diagnostics/logs?service=${encodeURIComponent(service)}&limit=${limit}`);
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch logs");
    }

    async fetchUpdatesStatus() {
        const res = await window.authService.apiFetch("/api/v1/system/updates/status");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch updates status");
    }

    async checkUpdates() {
        const res = await window.authService.apiFetch("/api/v1/system/updates/check", { method: "POST" });
        if (res.ok) return await res.json();
        throw new Error("Failed to check for updates");
    }

    async installUpdates(securityOnly = false) {
        const res = await window.authService.apiFetch(`/api/v1/system/updates/install?security_only=${securityOnly}`, { method: "POST" });
        if (res.ok) return await res.json();
        throw new Error("Failed to install updates");
    }

    async fetchUpdatesConfig() {
        const res = await window.authService.apiFetch("/api/v1/system/updates/config");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch updates config");
    }

    async saveUpdatesConfig(config) {
        const res = await window.authService.apiFetch("/api/v1/system/updates/config", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        });
        if (res.ok) return await res.json();
        throw new Error("Failed to save updates config");
    }

    async fetchDependencies() {
        const res = await window.authService.apiFetch("/api/v1/system/dependencies");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch system dependencies");
    }

    async installDependencies(feature = null, packages = null) {
        const res = await window.authService.apiFetch("/api/v1/system/dependencies/install", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ feature, packages })
        });
        if (res.ok) return await res.json();
        const err = await res.json().catch(() => ({ detail: "Installation failed" }));
        throw new Error(err.detail || "Failed to install dependencies");
    }
}

window.systemService = new SystemService();
