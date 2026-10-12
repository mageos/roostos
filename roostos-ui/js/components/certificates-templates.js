/**
 * HTML Templates for Certificates & Automated ACME SSL Web Component
 */

export const html = (strings, ...values) => String.raw({ raw: strings }, ...values);

export const renderCertificatesTemplate = (caStatus, acmeSettings, certs, rowsHtml) => html`
    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Internal RoostOS Root Certificate Authority</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Used for internal mTLS cluster authentication, sidecar plugins, and local <code>.lan</code> HTTPS encryption.
                </p>
            </div>
            <a href="/api/v1/system/certificates/ca.crt" download="roostos-root-ca.crt" class="btn btn-secondary btn-sm" id="download-ca-btn">
                ⬇ Download Root CA (for LAN Devices)
            </a>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 16px;">
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">CA Status</div>
                <div style="font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <span style="width: 10px; height: 10px; border-radius: 50%; background: #10b981;"></span>
                    Active & Operational
                </div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">Issuer Common Name</div>
                <div style="font-family: monospace; font-size: 13px; font-weight: 600;">${caStatus?.issuer || "RoostOS Root CA"}</div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;">Valid Until</div>
                <div style="font-family: monospace; font-size: 13px;">${caStatus?.expires_at ? new Date(caStatus.expires_at).toLocaleDateString() : "2036"}</div>
            </div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 24px;">
        <div class="card-header table-action-bar">
            <div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600;">Automated Let's Encrypt / ACME Settings</h3>
                <p style="margin: 4px 0 0; font-size: 13px; color: var(--text-secondary);">
                    Automated domain validation using DNS-01 (for private LAN & wildcards) and HTTP-01 (for public Edge routes).
                </p>
            </div>
            <button class="btn btn-secondary btn-sm" id="save-acme-settings-btn">Save Settings</button>
        </div>
        <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 16px; margin-top: 16px;" class="acme-settings-grid">
            <div>
                <label style="display: block; font-size: 12px; margin-bottom: 4px; color: var(--text-secondary);">ACME Account Email:</label>
                <input type="email" id="acme-email-input" class="inline-input" placeholder="admin@yourdomain.com" value="${acmeSettings?.email || ''}">
            </div>
            <div>
                <label style="display: block; font-size: 12px; margin-bottom: 4px; color: var(--text-secondary);">Default Challenge:</label>
                <select id="acme-default-challenge-select" class="inline-input">
                    <option value="dns-01" ${acmeSettings?.default_challenge === 'dns-01' ? 'selected' : ''}>DNS-01 (Recommended for LAN)</option>
                    <option value="http-01" ${acmeSettings?.default_challenge === 'http-01' ? 'selected' : ''}>HTTP-01 (Public Edge Gateway)</option>
                </select>
            </div>
            <div>
                <label style="display: block; font-size: 12px; margin-bottom: 4px; color: var(--text-secondary);">Environment:</label>
                <select id="acme-staging-select" class="inline-input">
                    <option value="false" ${!acmeSettings?.staging ? 'selected' : ''}>Production (Trusted)</option>
                    <option value="true" ${acmeSettings?.staging ? 'selected' : ''}>Staging (Test Rate Limits)</option>
                </select>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-header table-action-bar">
            <h3>Managed SSL Certificates (${certs.length})</h3>
            <button class="btn btn-primary btn-sm" id="top-add-cert-btn">+ Request Certificate</button>
        </div>
        <div class="table-responsive">
            <table class="data-table" id="certificates-table">
                <thead>
                    <tr>
                        <th>Domain / SANs</th>
                        <th>Issuer</th>
                        <th>Challenge Method</th>
                        <th>Expires</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="certificates-tbody">${rowsHtml}</tbody>
            </table>
        </div>
        <div class="card-footer table-action-bar" style="margin-top: 12px;">
            <span></span>
            <button class="btn btn-primary btn-sm" id="bottom-add-cert-btn">+ Request Certificate</button>
        </div>
    </div>
`;

export const renderCertRowTemplate = (c) => {
    const isExpiring = c.status === "expiring_soon";
    const isExpired = c.status === "expired";
    const badgeClass = isExpired ? "badge-danger" : (isExpiring ? "badge-warning" : "badge-success");
    const statusLabel = isExpired ? "Expired" : (isExpiring ? "Expiring Soon" : "Valid");

    return html`
    <tr id="cert-row-${c.domain}">
        <td>
            <strong><code>${c.domain}</code></strong>
            ${c.sans && c.sans.length > 0 ? `<div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">SANs: ${c.sans.join(', ')}</div>` : ''}
        </td>
        <td>${c.issuer || "Let's Encrypt"}</td>
        <td>
            <span style="font-family: monospace; font-size: 12px;">${c.challenge_type}</span>
            ${c.dns_provider ? `<span style="font-size: 11px; color: #38bdf8; margin-left: 4px;">(${c.dns_provider})</span>` : ''}
        </td>
        <td>${c.expires_at ? new Date(c.expires_at).toLocaleDateString() : 'N/A'}</td>
        <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
        <td>
            <button class="btn btn-secondary btn-sm renew-cert-btn" data-domain="${c.domain}">Renew</button>
            <button class="btn btn-danger btn-sm delete-cert-btn" data-domain="${c.domain}">Delete</button>
        </td>
    </tr>
    `;
};

export const renderInlineCertRowTemplate = (c = {}) => html`
    <tr class="inline-add-row" ${c.domain ? `id="edit-row-${c.domain}"` : ''}>
        <td>
            <input type="text" class="inline-input cert-domain-input" placeholder="router.yourdomain.com" value="${c.domain || ''}" style="margin-bottom: 4px;">
            <input type="text" class="inline-input cert-sans-input" placeholder="SANs (optional, comma-separated)" value="${c.sans ? c.sans.join(', ') : ''}" style="font-size: 11px;">
        </td>
        <td><span style="font-size: 13px; color: var(--text-secondary);">Let's Encrypt</span></td>
        <td>
            <select class="inline-input cert-challenge-select" style="margin-bottom: 4px;">
                <option value="dns-01" ${c.challenge_type === 'dns-01' ? 'selected' : ''}>DNS-01 (LAN & Wildcards)</option>
                <option value="http-01" ${c.challenge_type === 'http-01' ? 'selected' : ''}>HTTP-01 (Edge Gateway)</option>
            </select>
            <div class="dns-prov-fields" style="${c.challenge_type === 'http-01' ? 'display: none;' : ''}">
                <select class="inline-input cert-provider-select" style="margin-bottom: 4px; font-size: 12px;">
                    <option value="cloudflare">Cloudflare</option>
                    <option value="duckdns">DuckDNS</option>
                    <option value="route53">AWS Route53</option>
                    <option value="webhook">RFC 2136 / Webhook</option>
                </select>
                <input type="password" class="inline-input cert-token-input" placeholder="API Token / Secret Key" style="font-size: 11px;">
            </div>
        </td>
        <td><span style="font-size: 12px; color: var(--text-secondary);">90 Days</span></td>
        <td>
            <label style="font-size: 12px; display: flex; align-items: center; gap: 4px; cursor: pointer;">
                <input type="checkbox" class="cert-autorenew-input" ${c.auto_renew !== false ? 'checked' : ''}> Auto-Renew
            </label>
        </td>
        <td>
            <div class="inline-form-controls">
                <button class="btn btn-success btn-sm save-cert-btn">Request</button>
                <button class="btn btn-secondary btn-sm cancel-cert-btn">Cancel</button>
            </div>
        </td>
    </tr>
`;
