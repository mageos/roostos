/**
 * Modals for Edge Gateway Web Component
 */

import { createModal, renderPeerQrModalContent } from "./edge-gateway-templates.js";

export const showPeerQrModal = (peer) => {
    const modal = createModal("peer-qr-modal", renderPeerQrModalContent(peer));
    modal.querySelectorAll(".close-modal-btn").forEach(btn => {
        btn.onclick = () => modal.remove();
    });
    return modal;
};

export const showEditEndpointModal = (component, apiFetch) => {
    const currentHost = component.gateway?.domain || component.gateway?.public_ip || "";
    const currentPort = component.gateway?.listen_port || 51820;
    const modal = createModal("edge-endpoint-modal", `
        <h3 style="margin-top:0;margin-bottom:12px;">Update Edge Endpoint</h3>
        <p style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:16px;">
            Specify a domain name (e.g. <code>vps.example.com</code>) or IP address for WireGuard endpoint resolution.
        </p>
        <div class="form-group" style="margin-bottom:12px;">
            <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Domain Name or IP:</label>
            <input type="text" id="endpoint-host-input" class="input-field" placeholder="vps.example.com" value="${currentHost}" style="width:100%;">
        </div>
        <div class="form-group" style="margin-bottom:16px;">
            <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Port:</label>
            <input type="number" id="endpoint-port-input" class="input-field" value="${currentPort}" style="width:100%;">
        </div>
        <div style="display:flex;justify-content:flex-end;gap:12px;">
            <button class="btn btn-secondary" id="endpoint-modal-cancel">Cancel</button>
            <button class="btn btn-primary" id="endpoint-modal-save">Update Endpoint</button>
        </div>
    `);

    modal.querySelector("#endpoint-modal-cancel").onclick = () => modal.remove();
    modal.querySelector("#endpoint-modal-save").onclick = async () => {
        const host = modal.querySelector("#endpoint-host-input").value.trim();
        const port = parseInt(modal.querySelector("#endpoint-port-input").value, 10) || 51820;
        if (!host) return alert("Please specify a domain name or IP.");
        const isIp = /^(\d{1,3}\.){3}\d{1,3}$/.test(host);
        try {
            const res = await apiFetch("/api/v1/edge/endpoint", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ domain: isIp ? null : host, ip: isIp ? host : null, port })
            });
            if (res.ok) {
                modal.remove();
                await component.loadData();
            } else {
                const err = await res.json();
                alert(`Update failed: ${err.detail || "Error"}`);
            }
        } catch (err) {
            alert(`Network error: ${err}`);
        }
    };
    return modal;
};

export const showLinkModal = (component, apiFetch) => {
    const modal = createModal("edge-link-modal", `
        <h3 style="margin-top:0;margin-bottom:12px;">Connect VPS Edge Gateway</h3>
        <p style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:16px;">
            Run <code>roostos edge token</code> on your Debian VPS, then paste the WireGuard invite token or upload the bundle file:
        </p>
        <div class="form-group" style="margin-bottom:12px;">
            <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Invitation Token:</label>
            <input type="text" id="edge-token-input" class="input-field" placeholder="roost-edge-wg://... or roost-edge://..." style="width:100%;">
        </div>
        <div class="form-group" style="margin-bottom:16px;">
            <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Or Upload Invitation File (.json):</label>
            <input type="file" id="edge-bundle-file" accept=".json" style="font-size:12px;color:#94a3b8;width:100%;">
        </div>
        <div style="display:flex;justify-content:flex-end;gap:12px;">
            <button class="btn btn-secondary" id="edge-modal-cancel">Cancel</button>
            <button class="btn btn-primary" id="edge-modal-connect">Connect & Establish Tunnel</button>
        </div>
    `);

    modal.querySelector("#edge-bundle-file").onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                const parsed = JSON.parse(evt.target.result);
                if (parsed.client_private_key && parsed.endpoint) {
                    modal.querySelector("#edge-token-input").value = `roost-edge-wg://${btoa(evt.target.result)}`;
                } else if (parsed.token) {
                    modal.querySelector("#edge-token-input").value = parsed.token;
                }
            } catch (err) {
                alert("Could not read file: " + err);
            }
        };
        reader.readAsText(file);
    };

    modal.querySelector("#edge-modal-cancel").onclick = () => modal.remove();
    modal.querySelector("#edge-modal-connect").onclick = async () => {
        const token = modal.querySelector("#edge-token-input").value.trim();
        if (!token) return alert("Please enter the bootstrap token.");
        const btn = modal.querySelector("#edge-modal-connect");
        btn.disabled = true;
        btn.textContent = "Connecting...";

        try {
            const res = await apiFetch("/api/v1/edge/connect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token })
            });
            if (res.ok) {
                modal.remove();
                alert("Edge Gateway paired successfully! WireGuard tunnel active.");
                await component.loadData();
            } else {
                const err = await res.json();
                alert(`Connection failed: ${err.detail || "Unknown error"}`);
                btn.disabled = false;
                btn.textContent = "Connect & Establish Tunnel";
            }
        } catch (err) {
            alert(`Error connecting to Edge Gateway: ${err}`);
            btn.disabled = false;
            btn.textContent = "Connect & Establish Tunnel";
        }
    };
    return modal;
};
