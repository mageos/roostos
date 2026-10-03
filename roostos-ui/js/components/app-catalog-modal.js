/**
 * AppCatalogModal - Modal template helpers for RoostOS App Catalog
 */

export const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export const renderInstallModalTemplate = (app) => html`
    <div class="card" style="width:90%;max-width:540px;background:#131b2e;border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:24px;color:#f1f5f9;font-family:'Outfit',sans-serif;">
        <h3 style="margin-top:0;margin-bottom:8px;">Install ${app.name}</h3>
        <p style="font-size:13px;color:#94a3b8;margin-bottom:16px;">${app.description}</p>
        <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:12px;margin-bottom:16px;font-size:12px;">
            <div style="font-weight:600;margin-bottom:6px;color:#e2e8f0;">Required System Scopes & Permissions:</div>
            <div style="color:#94a3b8;">Ports: ${(app.container?.ports || []).map(p => `${p.host_port}➔${p.container_port}`).join(", ") || "None"}</div>
            <div style="color:#94a3b8;">Volumes: ${(app.container?.volumes || []).map(v => `${v.host_path}➔${v.container_path}`).join(", ") || "None"}</div>
        </div>
        <div style="margin-bottom:12px;">
            <label style="font-size:12px;color:#94a3b8;display:block;margin-bottom:4px;">Target Node / Compute:</label>
            <select id="install-node-select" class="input-field" style="width:100%;">
                <option value="local">local (Current Node)</option>
            </select>
        </div>
        <div style="margin-bottom:16px;">
            <label style="font-size:13px;display:flex;align-items:center;gap:8px;cursor:pointer;">
                <input type="checkbox" id="install-consent-check">
                <span>I consent to granting these container volume & port permissions.</span>
            </label>
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.08);padding-top:12px;margin-bottom:16px;">
            <label style="font-size:13px;display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:8px;">
                <input type="checkbox" id="install-edge-check">
                <span>Expose externally via Edge Gateway (CGNAT Bypass)</span>
            </label>
            <div id="install-edge-domain-box" style="display:none;margin-left:22px;">
                <input type="text" id="install-edge-domain" class="input-field" placeholder="${app.id}.yourdomain.com" style="width:100%;font-size:13px;">
            </div>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:12px;">
            <button class="btn btn-secondary btn-sm" id="close-install-modal-btn">Cancel</button>
            <button class="btn btn-primary btn-sm" id="confirm-install-btn">Confirm & Install</button>
        </div>
    </div>
`;
