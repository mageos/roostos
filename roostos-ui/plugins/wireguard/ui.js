window.RoostOS.registerVpnFormHandler("wireguard", {
    renderConfigFields(containerEl, currentConfig = {}) {
        containerEl.innerHTML = `
            <h4 style="font-size: 13px; margin-bottom: 12px; font-weight: 600; color: var(--text-secondary);">WireGuard Client Parameters</h4>
            <div class="form-row-multi">
                <div class="form-group" style="flex: 1;">
                    <label>Client Interface Private Key</label>
                    <input type="password" id="wg-privkey" value="${escapeHtml(currentConfig.private_key || '')}" required placeholder="e.g. yAnu6...=">
                </div>
                <div class="form-group" style="flex: 1;">
                    <label>Local Tunnel Address (CIDR)</label>
                    <input type="text" id="wg-address" value="${escapeHtml(currentConfig.address || '')}" required placeholder="e.g. 10.0.0.2/32">
                </div>
            </div>
            <div class="form-row-multi">
                <div class="form-group" style="flex: 1;">
                    <label>Peer Public Key</label>
                    <input type="text" id="wg-pubkey" value="${escapeHtml(currentConfig.peer_pubkey || '')}" required placeholder="e.g. xI9uf...=">
                </div>
                <div class="form-group" style="flex: 1;">
                    <label>Peer Endpoint Address</label>
                    <input type="text" id="wg-endpoint" value="${escapeHtml(currentConfig.endpoint || '')}" required placeholder="e.g. vpn.example.com:51820">
                </div>
            </div>
            <div class="form-row-multi">
                <div class="form-group" style="flex: 1;">
                    <label>Allowed IPs (route selection)</label>
                    <input type="text" id="wg-allowed-ips" value="${escapeHtml(currentConfig.allowed_ips || '0.0.0.0/0')}" required>
                </div>
            </div>
        `;
    },
    serializeConfig() {
        return {
            private_key: document.getElementById("wg-privkey").value.trim(),
            address: document.getElementById("wg-address").value.trim(),
            peer_pubkey: document.getElementById("wg-pubkey").value.trim(),
            endpoint: document.getElementById("wg-endpoint").value.trim(),
            allowed_ips: document.getElementById("wg-allowed-ips").value.trim()
        };
    }
});

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
