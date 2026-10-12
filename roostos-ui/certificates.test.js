const fs = require('fs');
const path = require('path');

global.fetch = jest.fn();
global.alert = jest.fn();
global.confirm = jest.fn(() => true);

const localStorageMock = (() => {
    let store = {};
    return {
        getItem: (k) => store[k] || null,
        setItem: (k, v) => { store[k] = v.toString(); },
        removeItem: (k) => delete store[k],
        clear: () => { store = {}; }
    };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

function loadScript(relPath) {
    const fullPath = path.resolve(__dirname, relPath);
    let content = fs.readFileSync(fullPath, 'utf8');
    content = content.replace(/import\s*\{[\s\S]*?\}\s*from\s*['"][^'"]+['"];?/g, '');
    content = content.replace(/import\s+.*?from\s+['"][^'"]+['"];?/g, '');
    content = content.replace(/^export\s+const\s+(\w+)\s*=/gm, 'global.$1 = window.$1 =');
    content = content.replace(/^export\s+class\s+(\w+)/gm, 'global.$1 = window.$1 = class $1');
    content = content.replace(/^export\s+/gm, '');
    (0, eval)(content);
}

loadScript('js/components/certificates-templates.js');
loadScript('js/components/certificates-management.js');

describe('Certificates & Automated ACME SSL UI Component', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-jwt');
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ([])
        });
        document.body.innerHTML = '<certificates-management id="cert-elem"></certificates-management>';
    });

    test('Renders Root CA status, ACME settings, and certificates table', async () => {
        global.fetch
            // 1. /api/v1/system/certificates
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    root_ca: { issuer: "RoostOS Root Certificate Authority", expires_at: "2036-01-01T00:00:00Z", valid: true },
                    domains: []
                })
            })
            // 2. /api/v1/system/certificates/acme/settings
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    email: "admin@myhome.org",
                    staging: false,
                    default_challenge: "dns-01",
                    dns_providers: {}
                })
            })
            // 3. /api/v1/system/certificates/domains
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ([{
                    domain: "router.myhome.org",
                    sans: ["*.router.myhome.org"],
                    issuer: "Let's Encrypt",
                    status: "valid",
                    challenge_type: "dns-01",
                    dns_provider: "cloudflare",
                    expires_at: "2027-01-01T00:00:00Z",
                    auto_renew: true
                }])
            });

        const elem = document.getElementById('cert-elem');
        await elem.loadData();

        expect(elem.innerHTML).toContain("Internal RoostOS Root Certificate Authority");
        expect(elem.innerHTML).toContain("router.myhome.org");
        expect(elem.innerHTML).toContain("Let's Encrypt");
        expect(elem.innerHTML).toContain("dns-01");
        expect(elem.innerHTML).toContain("Valid");
        expect(elem.querySelector("#download-ca-btn")).not.toBeNull();
    });

    test('Clicking + Request Certificate inserts an inline add row form without persistent form', async () => {
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ root_ca: { valid: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ email: "" }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] });

        const elem = document.getElementById('cert-elem');
        await elem.loadData();

        // Verify no persistent form initially
        expect(elem.querySelector('.inline-add-row')).toBeNull();

        // Click top add button
        const topBtn = elem.querySelector('#top-add-cert-btn');
        expect(topBtn).not.toBeNull();
        topBtn.click();

        // Verify inline add row exists
        const inlineRow = elem.querySelector('.inline-add-row');
        expect(inlineRow).not.toBeNull();
        expect(inlineRow.querySelector('.cert-domain-input')).not.toBeNull();
        expect(inlineRow.querySelector('.cert-challenge-select')).not.toBeNull();

        // Cancel removes inline row
        inlineRow.querySelector('.cancel-cert-btn').click();
        expect(elem.querySelector('.inline-add-row')).toBeNull();
    });

    test('Submitting inline add form orders SSL certificate via API', async () => {
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ root_ca: { valid: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ email: "" }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] });

        const elem = document.getElementById('cert-elem');
        await elem.loadData();

        elem.querySelector('#top-add-cert-btn').click();
        const inlineRow = elem.querySelector('.inline-add-row');

        inlineRow.querySelector('.cert-domain-input').value = 'app.myhome.org';
        inlineRow.querySelector('.cert-challenge-select').value = 'dns-01';
        inlineRow.querySelector('.cert-provider-select').value = 'cloudflare';
        inlineRow.querySelector('.cert-token-input').value = 'cf-token-secret';

        // Mock POST order response
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                domain: 'app.myhome.org',
                status: 'valid'
            })
        });
        // Mock reloadData responses
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ root_ca: { valid: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ email: "" }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [{ domain: 'app.myhome.org', status: 'valid', expires_at: '2027-01-01' }] });

        await elem.submitOrder(inlineRow);

        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/certificates/domains', expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('"domain":"app.myhome.org"')
        }));
    });

    test('Renew and delete actions call corresponding endpoints', async () => {
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ root_ca: { valid: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ email: "" }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [{ domain: 'test.lan', status: 'valid' }] });

        const elem = document.getElementById('cert-elem');
        await elem.loadData();

        // Renew
        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) });
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ root_ca: { valid: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ email: "" }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] });

        await elem.renewCert('test.lan');
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/certificates/domains/test.lan/renew', expect.objectContaining({
            method: 'POST'
        }));

        // Delete
        global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success' }) });
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ root_ca: { valid: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ email: "" }) })
            .mockResolvedValueOnce({ ok: true, json: async () => [] });

        await elem.deleteCert('test.lan');
        expect(global.fetch).toHaveBeenCalledWith('/api/v1/system/certificates/domains/test.lan', expect.objectContaining({
            method: 'DELETE'
        }));
    });
});
