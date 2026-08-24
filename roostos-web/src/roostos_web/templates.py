"""HTML Templates for RoostOS Web Authentication."""

from typing import Optional

LOGIN_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Sign in to RoostOS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            background: radial-gradient(circle at top left, #1e1b4b, #0f172a);
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }
        .card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 32px;
            width: 100%;
            max-width: 380px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
        }
        h2 {
            margin: 0 0 8px 0;
            font-size: 24px;
            font-weight: 600;
            background: linear-gradient(135deg, #a5b4fc, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p {
            color: #94a3b8;
            margin: 0 0 24px 0;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 16px;
        }
        label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            color: #cbd5e1;
            font-weight: 500;
        }
        input, select {
            width: 100%;
            padding: 10px 12px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            box-sizing: border-box;
            transition: all 0.2s;
        }
        select option {
            background: #1e293b;
            color: #fff;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }
        .btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            border: none;
            border-radius: 8px;
            color: #fff;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 8px;
        }
        .btn:hover {
            opacity: 0.95;
            transform: translateY(-1px);
        }
        .error {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #fca5a5;
            padding: 10px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 16px;
        }
    </style>
</head>
<body>
    <div class="card">
        <h2>Sign in to RoostOS</h2>
        <p>Authenticate with your router system login</p>
        
        [ERROR_PLACEHOLDER]

        <form action="/oauth/authorize" method="POST">
            <input type="hidden" name="client_id" value="[CLIENT_ID]">
            <input type="hidden" name="redirect_uri" value="[REDIRECT_URI]">
            
            <div class="form-group">
                <label>Sign in to</label>
                <select name="authority" id="authority">
                    <option value="local" selected>This Device (Local Router)</option>
                    <option value="central">RoostOS Central Identity</option>
                </select>
            </div>

            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required autofocus placeholder="username or .\\localadmin">
            </div>
            
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            
            <button type="submit" class="btn">Sign In</button>
        </form>
    </div>
</body>
</html>"""


def render_login_html(client_id: str, redirect_uri: str, error: Optional[str] = None) -> str:
    """Renders the HTML login page string with error placeholder and query bindings."""
    error_html = f'<div class="error">{error}</div>' if error else ""
    return (
        LOGIN_HTML_TEMPLATE
        .replace("[CLIENT_ID]", client_id)
        .replace("[REDIRECT_URI]", redirect_uri)
        .replace("[ERROR_PLACEHOLDER]", error_html)
    )
