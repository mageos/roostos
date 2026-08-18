window.RoostOS.registerExtension({
    id: "technitium-dns",
    title: "DNS Server",
    render(containerEl) {
        containerEl.innerHTML = `
            <div class="card" style="height: calc(100vh - 180px); display: flex; flex-direction: column; margin-bottom: 0;">
                <h2>Technitium DNS Server Console</h2>
                <div style="flex: 1; border-radius: 8px; overflow: hidden; border: 1px solid var(--card-border);">
                    <iframe src="/api/services/technitium-dns/" style="width: 100%; height: 100%; border: none; background: white;"></iframe>
                </div>
            </div>
        `;
    }
});
