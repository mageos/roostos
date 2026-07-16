class SystemService {
    async fetchSystemSettings() {
        const res = await window.authService.apiFetch("/api/system");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch system settings");
    }

    async saveSystemSettings(settings) {
        const res = await window.authService.apiFetch("/api/system", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        });
        return res;
    }

    async fetchHealth() {
        const res = await window.authService.apiFetch("/api/system/health");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch system health status");
    }

    async triggerBackup(passphrase) {
        const res = await window.authService.apiFetch("/api/backups", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ passphrase })
        });
        return res;
    }

    async fetchPlugins() {
        const res = await window.authService.apiFetch("/api/plugins");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch plugins");
    }

    async savePlugin(plugin) {
        const res = await window.authService.apiFetch("/api/plugins", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(plugin)
        });
        return res;
    }

    async deletePlugin(id) {
        const res = await window.authService.apiFetch(`/api/plugins/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async uploadPlugin(formData) {
        const res = await window.authService.apiFetch("/api/plugins/upload", {
            method: "POST",
            body: formData // Note: no Content-Type header so the browser sets multipart/form-data boundary
        });
        return res;
    }

    async updatePluginManifest(id, manifestJson) {
        const res = await window.authService.apiFetch("/api/plugins/manifest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, manifest: manifestJson })
        });
        return res;
    }

    // Additional generic endpoints for rooms, buildings, people
    async fetchPeople() {
        const res = await window.authService.apiFetch("/api/people");
        if (res.ok) {
            window.allOwners = await res.json();
            return window.allOwners;
        }
        throw new Error("Failed to fetch people list");
    }

    async savePerson(person) {
        const res = await window.authService.apiFetch("/api/people", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(person)
        });
        return res;
    }

    async deletePerson(id) {
        const res = await window.authService.apiFetch(`/api/people/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchBuildings() {
        const res = await window.authService.apiFetch("/api/buildings");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch buildings list");
    }

    async saveBuilding(building) {
        const res = await window.authService.apiFetch("/api/buildings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(building)
        });
        return res;
    }

    async deleteBuilding(id) {
        const res = await window.authService.apiFetch(`/api/buildings/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchRooms() {
        const res = await window.authService.apiFetch("/api/rooms");
        if (res.ok) {
            window.allLocations = await res.json();
            return window.allLocations;
        }
        throw new Error("Failed to fetch rooms list");
    }

    async saveRoom(room) {
        const res = await window.authService.apiFetch("/api/rooms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(room)
        });
        return res;
    }

    async deleteRoom(id) {
        const res = await window.authService.apiFetch(`/api/rooms/${id}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchServicesStatus() {
        const res = await window.authService.apiFetch("/api/system/services");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch system services status");
    }

    async fetchLogs(service, limit) {
        const res = await window.authService.apiFetch(`/api/diagnostics/logs?service=${encodeURIComponent(service)}&limit=${limit}`);
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch logs");
    }
}

window.systemService = new SystemService();
