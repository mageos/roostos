import grp
import pwd
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from roostos_engine.repository import ConfigRepository
from roostos_web.auth import (
    authenticate_user, create_access_token, get_current_user,
    generate_authorization_code, validate_authorization_code, UserSession
)
from roostos_web.interfaces.auth import AuthProvider
from roostos_web.di import Injected
from roostos_web.services import get_repository

router = APIRouter(tags=["auth"])

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
        input {
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
        input:focus {
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
                <label>Username</label>
                <input type="text" name="username" required autofocus>
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

def render_login_page(client_id: str, redirect_uri: str, error: Optional[str] = None) -> HTMLResponse:
    error_html = f'<div class="error">{error}</div>' if error else ''
    html = LOGIN_HTML_TEMPLATE.replace("[CLIENT_ID]", client_id).replace("[REDIRECT_URI]", redirect_uri).replace("[ERROR_PLACEHOLDER]", error_html)
    return HTMLResponse(content=html, status_code=200)

def resolve_user_role(username: str, config) -> tuple[str, Optional[str]]:
    """Resolves the user's role and associated person profile, factoring in OS group membership."""
    user_record = next((u for u in config.users if u.username == username), None)
    
    is_roostos_group_member = False
    try:
        roostos_group = grp.getgrnam("roostos")
        target_gid = roostos_group.gr_gid
        user_pw = pwd.getpwnam(username)
        user_gid = user_pw.pw_gid
        gids = os.getgrouplist(username, user_gid)
        if target_gid in gids:
            is_roostos_group_member = True
    except KeyError:
        pass

    if is_roostos_group_member:
        return "admin", (user_record.person if user_record else None)
    elif user_record:
        return user_record.role, user_record.person
    else:
        return "member", None

@router.get("/oauth/authorize")
async def oauth_authorize_get(client_id: str, redirect_uri: str):
    """Renders the HTML login page for the authorization flow."""
    return render_login_page(client_id, redirect_uri)

@router.post("/oauth/authorize")
async def oauth_authorize_post(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    auth_provider: AuthProvider = Injected(AuthProvider)
):
    """Processes credentials via AuthProvider and redirects back to client with authorization code."""
    if not auth_provider.authenticate(username, password):
        return render_login_page(client_id, redirect_uri, error="Incorrect username or password")
    
    code = generate_authorization_code(username, redirect_uri)
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{separator}code={code}",
        status_code=303
    )

import urllib.parse
from roostos_engine.cert_manager import CertificateManager

@router.post("/oauth/token")
async def oauth_token(
    response: Response,
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_certificate: Optional[str] = Form(None),
    client_assertion: Optional[str] = Form(None),
    repo: ConfigRepository = Injected(ConfigRepository),
    cert_mgr: CertificateManager = Injected(CertificateManager),
    auth_provider: AuthProvider = Injected(AuthProvider)
):
    """Exchanges an authorization code or client certificate for a signed JWT access token."""
    if grant_type == "authorization_code":
        if not code or not redirect_uri:
            raise HTTPException(status_code=400, detail="Missing code or redirect_uri")
        username = validate_authorization_code(code, redirect_uri)
        if not username:
            raise HTTPException(status_code=400, detail="Invalid or expired authorization code")
            
        config = repo.get_config()
        role, person = auth_provider.resolve_role(username, config)
     
        token = create_access_token(
            data={"sub": username, "role": role, "person": person}
        )
        response.set_cookie(key="roostos_token", value=token, path="/", httponly=True, samesite="lax")
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600
        }

    elif grant_type in ("client_credentials", "client_certificate", "certificate"):
        raw_cert = client_certificate or client_assertion
        if not raw_cert:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing client certificate for certificate authentication"
            )

        cert_pem = urllib.parse.unquote(raw_cert) if "%" in raw_cert else raw_cert
        verification = cert_mgr.verify_client_cert(cert_pem)
        if not verification.get("valid"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Certificate validation failed: {verification.get('error', 'Invalid certificate')}"
            )

        subject_cn = verification["subject_cn"]
        scopes = verification.get("scopes", [])
        service_id = subject_cn.replace("service-", "").replace("plugin-", "")

        token = create_access_token(
            data={
                "sub": subject_cn,
                "role": "service",
                "service_id": service_id,
                "scopes": scopes,
                "type": "service"
            }
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600,
            "scope": " ".join(scopes)
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")


@router.post("/api/auth/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    repo: ConfigRepository = Depends(get_repository)
):
    """Authenticates credentials against PAM and returns a signed session token."""
    username = form_data.username
    password = form_data.password
 
    if not authenticate_user(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
 
    config = repo.get_config()
    role, person = resolve_user_role(username, config)
 
    access_token = create_access_token(
        data={"sub": username, "role": role, "person": person}
    )
    response.set_cookie(key="roostos_token", value=access_token, path="/", httponly=True, samesite="lax")
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/api/auth/me", response_model=UserSession)
async def read_users_me(current_user: UserSession = Depends(get_current_user)):
    """Returns metadata for the currently logged-in session."""
    return current_user
