// RoostOS SysAdmin - Application Install Modal
import { api } from '../api.js';

export function showInstallModal(app, onSuccess) {
    const defaultPort = app.container?.ports?.[0]?.container_port || 8080;
    const modal = document.createElement('div');
    modal.className = 'c1-modal-overlay';
    modal.style.cssText = 'position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 1000;';

    modal.innerHTML = `
        <div class="c1-card" style="width: 440px; max-width: 90vw; background: var(--bg-card); box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; font-size: 16px; font-weight: 700;">Deploy ${app.name}</h3>
                <button class="close-btn" style="background: none; border: none; font-size: 18px; cursor: pointer; color: var(--text-muted);">✕</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <div>
                    <label style="font-size: 12px; font-weight: 600; color: var(--text-muted);">Image</label>
                    <input type="text" class="c1-input" value="${app.container?.image || app.id}" disabled style="width: 100%; opacity: 0.8; font-size: 12px;">
                </div>
                <div>
                    <label style="font-size: 12px; font-weight: 600; color: var(--text-muted);">Host Port</label>
                    <input type="number" id="install-port-input" class="c1-input" value="${defaultPort}" style="width: 100%; font-size: 12px;">
                </div>
                <div style="border-top: 1px solid var(--border-color); padding-top: 10px;">
                    <label style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                        <input type="checkbox" id="install-ingress-check">
                        <span>Expose via Cloud VPS Edge Ingress</span>
                    </label>
                    <input type="text" id="install-domain-input" class="c1-input" placeholder="${app.id}.roostos.lan" style="width: 100%; margin-top: 6px; font-size: 12px; display: none;">
                </div>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px;">
                <button class="btn btn-secondary btn-sm close-btn">Cancel</button>
                <button class="btn btn-primary btn-sm" id="confirm-install-btn">🚀 Deploy Container</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    const ingressCheck = modal.querySelector('#install-ingress-check');
    const domainInput = modal.querySelector('#install-domain-input');
    ingressCheck.onchange = () => {
        domainInput.style.display = ingressCheck.checked ? 'block' : 'none';
    };

    const closeModal = () => modal.remove();
    modal.querySelectorAll('.close-btn').forEach(b => b.onclick = closeModal);

    modal.querySelector('#confirm-install-btn').onclick = async () => {
        const hostPort = parseInt(modal.querySelector('#install-port-input').value, 10) || defaultPort;
        const exposeIngress = ingressCheck.checked;
        const domain = domainInput.value.trim() || undefined;

        const btn = modal.querySelector('#confirm-install-btn');
        btn.disabled = true;
        btn.textContent = '⏳ Deploying...';

        try {
            await api.installCatalogApp({
                app_id: app.id,
                custom_ports: { [defaultPort]: hostPort },
                expose_edge_ingress: exposeIngress,
                ingress_domain: domain
            });
            closeModal();
            onSuccess();
        } catch (e) {
            alert(`Deployment failed: ${e.message}`);
            btn.disabled = false;
            btn.textContent = '🚀 Deploy Container';
        }
    };
}
