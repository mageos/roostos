// RoostOS Web API Client Bridge
export class RoostApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async request(path, options = {}) {
        const url = `${this.baseUrl}${path}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };
        const token = localStorage.getItem('roostos_token') || sessionStorage.getItem('roostos_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        try {
            const resp = await fetch(url, { ...options, headers });
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Request to ${path} failed with status ${resp.status}`);
            }
            return await resp.json();
        } catch (err) {
            console.warn(`API request to ${path} failed:`, err.message);
            throw err;
        }
    }

    // Household Hub APIs
    async getHouseholdPulse() {
        return this.request('/api/v1/household/pulse');
    }

    async getGuestWifi() {
        return this.request('/api/v1/household/guest-wifi');
    }

    async toggleGuestWifi(enabled) {
        return this.request('/api/v1/household/guest-wifi/toggle', {
            method: 'POST',
            body: JSON.stringify({ enabled })
        });
    }

    async runSpeedTest() {
        return this.request('/api/v1/household/speedtest', { method: 'POST' });
    }

    // Family & Screentime APIs
    async getFamilyPeople() {
        return this.request('/api/v1/family/people');
    }

    async createFamilyPerson(personData) {
        return this.request('/api/v1/family/people', {
            method: 'POST',
            body: JSON.stringify(personData)
        });
    }

    async updateFamilyPerson(personId, personData) {
        return this.request(`/api/v1/family/people/${encodeURIComponent(personId)}`, {
            method: 'PUT',
            body: JSON.stringify(personData)
        });
    }

    async deleteFamilyPerson(personId) {
        return this.request(`/api/v1/family/people/${encodeURIComponent(personId)}`, {
            method: 'DELETE'
        });
    }

    async pausePerson(personId, paused = true) {
        return this.request(`/api/v1/family/people/${encodeURIComponent(personId)}/pause`, {
            method: 'POST',
            body: JSON.stringify({ paused })
        });
    }

    async grantScreentimeBonus(personId, durationMinutes = 30) {
        return this.request(`/api/v1/family/people/${personId}/bonus`, {
            method: 'POST',
            body: JSON.stringify({ duration_minutes: durationMinutes })
        });
    }

    async pauseKids(paused = true) {
        return this.request('/api/v1/family/pause-kids', {
            method: 'POST',
            body: JSON.stringify({ paused })
        });
    }

    async triggerDinnerTime(durationMinutes = 60) {
        return this.request('/api/v1/family/dinner-time', {
            method: 'POST',
            body: JSON.stringify({ duration_minutes: durationMinutes })
        });
    }

    // Protection & Threat Feed APIs
    async getBlockedThreatFeed(category = null) {
        const query = category ? `?category=${encodeURIComponent(category)}` : '';
        return this.request(`/api/v1/protection/blocked-feed${query}`);
    }

    async allowThreatTarget(target, subsystem = 'DNS Sinkhole') {
        return this.request('/api/v1/protection/allow', {
            method: 'POST',
            body: JSON.stringify({ target, subsystem })
        });
    }

    async getSecurityShields() {
        return this.request('/api/v1/protection/shields');
    }

    async updateSecurityShields(shieldsData) {
        return this.request('/api/v1/protection/shields', {
            method: 'POST',
            body: JSON.stringify(shieldsData)
        });
    }

    // Devices APIs
    async getDevices() {
        return this.request('/api/devices');
    }

    async registerDevice(devData) {
        return this.request('/api/devices', {
            method: 'POST',
            body: JSON.stringify(devData)
        });
    }

    async deleteDevice(mac) {
        return this.request(`/api/devices/${encodeURIComponent(mac)}`, {
            method: 'DELETE'
        });
    }

    // Kea DHCP APIs
    async getDhcpScopes() {
        return this.request('/api/v1/dhcp/scopes');
    }

    async updateDhcpScope(scopeId, scopeData) {
        return this.request(`/api/v1/dhcp/scopes/${encodeURIComponent(scopeId)}`, {
            method: 'PUT',
            body: JSON.stringify(scopeData)
        });
    }

    async createDhcpScope(scopeData) {
        return this.request('/api/v1/dhcp/scopes', {
            method: 'POST',
            body: JSON.stringify(scopeData)
        });
    }

    async getDhcpLeases(nodeId = null) {
        const q = nodeId ? `?node_id=${encodeURIComponent(nodeId)}` : '';
        return this.request(`/api/v1/dhcp/leases${q}`);
    }

    async convertLeaseToStatic(mac, hostname = null, description = null) {
        return this.request('/api/v1/dhcp/reservations/from-lease', {
            method: 'POST',
            body: JSON.stringify({ mac, hostname, description })
        });
    }

    async getDhcpReservations() {
        return this.request('/api/v1/dhcp/reservations');
    }

    async deleteDhcpReservation(mac) {
        return this.request(`/api/v1/dhcp/reservations/${encodeURIComponent(mac)}`, {
            method: 'DELETE'
        });
    }

    // Firewall & Port Forwards APIs
    async getPortForwards() {
        return this.request('/api/firewall/port-forwards');
    }

    async createPortForward(pfData) {
        return this.request('/api/firewall/port-forwards', {
            method: 'POST',
            body: JSON.stringify(pfData)
        });
    }

    async deletePortForward(name) {
        return this.request(`/api/firewall/port-forwards/${encodeURIComponent(name)}`, {
            method: 'DELETE'
        });
    }

    // DNS Records APIs
    async getDnsRecords() {
        return this.request('/api/dns/records');
    }

    async createDnsRecord(recordData) {
        return this.request('/api/dns/records', {
            method: 'POST',
            body: JSON.stringify(recordData)
        });
    }

    async deleteDnsRecord(recordId) {
        return this.request(`/api/dns/records/${encodeURIComponent(recordId)}`, {
            method: 'DELETE'
        });
    }
}

export const api = new RoostApiClient();
