/**
 * CatalogService - Service for interacting with RoostOS Catalog & Image APIs
 */

class CatalogService {
    async fetchSources() {
        const res = await window.authService.apiFetch("/api/catalog/sources");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch catalog sources");
    }

    async saveSource(source) {
        const res = await window.authService.apiFetch("/api/catalog/sources", {
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
        const res = await window.authService.apiFetch(`/api/catalog/sources/${sourceId}`, {
            method: "DELETE"
        });
        if (!res.ok) throw new Error("Failed to delete catalog source");
        return await res.json();
    }

    async refreshCatalogs() {
        const res = await window.authService.apiFetch("/api/catalog/refresh", {
            method: "POST"
        });
        if (!res.ok) throw new Error("Failed to refresh catalogs");
        return await res.json();
    }

    async fetchApps(category = "") {
        const url = category && category !== "all"
            ? `/api/catalog/apps?category=${encodeURIComponent(category)}`
            : "/api/catalog/apps";
        const res = await window.authService.apiFetch(url);
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch catalog apps");
    }

    async installApp(payload) {
        const res = await window.authService.apiFetch("/api/catalog/apps/install", {
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
        const res = await window.authService.apiFetch("/api/catalog/images");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch local images");
    }

    async uploadImage(file) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await window.authService.apiFetch("/api/catalog/images/load", {
            method: "POST",
            body: formData
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to upload image archive");
        }
        return await res.json();
    }
}

window.catalogService = new CatalogService();
