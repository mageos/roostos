/**
 * ExtensionRegistry - Dynamic Extension Slot Manager for RoostOS Plugins
 * Handles custom navigation tabs, dashboard widgets, and entity form field slots.
 */
export class ExtensionRegistry {
    constructor() {
        this.extensions = [];
        this.vpnHandlers = {};
        this.widgets = [];
        this.formExtensions = {};
    }

    registerExtension(ext) {
        if (!ext || !ext.id) return;
        if (this.extensions.some(e => e.id === ext.id)) return;
        this.extensions.push(ext);

        const nav = document.querySelector(".sidebar-nav");
        if (!nav) return;

        const btn = document.createElement("button");
        btn.className = "nav-item";
        btn.textContent = ext.title || ext.name || ext.id;
        btn.onclick = () => {
            document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            document.querySelectorAll(".view-pane").forEach(p => p.classList.remove("active"));

            let pane = document.getElementById(`ext-view-${ext.id}`);
            if (!pane) {
                pane = document.createElement("div");
                pane.id = `ext-view-${ext.id}`;
                pane.className = "view-pane";
                const viewContainer = document.querySelector(".view-container");
                if (viewContainer) viewContainer.appendChild(pane);
            }
            pane.classList.add("active");
            const titleEl = document.getElementById("view-title");
            if (titleEl) titleEl.textContent = ext.title || ext.name || ext.id;
            if (typeof ext.render === "function") {
                ext.render(pane);
            }
        };

        const pluginsBtn = Array.from(nav.querySelectorAll("button")).find(b => b.textContent === "Plugins");
        if (pluginsBtn) {
            nav.insertBefore(btn, pluginsBtn);
        } else {
            nav.appendChild(btn);
        }
    }

    registerVpnFormHandler(type, handler) {
        this.vpnHandlers[type] = handler;
    }

    registerWidget(widget) {
        if (widget && widget.id) {
            this.widgets.push(widget);
        }
    }

    registerFormExtension(entityType, renderFieldsFn) {
        if (!this.formExtensions[entityType]) {
            this.formExtensions[entityType] = [];
        }
        this.formExtensions[entityType].push(renderFieldsFn);
    }
}

// Global Singleton Initialization
if (!window.RoostOS) {
    window.RoostOS = new ExtensionRegistry();
}

window.registerExtension = (ext) => window.RoostOS.registerExtension(ext);
window.registerVpnFormHandler = (type, handler) => window.RoostOS.registerVpnFormHandler(type, handler);
