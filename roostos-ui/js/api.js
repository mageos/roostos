// RoostOS Web API Client Bridge
export class RoostApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async request(path, options = {}) {
        const url = `${this.baseUrl}${path}`;
        const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
        const token = localStorage.getItem('roostos_token') || sessionStorage.getItem('roostos_token');
        if (token) headers['Authorization'] = `Bearer ${token}`;

        try {
            const resp = await fetch(url, { ...options, headers });
            if (resp.status === 401) {
                localStorage.removeItem('roostos_token');
                sessionStorage.removeItem('roostos_token');
                const urlParams = new URLSearchParams(window.location.search);
                if (!urlParams.get('code') && !window.ROOSTOS_MOCK) {
                    window.location.href = "/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=" + encodeURIComponent(window.location.origin + "/");
                }
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Unauthorized (401)`);
            }
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
    async getHouseholdPulse() { return this.request('/api/v1/household/pulse'); }
    async getGuestWifi() { return this.request('/api/v1/household/guest-wifi'); }
    async toggleGuestWifi(enabled) {
        return this.request('/api/v1/household/guest-wifi/toggle', { method: 'POST', body: JSON.stringify({ enabled }) });
    }
    async runSpeedTest() { return this.request('/api/v1/household/speedtest', { method: 'POST' }); }

    // Family & Screentime APIs
    async getFamilyPeople() { return this.request('/api/v1/family/people'); }
    async createFamilyPerson(personData) {
        return this.request('/api/v1/family/people', { method: 'POST', body: JSON.stringify(personData) });
    }
    async updateFamilyPerson(personId, personData) {
        return this.request(`/api/v1/family/people/${encodeURIComponent(personId)}`, { method: 'PUT', body: JSON.stringify(personData) });
    }
    async deleteFamilyPerson(personId) {
        return this.request(`/api/v1/family/people/${encodeURIComponent(personId)}`, { method: 'DELETE' });
    }
    async pausePerson(personId, paused = true) {
        return this.request(`/api/v1/family/people/${encodeURIComponent(personId)}/pause`, { method: 'POST', body: JSON.stringify({ paused }) });
    }
    async grantScreentimeBonus(personId, durationMinutes = 30) {
        return this.request(`/api/v1/family/people/${personId}/bonus`, { method: 'POST', body: JSON.stringify({ duration_minutes: durationMinutes }) });
    }
    async pauseKids(paused = true) {
        return this.request('/api/v1/family/pause-kids', { method: 'POST', body: JSON.stringify({ paused }) });
    }
    async triggerDinnerTime(durationMinutes = 60) {
        return this.request('/api/v1/family/dinner-time', { method: 'POST', body: JSON.stringify({ duration_minutes: durationMinutes }) });
    }

    // Protection & Threat Feed APIs
    async getBlockedThreatFeed(category = null) {
        const query = category ? `?category=${encodeURIComponent(category)}` : '';
        return this.request(`/api/v1/protection/blocked-feed${query}`);
    }
    async allowThreatTarget(target, subsystem = 'DNS Sinkhole') {
        return this.request('/api/v1/protection/allow', { method: 'POST', body: JSON.stringify({ target, subsystem }) });
    }
    async getSecurityShields() { return this.request('/api/v1/protection/shields'); }
    async updateSecurityShields(shieldsData) {
        return this.request('/api/v1/protection/shields', { method: 'POST', body: JSON.stringify(shieldsData) });
    }

    // Devices APIs
    async getDevices() { return this.request('/api/v1/devices'); }
    async registerDevice(devData) {
        return this.request('/api/v1/devices', { method: 'POST', body: JSON.stringify(devData) });
    }
    async deleteDevice(mac) {
        return this.request(`/api/v1/devices/${encodeURIComponent(mac)}`, { method: 'DELETE' });
    }

    // System & Telemetry APIs
    async getSystem() { return this.request('/api/v1/system'); }
    async getSystemServices() { return this.request('/api/v1/system/services'); }
    async getSystemHealth() { return this.request('/api/v1/health'); }
    async getStateBundle() { return this.request('/api/v1/config/state-bundle'); }
    async getTelemetryHealth() { return this.request('/api/v1/telemetry/health'); }

    // Network & Wi-Fi APIs
    async getNetwork() { return this.request('/api/v1/network'); }

    // Cluster Fleet APIs
    async getClusterStatus() { return this.request('/api/v1/cluster/status'); }
    async getClusterNodes() { return this.request('/api/v1/cluster/nodes'); }

    // Edge Gateway APIs
    async getEdgeStatus() { return this.request('/api/v1/edge/status'); }
    async connectEdgeGateway(token, name = 'VPS Edge Gateway', domain = null) {
        return this.request('/api/v1/edge/connect', { method: 'POST', body: JSON.stringify({ token, name, domain }) });
    }
    async updateEdgeEndpoint(endpointData) {
        return this.request('/api/v1/edge/endpoint', { method: 'PUT', body: JSON.stringify(endpointData) });
    }
    async createEdgeRoute(routeData) {
        return this.request('/api/v1/edge/routes', { method: 'POST', body: JSON.stringify(routeData) });
    }
    async deleteEdgeRoute(routeId) {
        return this.request(`/api/v1/edge/routes/${encodeURIComponent(routeId)}`, { method: 'DELETE' });
    }
    async getEdgePeers() { return this.request('/api/v1/edge/peers'); }
    async createEdgePeer(peerData) {
        return this.request('/api/v1/edge/peers', { method: 'POST', body: JSON.stringify(peerData) });
    }
    async deleteEdgePeer(peerId) {
        return this.request(`/api/v1/edge/peers/${encodeURIComponent(peerId)}`, { method: 'DELETE' });
    }
    async getEdgePeerQr(peerId) {
        const token = localStorage.getItem('roostos_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch(`/api/v1/edge/peers/${encodeURIComponent(peerId)}/qr`, { headers });
        return res.text();
    }
    async getEdgePeerConfig(peerId) {
        const token = localStorage.getItem('roostos_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch(`/api/v1/edge/peers/${encodeURIComponent(peerId)}/config`, { headers });
        return res.text();
    }
    async disconnectEdgeGateway(gatewayId = null) {
        return this.request('/api/v1/edge/disconnect', { method: 'POST', body: JSON.stringify(gatewayId ? { gateway_id: gatewayId } : {}) });
    }
    async getVpnServers() { return this.request('/api/v1/edge/peers/servers'); }
    async updateVpnServer(serverId, data) {
        return this.request(`/api/v1/edge/peers/servers/${encodeURIComponent(serverId)}`, { method: 'PUT', body: JSON.stringify(data) });
    }
    async syncEdgeLanRoutes(lanSubnets = null) {
        return this.request('/api/v1/edge/routes/sync-lan', {
            method: 'POST', body: JSON.stringify(lanSubnets ? { lan_subnets: lanSubnets } : {})
        });
    }
    async verifyEdgeConnectivity() { return this.request('/api/v1/edge/verify'); }
    async verifyClusterConnectivity() { return this.request('/api/v1/cluster/verify'); }

    // System Updates & Maintenance APIs
    async getUpdateStatus() { return this.request('/api/v1/system/updates/status'); }
    async checkUpdates() { return this.request('/api/v1/system/updates/check', { method: 'POST' }); }
    async installUpdates(securityOnly = false) {
        return this.request(`/api/v1/system/updates/install?security_only=${Boolean(securityOnly)}`, { method: 'POST' });
    }
    async rebootRouter() { return this.request('/api/v1/system/reboot', { method: 'POST' }); }

    // Kea DHCP APIs
    async getDhcpScopes() { return this.request('/api/v1/dhcp/scopes'); }
    async updateDhcpScope(scopeId, scopeData) {
        return this.request(`/api/v1/dhcp/scopes/${encodeURIComponent(scopeId)}`, { method: 'PUT', body: JSON.stringify(scopeData) });
    }
    async createDhcpScope(scopeData) {
        return this.request('/api/v1/dhcp/scopes', { method: 'POST', body: JSON.stringify(scopeData) });
    }
    async getDhcpLeases(nodeId = null) {
        return this.request(`/api/v1/dhcp/leases${nodeId ? `?node_id=${encodeURIComponent(nodeId)}` : ''}`);
    }
    async convertLeaseToStatic(mac, hostname = null, description = null) {
        return this.request('/api/v1/dhcp/reservations/from-lease', { method: 'POST', body: JSON.stringify({ mac, hostname, description }) });
    }
    async getDhcpReservations() { return this.request('/api/v1/dhcp/reservations'); }
    async deleteDhcpReservation(mac) {
        return this.request(`/api/v1/dhcp/reservations/${encodeURIComponent(mac)}`, { method: 'DELETE' });
    }

    // Firewall & Port Forwards APIs
    async getPortForwards() { return this.request('/api/v1/firewall/port-forwards'); }
    async createPortForward(pfData) {
        return this.request('/api/v1/firewall/port-forwards', { method: 'POST', body: JSON.stringify(pfData) });
    }
    async deletePortForward(name) {
        return this.request(`/api/v1/firewall/port-forwards/${encodeURIComponent(name)}`, { method: 'DELETE' });
    }

    // DNS Records & Config APIs
    async getDnsConfig() { return this.request('/api/v1/dns/config'); }
    async getDnsRecords() { return this.request('/api/v1/dns/records'); }
    async createDnsRecord(recordData) {
        return this.request('/api/v1/dns/records', { method: 'POST', body: JSON.stringify(recordData) });
    }
    async deleteDnsRecord(recordId) {
        return this.request(`/api/v1/dns/records/${encodeURIComponent(recordId)}`, { method: 'DELETE' });
    }

    // App Catalog & Container Deployment APIs
    async getCatalogApps() { return this.request('/api/v1/catalog/apps'); }
    async getCatalogApp(appId) { return this.request(`/api/v1/catalog/apps/${encodeURIComponent(appId)}`); }
    async installCatalogApp(appData) {
        return this.request('/api/v1/catalog/apps/install', { method: 'POST', body: JSON.stringify(appData) });
    }
    async getCatalogSources() { return this.request('/api/v1/catalog/sources'); }
    async addCatalogSource(sourceData) {
        return this.request('/api/v1/catalog/sources', { method: 'POST', body: JSON.stringify(sourceData) });
    }
    async deleteCatalogSource(sourceId) {
        return this.request(`/api/v1/catalog/sources/${encodeURIComponent(sourceId)}`, { method: 'DELETE' });
    }
    async refreshCatalogs() { return this.request('/api/v1/catalog/refresh', { method: 'POST' }); }

    // Plugins / Installed Containers APIs
    async getPlugins() { return this.request('/api/v1/plugins'); }
    async togglePlugin(pluginId, enabled) {
        return this.request(`/api/v1/plugins/${encodeURIComponent(pluginId)}/toggle`, {
            method: 'POST', body: JSON.stringify({ enabled })
        });
    }
    async deletePlugin(pluginId) {
        return this.request(`/api/v1/plugins/${encodeURIComponent(pluginId)}`, { method: 'DELETE' });
    }

    // Incident Alerts APIs
    async getActiveAlerts() { return this.request('/api/v1/alerts/active'); }
    async getAlertHistory(limit = 20) { return this.request(`/api/v1/alerts/history?limit=${limit}`); }
    async acknowledgeAlert(alertId) {
        return this.request(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, { method: 'POST' });
    }
}

export const api = new RoostApiClient();
