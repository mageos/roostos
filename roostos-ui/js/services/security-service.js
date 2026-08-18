class SecurityService {
    async fetchSchedules() {
        const res = await window.authService.apiFetch("/api/schedules");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch schedules");
    }

    async fetchFirewallRules() {
        const res = await window.authService.apiFetch("/api/firewall/rules");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch firewall rules");
    }

    async saveFirewallRule(rule) {
        const res = await window.authService.apiFetch("/api/firewall/rules", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rule)
        });
        return res;
    }

    async deleteFirewallRule(name) {
        const res = await window.authService.apiFetch(`/api/firewall/rules/${encodeURIComponent(name)}`, {
            method: "DELETE"
        });
        return res;
    }


    async saveSchedule(schedule) {
        const res = await window.authService.apiFetch("/api/schedules", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(schedule)
        });
        return res;
    }

    async deleteSchedule(name) {
        const res = await window.authService.apiFetch(`/api/schedules/${name}`, {
            method: "DELETE"
        });
        return res;
    }

    async triggerBypass(personId, durationMins) {
        const res = await window.authService.apiFetch("/api/schedules/bypass", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ person_id: personId, duration_minutes: durationMins })
        });
        return res;
    }

    async fetchDnsConfig() {
        const res = await window.authService.apiFetch("/api/dns/config");
        if (res.ok) {
            const data = await res.json();
            window.localDnsRecords = data.local_records || [];
            return data;
        }
        throw new Error("Failed to fetch DNS configuration");
    }

    async saveDnsConfig(config) {
        const res = await window.authService.apiFetch("/api/dns/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        });
        return res;
    }

    async fetchUsers() {
        const res = await window.authService.apiFetch("/api/users");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch users list");
    }

    async saveUser(user) {
        const res = await window.authService.apiFetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(user)
        });
        return res;
    }

    async deleteUser(username) {
        const res = await window.authService.apiFetch(`/api/users/${username}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchFirewallBlocks() {
        const res = await window.authService.apiFetch("/api/firewall/blocks");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch firewall blocked packet logs");
    }
}

window.securityService = new SecurityService();
