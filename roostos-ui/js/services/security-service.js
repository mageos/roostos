class SecurityService {
    async fetchSchedules() {
        const res = await window.authService.apiFetch("/api/v1/schedules");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch schedules");
    }

    async fetchFirewallRules() {
        const res = await window.authService.apiFetch("/api/v1/firewall/rules");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch firewall rules");
    }

    async saveFirewallRule(rule) {
        const res = await window.authService.apiFetch("/api/v1/firewall/rules", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rule)
        });
        return res;
    }

    async deleteFirewallRule(name) {
        const res = await window.authService.apiFetch(`/api/v1/firewall/rules/${encodeURIComponent(name)}`, {
            method: "DELETE"
        });
        return res;
    }


    async saveSchedule(schedule) {
        const res = await window.authService.apiFetch("/api/v1/schedules", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(schedule)
        });
        return res;
    }

    async deleteSchedule(name) {
        const res = await window.authService.apiFetch(`/api/v1/schedules/${name}`, {
            method: "DELETE"
        });
        return res;
    }

    async triggerBypass(personId, durationMins) {
        const res = await window.authService.apiFetch("/api/v1/schedules/bypass", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ person_id: personId, duration_minutes: durationMins })
        });
        return res;
    }

    async fetchDnsConfig() {
        const res = await window.authService.apiFetch("/api/v1/dns/config");
        if (res.ok) {
            const data = await res.json();
            window.localDnsRecords = data.local_records || [];
            return data;
        }
        throw new Error("Failed to fetch DNS configuration");
    }

    async saveDnsConfig(config) {
        const res = await window.authService.apiFetch("/api/v1/dns/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        });
        return res;
    }

    async fetchUsers() {
        const res = await window.authService.apiFetch("/api/v1/users");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch users list");
    }

    async saveUser(user) {
        const res = await window.authService.apiFetch("/api/v1/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(user)
        });
        return res;
    }

    async deleteUser(username) {
        const res = await window.authService.apiFetch(`/api/v1/users/${username}`, {
            method: "DELETE"
        });
        return res;
    }

    async fetchAntiEvasionSettings() {
        const res = await window.authService.apiFetch("/api/v1/firewall/anti-evasion");
        if (res.ok) {
            return await res.json();
        }
        throw new Error("Failed to fetch anti-evasion settings");
    }

    async saveAntiEvasionSettings(settings) {
        const res = await window.authService.apiFetch("/api/v1/firewall/anti-evasion", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        });
        return res;
    }
}

window.securityService = new SecurityService();

