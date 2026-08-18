window.RoostOS.registerVpnFormHandler("openvpn", {
    renderConfigFields(containerEl, currentConfig = {}) {
        containerEl.innerHTML = `
            <h4 style="font-size: 13px; margin-bottom: 12px; font-weight: 600; color: var(--text-secondary);">OpenVPN Connection Parameters</h4>
            <div class="form-group">
                <label>Imported .ovpn Profile Payload</label>
                <textarea id="ovpn-config" style="width: 100%; height: 180px; font-family: monospace; background: rgba(0,0,0,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; color: var(--text-primary); outline: none;" placeholder="client&#10;dev tun&#10;proto udp&#10;..." required>${escapeHtml(currentConfig.ovpn_data || '')}</textarea>
            </div>
            <div class="form-row-multi">
                <div class="form-group" style="flex: 1;">
                    <label>Username (Optional)</label>
                    <input type="text" id="ovpn-user" value="${escapeHtml(currentConfig.username || '')}" placeholder="VPN username">
                </div>
                <div class="form-group" style="flex: 1;">
                    <label>Password (Optional)</label>
                    <input type="password" id="ovpn-pass" value="${escapeHtml(currentConfig.password || '')}" placeholder="VPN password">
                </div>
            </div>
        `;
    },
    serializeConfig() {
        return {
            ovpn_data: document.getElementById("ovpn-config").value,
            username: document.getElementById("ovpn-user").value.trim(),
            password: document.getElementById("ovpn-pass").value
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
