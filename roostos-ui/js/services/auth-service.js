class AuthService {
    getToken() {
        return localStorage.getItem("roostos_token");
    }

    setToken(token) {
        localStorage.setItem("roostos_token", token);
    }

    clearToken() {
        localStorage.removeItem("roostos_token");
    }

    async apiFetch(url, options = {}) {
        const token = this.getToken();
        const headers = options.headers || {};
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(url, { ...options, headers });
        if (res.status === 401) {
            this.clearToken();
            const urlParams = new URLSearchParams(window.location.search);
            const code = urlParams.get("code");
            if (!code) {
                window.location.href = "/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=" + encodeURIComponent(window.location.origin + "/");
            }
        }
        return res;
    }

    handleAuthentication() {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get("code");
        const token = this.getToken();

        if (code) {
            this.exchangeAuthCode(code);
            return false;
        }

        if (!token) {
            window.location.href = "/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=" + encodeURIComponent(window.location.origin + "/");
            return false;
        }
        return true;
    }

    async exchangeAuthCode(code) {
        try {
            const res = await fetch("/oauth/token", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: new URLSearchParams({
                    grant_type: "authorization_code",
                    code: code,
                    redirect_uri: window.location.origin + "/",
                    client_id: "roostos_admin_ui"
                })
            });

            if (res.ok) {
                const data = await res.json();
                this.setToken(data.access_token);
                window.history.replaceState({}, document.title, "/");
                if (window.init) window.init();
            } else {
                alert("OAuth token exchange failed.");
                window.location.href = "/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=" + encodeURIComponent(window.location.origin + "/");
            }
        } catch (e) {
            console.error(e);
            alert("Failed to connect to authorization server.");
        }
    }

    logout() {
        this.clearToken();
        window.location.href = "/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=" + encodeURIComponent(window.location.origin + "/");
    }
}

// Global service instance
window.authService = new AuthService();

// Backward compatibility bindings
window.apiFetch = (url, opts) => window.authService.apiFetch(url, opts);
window.handleAuthentication = () => window.authService.handleAuthentication();
window.logout = () => window.authService.logout();
