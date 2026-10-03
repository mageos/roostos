// RoostOS First-Run Setup & Onboarding Wizard Component

window.setupWizard = {
    env: null,
    selectedRole: null,

    async checkAndPromptSetup() {
        try {
            const res = await fetch("/api/setup/status");
            if (!res.ok) return;
            const data = await res.json();
            if (!data.is_configured) {
                this.env = data.environment;
                this.selectedRole = this.env.recommended_role || "gateway";
                this.renderModal();
            }
        } catch (e) {
            console.warn("Setup status check skipped:", e);
        }
    },

    renderModal() {
        let existing = document.getElementById("setup-wizard-modal");
        if (existing) existing.remove();

        const modal = document.createElement("div");
        modal.id = "setup-wizard-modal";
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(10, 15, 30, 0.85); backdrop-filter: blur(8px);
            display: flex; align-items: center; justify-content: center; z-index: 10000;
        `;

        const card = document.createElement("div");
        card.className = "card";
        card.style.cssText = `
            width: 90%; max-width: 640px; background: #131b2e; border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px; padding: 28px; box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            color: #f1f5f9; font-family: 'Outfit', sans-serif;
        `;

        card.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
                <span class="logo-dot" style="width: 14px; height: 14px; background: #6366f1; border-radius: 50%; box-shadow: 0 0 10px #6366f1;"></span>
                <h2 style="margin: 0; font-size: 22px; font-weight: 600;">Welcome to RoostOS Initial Setup</h2>
            </div>
            
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 14px; margin-bottom: 20px; font-size: 13px; line-height: 1.6;">
                <div><strong>System:</strong> ${this.env.arch} (${this.env.cpu_cores} Cores) | <strong>Memory:</strong> ${this.env.memory_total_mb} MB | <strong>Form:</strong> ${this.env.is_laptop ? "Laptop" : "Server/SBC"}</div>
                <div><strong>Detected Interfaces:</strong> ${this.env.interfaces.map(i => i.name).join(", ") || "None"}</div>
                <div style="color: #38bdf8; margin-top: 6px;">💡 <em>${this.env.recommendation_reason || "Ready to configure."}</em></div>
            </div>

            <div style="margin-bottom: 20px;">
                <label style="display: block; font-size: 13px; font-weight: 500; margin-bottom: 8px; color: #94a3b8;">Select System Role:</label>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;" id="wizard-role-buttons">
                    <button type="button" class="btn ${this.selectedRole === 'gateway' ? 'btn-primary' : 'btn-outline'}" onclick="window.setupWizard.selectRole('gateway')">
                        🌐 Gateway Router
                    </button>
                    <button type="button" class="btn ${this.selectedRole === 'controller' ? 'btn-primary' : 'btn-outline'}" onclick="window.setupWizard.selectRole('controller')">
                        🎛️ Controller & Server
                    </button>
                    <button type="button" class="btn ${this.selectedRole === 'standalone' ? 'btn-primary' : 'btn-outline'}" onclick="window.setupWizard.selectRole('standalone')">
                        📦 Standalone All-in-One
                    </button>
                    <button type="button" class="btn ${this.selectedRole === 'workstation' ? 'btn-primary' : 'btn-outline'}" onclick="window.setupWizard.selectRole('workstation')">
                        💻 Client Workstation
                    </button>
                </div>
            </div>

            <div id="wizard-role-fields" style="margin-bottom: 24px;"></div>

            <div style="display: flex; justify-content: flex-end; gap: 12px;">
                <button type="button" class="btn btn-primary" id="wizard-apply-btn" onclick="window.setupWizard.applySetup()" style="padding: 10px 24px; font-weight: 500;">
                    Complete Setup & Apply
                </button>
            </div>
        `;

        modal.appendChild(card);
        document.body.appendChild(modal);
        this.renderFields();
    },

    selectRole(role) {
        this.selectedRole = role;
        const btns = document.querySelectorAll("#wizard-role-buttons button");
        btns.forEach(b => {
            if (b.textContent.toLowerCase().includes(role)) {
                b.className = "btn btn-primary";
            } else {
                b.className = "btn btn-outline";
            }
        });
        this.renderFields();
    },

    renderFields() {
        const container = document.getElementById("wizard-role-fields");
        if (!container) return;

        const ethIfaces = this.env.interfaces.filter(i => !i.is_wireless && i.name !== "lo").map(i => i.name);
        const wanDefault = ethIfaces[0] || "eth0";
        const lanDefault = ethIfaces.slice(1).join(", ") || "eth1";

        if (this.selectedRole === "gateway" || this.selectedRole === "standalone") {
            container.innerHTML = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
                    <div>
                        <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">WAN Interface:</label>
                        <input type="text" id="wiz-wan" class="input-field" value="${wanDefault}" style="width: 100%;">
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">LAN Interface(s):</label>
                        <input type="text" id="wiz-lan" class="input-field" value="${lanDefault}" style="width: 100%;">
                    </div>
                </div>
                <div>
                    <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">LAN Subnet CIDR:</label>
                    <input type="text" id="wiz-subnet" class="input-field" value="192.168.1.0/24" style="width: 100%;">
                </div>
            `;
        } else if (this.selectedRole === "controller") {
            const discoveredGw = this.env.discovered_gateways?.[0]?.ip || "";
            container.innerHTML = `
                <div style="margin-bottom: 12px;">
                    <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">Adopt Gateway Router IP (Optional):</label>
                    <input type="text" id="wiz-adopt-gw" class="input-field" value="${discoveredGw}" placeholder="e.g. 192.168.1.1" style="width: 100%;">
                </div>
                <div>
                    <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">Cluster Domain Name:</label>
                    <input type="text" id="wiz-domain" class="input-field" value="roostos.local" style="width: 100%;">
                </div>
            `;
        } else if (this.selectedRole === "workstation") {
            const discoveredCtrl = this.env.discovered_controllers?.[0]?.ip || "roostos.local";
            container.innerHTML = `
                <div style="margin-bottom: 12px;">
                    <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">Controller Host / IP:</label>
                    <input type="text" id="wiz-ctrl-host" class="input-field" value="${discoveredCtrl}" style="width: 100%;">
                </div>
                <div>
                    <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">Pairing Token (Optional):</label>
                    <input type="text" id="wiz-token" class="input-field" placeholder="roost-..." style="width: 100%;">
                </div>
            `;
        }
    },

    async applySetup() {
        const btn = document.getElementById("wizard-apply-btn");
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Applying Configuration...";
        }

        const payload = { role: this.selectedRole };

        if (this.selectedRole === "gateway" || this.selectedRole === "standalone") {
            const wan = document.getElementById("wiz-wan")?.value || "eth0";
            const lanStr = document.getElementById("wiz-lan")?.value || "eth1";
            const subnet = document.getElementById("wiz-subnet")?.value || "192.168.1.0/24";
            const ipPrefix = subnet.split("/")[0].split(".").slice(0, 3).join(".");
            payload.gateway_params = {
                wan_interface: wan,
                lan_interfaces: lanStr.split(",").map(s => s.trim()).filter(Boolean),
                lan_network: subnet,
                lan_ip: `${ipPrefix}.1`,
                dhcp_enabled: true,
                dhcp_start: `${ipPrefix}.100`,
                dhcp_end: `${ipPrefix}.250`,
                dns_servers: ["1.1.1.1", "8.8.8.8"]
            };
        }

        if (this.selectedRole === "controller" || this.selectedRole === "standalone") {
            const adoptIp = document.getElementById("wiz-adopt-gw")?.value?.trim() || null;
            const domain = document.getElementById("wiz-domain")?.value?.trim() || "roostos.local";
            payload.controller_params = {
                cluster_name: "RoostOS Home",
                domain: domain,
                adopted_gateway_ip: adoptIp
            };
        }

        if (this.selectedRole === "workstation") {
            const host = document.getElementById("wiz-ctrl-host")?.value?.trim() || "roostos.local";
            const token = document.getElementById("wiz-token")?.value?.trim() || null;
            payload.workstation_params = {
                controller_host: host,
                join_token: token
            };
        }

        try {
            const res = await fetch("/api/setup/apply", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok && data.success) {
                const modal = document.getElementById("setup-wizard-modal");
                if (modal) modal.remove();
                alert(`Setup completed successfully!\n\n${data.message}`);
                window.location.reload();
            } else {
                alert(`Setup failed: ${data.detail || data.message || "Unknown error"}`);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = "Complete Setup & Apply";
                }
            }
        } catch (e) {
            alert(`Error communicating with setup API: ${e}`);
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Complete Setup & Apply";
            }
        }
    }
};
