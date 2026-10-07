/**
 * ClusterService - Client-side service for multi-node cluster management & fleet updates.
 */

class ClusterService {
    async fetchClusterStatus() {
        const res = await window.authService.apiFetch("/api/cluster/status");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch cluster status");
    }

    async fetchNodes() {
        const res = await window.authService.apiFetch("/api/cluster/nodes");
        if (res.ok) {
            const data = await res.json();
            return data.nodes || [];
        }
        throw new Error("Failed to fetch cluster nodes");
    }

    async saveNode(nodeData) {
        const res = await window.authService.apiFetch("/api/cluster/nodes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(nodeData)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to save cluster node");
        }
        return await res.json();
    }

    async removeNode(nodeId) {
        const res = await window.authService.apiFetch(`/api/cluster/nodes/${encodeURIComponent(nodeId)}`, {
            method: "DELETE"
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to remove cluster node");
        }
        return await res.json();
    }

    async generateJoinToken() {
        const res = await window.authService.apiFetch("/api/cluster/token", {
            method: "POST"
        });
        if (res.ok) return await res.json();
        throw new Error("Failed to generate join token");
    }

    async discoverControllers() {
        const res = await window.authService.apiFetch("/api/cluster/discover", {
            method: "POST"
        });
        if (res.ok) {
            const data = await res.json();
            return data.controllers || [];
        }
        throw new Error("Failed to discover cluster controllers");
    }

    async fetchDetectedHardware() {
        const res = await window.authService.apiFetch("/api/cluster/hardware");
        if (res.ok) {
            const data = await res.json();
            return data.hardware || [];
        }
        throw new Error("Failed to fetch detected hardware");
    }

    async fetchClusterUpdates() {
        const res = await window.authService.apiFetch("/api/cluster/updates");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch cluster updates");
    }

    async triggerNodeUpdate(nodeId, securityOnly = false) {
        const url = `/api/cluster/nodes/${encodeURIComponent(nodeId)}/updates/install?security_only=${securityOnly}`;
        const res = await window.authService.apiFetch(url, { method: "POST" });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Failed to trigger update for node ${nodeId}`);
        }
        return await res.json();
    }

    async fetchNodeHeartbeat(nodeId) {
        const res = await window.authService.apiFetch(`/api/cluster/nodes/${encodeURIComponent(nodeId)}/heartbeat`);
        if (res.ok) return await res.json();
        throw new Error(`Failed to fetch heartbeat for node ${nodeId}`);
    }

    async fetchManifest() {
        const res = await window.authService.apiFetch("/api/cluster/sync/manifest");
        if (res.ok) return await res.json();
        throw new Error("Failed to fetch cluster state manifest");
    }

    async promoteNode(nodeId, newEpoch = null, force = false) {
        const res = await window.authService.apiFetch("/api/cluster/promote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: nodeId, new_epoch: newEpoch, force: force })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Failed to promote node ${nodeId}`);
        }
        return await res.json();
    }

    async demoteNode(nodeId) {
        const res = await window.authService.apiFetch("/api/cluster/demote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: nodeId })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Failed to demote node ${nodeId}`);
        }
        return await res.json();
    }
}

if (typeof window !== "undefined") {
    window.ClusterService = ClusterService;
    window.clusterService = new ClusterService();
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { ClusterService };
}
