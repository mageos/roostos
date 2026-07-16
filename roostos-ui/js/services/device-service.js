class DeviceService {
    async fetchDevices() {
        const res = await window.authService.apiFetch("/api/devices");
        if (res.ok) {
            const data = await res.json();
            window.allDevices = data.devices || [];
            window.activeLeases = data.active_leases || [];
            window.activeArp = data.active_arp || [];
            return data;
        }
        throw new Error("Failed to fetch devices");
    }

    async saveDevice(payload) {
        const res = await window.authService.apiFetch("/api/devices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        return res;
    }

    async deleteDevice(mac) {
        const res = await window.authService.apiFetch(`/api/devices/${mac}`, {
            method: "DELETE"
        });
        return res;
    }
}

window.deviceService = new DeviceService();
