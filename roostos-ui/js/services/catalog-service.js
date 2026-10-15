/**
 * CatalogService - Service for interacting with RoostOS Catalog & Image APIs
 */

class CatalogService {
    async fetchSources() {
        const res = await window.authService.apiFetch("/api/v1/catalog/sources");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch catalog sources");
    }

    async saveSource(source) {
        const res = await window.authService.apiFetch("/api/v1/catalog/sources", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(source)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to save catalog source");
        }
        return await res.json();
    }

    async deleteSource(sourceId) {
        const res = await window.authService.apiFetch(`/api/v1/catalog/sources/${sourceId}`, {
            method: "DELETE"
        });
        if (!res.ok) throw new Error("Failed to delete catalog source");
        return await res.json();
    }

    async refreshCatalogs() {
        const res = await window.authService.apiFetch("/api/v1/catalog/refresh", {
            method: "POST"
        });
        if (!res.ok) throw new Error("Failed to refresh catalogs");
        return await res.json();
    }

    async fetchApps(category = "") {
        const url = category && category !== "all"
            ? `/api/v1/catalog/apps?category=${encodeURIComponent(category)}`
            : "/api/v1/catalog/apps";
        const res = await window.authService.apiFetch(url);
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch catalog apps");
    }

    async installApp(payload) {
        const res = await window.authService.apiFetch("/api/v1/catalog/apps/install", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to install application");
        }
        return await res.json();
    }

    async fetchImages() {
        const res = await window.authService.apiFetch("/api/v1/catalog/images");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch local images");
    }

    async uploadImage(file) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await window.authService.apiFetch("/api/v1/catalog/images/load", {
            method: "POST",
            body: formData
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to upload image archive");
        }
        return await res.json();
    }

    async inspectManifest(sourceUrlOrPath, gitRef = "main") {
        const res = await window.authService.apiFetch("/api/v1/catalog/manifest/inspect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source_url_or_path: sourceUrlOrPath, git_ref: gitRef })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to inspect package manifest");
        }
        return await res.json();
    }

    async buildAndInstallFromSource(payload) {
        const res = await window.authService.apiFetch("/api/v1/catalog/build-and-install", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to build and install application from source");
        }
        return await res.json();
    }

    async importAppFromSource(payload) {
        const res = await window.authService.apiFetch("/api/v1/catalog/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to import application into catalog");
        }
        return await res.json();
    }

    async checkAppUpdate(appId) {
        const res = await window.authService.apiFetch(`/api/v1/catalog/apps/${encodeURIComponent(appId)}/check-update`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to check application updates");
        }
        return await res.json();
    }

    async updateImportedApp(appId, payload = {}) {
        const res = await window.authService.apiFetch(`/api/v1/catalog/apps/${encodeURIComponent(appId)}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to update application");
        }
        return await res.json();
    }

    async deleteLocalApp(appId) {
        const res = await window.authService.apiFetch(`/api/v1/catalog/apps/${encodeURIComponent(appId)}/local`, {
            method: "DELETE"
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to remove local application");
        }
        return true;
    }
}

window.catalogService = new CatalogService();
