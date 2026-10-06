const fs = require('fs');
const path = require('path');

global.fetch = jest.fn();
global.alert = jest.fn();

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
    content = content.replace(/^export\s+/gm, '');
    (0, eval)(content);
}

loadScript('js/services/auth-service.js');
loadScript('js/services/security-service.js');
loadScript('js/services/system-service.js');
loadScript('js/components/dns-settings-templates.js');
loadScript('js/components/dns-settings.js');

describe('DNS Settings & Dependency Management UI', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        window.localStorage.setItem('roostos_token', 'test-jwt');
        document.body.innerHTML = '<roost-dns-settings id="dns-elem"></roost-dns-settings>';
    });

    test('SystemService dependency methods make correct API requests', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({
                os_family: "debian",
                manager_name: "apt",
                all_satisfied: true,
                reports: []
            })
        });

        const deps = await window.systemService.fetchDependencies();
        expect(deps.manager_name).toBe("apt");
        expect(global.fetch).toHaveBeenCalledWith('/api/system/dependencies', expect.anything());

        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({ success: true, installed: ["docker.io"] })
        });

        const res = await window.systemService.installDependencies("dns_technitium");
        expect(res.success).toBe(true);
        expect(global.fetch).toHaveBeenCalledWith(
            '/api/system/dependencies/install',
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({ feature: "dns_technitium", packages: null })
            })
        );
    });

    test('SecurityService DNS methods make correct API requests', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({
                subsystem: "local",
                forwarders: ["1.1.1.1", "8.8.8.8"],
                ad_blocking_enabled: false,
                dependencies: { feature: "dns_local", satisfied: true, packages: [] }
            })
        });

        const data = await window.securityService.fetchDnsConfig();
        expect(data.subsystem).toBe("local");
        expect(global.fetch).toHaveBeenCalledWith('/api/dns/config', expect.anything());

        global.fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            json: async () => ({ status: "success", subsystem: "technitium" })
        });

        await window.securityService.saveDnsConfig({
            subsystem: "technitium",
            forwarders: ["9.9.9.9"],
            ad_blocking_enabled: true,
            auto_install_dependencies: true
        });
        expect(global.fetch).toHaveBeenCalledWith(
            '/api/dns/config',
            expect.objectContaining({ method: "POST" })
        );
    });

    test('DnsSettingsComponent renders local and technitium subsystem choices', () => {
        const elem = document.getElementById('dns-elem');
        elem.setData({
            subsystem: "local",
            forwarders: ["1.1.1.1", "8.8.8.8"],
            ad_blocking_enabled: false,
            dependencies: {
                feature: "dns_local",
                satisfied: true,
                packages: [
                    { name: "nftables", installed: true, version: "1.0.6" }
                ]
            }
        });

        expect(elem.querySelector('#select-local-card')).toBeTruthy();
        expect(elem.querySelector('#select-tech-card')).toBeTruthy();
        const fwdInput = elem.querySelector('#dns-forwarders-input');
        expect(fwdInput.value).toBe("1.1.1.1, 8.8.8.8");
    });

    test('DnsSettingsComponent displays missing dependencies warning and install button', () => {
        const elem = document.getElementById('dns-elem');
        elem.setData({
            subsystem: "technitium",
            forwarders: ["1.1.1.1"],
            ad_blocking_enabled: true,
            dependencies: {
                feature: "dns_technitium",
                satisfied: false,
                packages: [
                    { name: "docker.io", installed: false, version: null }
                ]
            }
        });

        const warningBanner = elem.querySelector('#install-subsystem-deps-btn');
        expect(warningBanner).toBeTruthy();
        expect(elem.textContent).toContain("docker.io");
        expect(elem.textContent).toContain("Missing Packages");
    });

    test('DnsSettingsComponent switches subsystem on card click', () => {
        const elem = document.getElementById('dns-elem');
        elem.setData({
            subsystem: "local",
            forwarders: ["1.1.1.1"],
            ad_blocking_enabled: false,
            dependencies: { feature: "dns_local", satisfied: true, packages: [] }
        });

        const techCard = elem.querySelector('#select-tech-card');
        techCard.click();

        expect(elem.subsystem).toBe("technitium");
        expect(elem.textContent).toContain("Technitium Web Console");
    });
});
