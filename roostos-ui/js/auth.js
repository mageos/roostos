// RoostOS OAuth2 and Session Authentication Coordinator
export function getRedirectUri() {
    return window.location.origin + window.location.pathname;
}

export async function handleAuthCallback() {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (!code) return;

    try {
        const redirectUri = getRedirectUri();
        const body = new URLSearchParams();
        body.append('grant_type', 'authorization_code');
        body.append('code', code);
        body.append('redirect_uri', redirectUri);
        body.append('client_id', 'roostos_admin_ui');

        const resp = await fetch('/oauth/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString()
        });

        if (resp.ok) {
            const data = await resp.json();
            if (data.access_token) {
                localStorage.setItem('roostos_token', data.access_token);
            }
        }
    } catch (err) {
        console.warn('OAuth code exchange encountered error:', err);
    } finally {
        params.delete('code');
        const cleanQuery = params.toString() ? `?${params.toString()}` : '';
        const cleanUrl = window.location.pathname + cleanQuery + window.location.hash;
        window.history.replaceState({}, document.title, cleanUrl);
    }
}

export async function checkAuth() {
    if (typeof window === 'undefined') return true;
    if (window.ROOSTOS_MOCK || localStorage.getItem('roostos_mock') === '1') return true;

    // Check query param first
    await handleAuthCallback();

    const token = localStorage.getItem('roostos_token') || sessionStorage.getItem('roostos_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    try {
        const resp = await fetch('/api/v1/auth/me', { headers, credentials: 'same-origin' });
        if (resp.status === 401) {
            localStorage.removeItem('roostos_token');
            sessionStorage.removeItem('roostos_token');
            const redirectUri = getRedirectUri();
            window.location.href = `/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=${encodeURIComponent(redirectUri)}`;
            return false;
        }
        if (resp.ok) {
            return await resp.json();
        }
    } catch (e) {
        console.warn('Authentication check failed:', e);
    }
    return true;
}

export function logout() {
    localStorage.removeItem('roostos_token');
    sessionStorage.removeItem('roostos_token');
    const redirectUri = getRedirectUri();
    window.location.href = `/oauth/authorize?client_id=roostos_admin_ui&redirect_uri=${encodeURIComponent(redirectUri)}`;
}
