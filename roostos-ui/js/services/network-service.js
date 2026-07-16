class NetworkService {
    async fetchConfig() {
        const res = await window.authService.apiFetch("/api/network");
        if (res.ok) {
            const data = await res.json();
            window.networkSettings = data.network || {};
            window.wifiSettings = data.wifi || {};
            window.vpnSettings = data.vpns || [];
            return data;
        }
        throw new Error("Failed to load network settings");
    }

    async saveConfig(network, wifi, vpns) {
        const res = await window.authService.apiFetch("/api/network", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ network, wifi, vpns })
        });
        return res;
    }

    async sendNetworkConfigUpdate(interfaces, bridges, vlans) {
        try {
            const updatedNetwork = {
                ...window.networkSettings,
                interfaces,
                bridges,
                vlans
            };
            
            const res = await this.saveConfig(updatedNetwork, window.wifiSettings, window.vpnSettings);
            if (res.ok) {
                alert("Network configuration saved successfully!");
                if (window.loadDashboard) window.loadDashboard();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail || 'Failed to save network configuration'}`);
            }
        } catch (e) {
            console.error(e);
            alert("Failed to propagate network configuration.");
        }
    }
}

window.networkService = new NetworkService();

// Backward compatibility bindings
window.sendNetworkConfigUpdate = (i, b, v) => window.networkService.sendNetworkConfigUpdate(i, b, v);
