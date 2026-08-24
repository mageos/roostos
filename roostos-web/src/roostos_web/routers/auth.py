import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from roostos_engine.repository import ConfigRepository
from roostos_engine.cert_manager import CertificateManager
from roostos_web.auth import (
    create_access_token, get_current_user,
    generate_authorization_code, validate_authorization_record, UserSession
)
from roostos_web.interfaces.auth import AuthProvider
from roostos_web.di import Injected
from roostos_web.templates import render_login_html
from roostos_web.audit import log_auth_success, log_auth_failure, log_cert_auth

router = APIRouter(tags=["auth"])


def render_login_page(client_id: str, redirect_uri: str, error: Optional[str] = None) -> HTMLResponse:
    """Renders the HTML login page with authority selection and error handling."""
    html = render_login_html(client_id, redirect_uri, error=error)
    return HTMLResponse(content=html, status_code=200)


@router.get("/oauth/authorize")
async def oauth_authorize_get(client_id: str, redirect_uri: str):
    """Renders the HTML login page for the authorization flow."""
    return render_login_page(client_id, redirect_uri)


@router.post("/oauth/authorize")
async def oauth_authorize_post(
    request: Request,
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    authority: Optional[str] = Form(None),
    auth_provider: AuthProvider = Injected(AuthProvider)
):
    """Processes credentials via AuthProvider with explicit authority and redirects back to client with authorization code."""
    target_auth = authority or "local"
    if not auth_provider.authenticate(username, password, authority=authority):
        log_auth_failure(username, target_auth, "invalid_credentials", request, method="oauth_authorize")
        return render_login_page(client_id, redirect_uri, error="Incorrect username or password")

    log_auth_success(username, target_auth, "authorized", request, method="oauth_authorize")
    code = generate_authorization_code(username, redirect_uri, authority=authority)
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{separator}code={code}",
        status_code=303
    )


@router.post("/oauth/token")
async def oauth_token(
    request: Request,
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
        record = validate_authorization_record(code, redirect_uri)
        if not record:
            log_auth_failure("unknown", "oauth", "expired_or_invalid_code", request, method="oauth_token")
            raise HTTPException(status_code=400, detail="Invalid or expired authorization code")

        username = record["username"]
        authority = record.get("authority", "local")

        config = repo.get_config()
        role, person = auth_provider.resolve_role(username, config, authority=authority)

        log_auth_success(username, authority, role, request, method="oauth_token")
        token = create_access_token(
            data={"sub": username, "role": role, "person": person, "authority": authority}
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
            err = verification.get('error', 'Invalid certificate')
            log_auth_failure("cert_client", "certificate", err, request, method="client_cert")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Certificate validation failed: {err}"
            )

        subject_cn = verification["subject_cn"]
        scopes = verification.get("scopes", [])
        service_id = subject_cn.replace("service-", "").replace("plugin-", "")

        log_cert_auth(service_id, subject_cn, scopes, request)
        token = create_access_token(
            data={
                "sub": subject_cn,
                "role": "service",
                "authority": "local",
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
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    repo: ConfigRepository = Injected(ConfigRepository),
    auth_provider: AuthProvider = Injected(AuthProvider)
):
    """Authenticates credentials against AuthProvider and returns a signed session token."""
    username = form_data.username
    password = form_data.password

    # Note: username may contain prefix notation (e.g., .\localadmin or DOMAIN\user)
    if not auth_provider.authenticate(username, password):
        log_auth_failure(username, "auto", "invalid_credentials", request, method="password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    config = repo.get_config()
    role, person = auth_provider.resolve_role(username, config)

    log_auth_success(username, "auto", role, request, method="password")
    access_token = create_access_token(
        data={"sub": username, "role": role, "person": person}
    )
    response.set_cookie(key="roostos_token", value=access_token, path="/", httponly=True, samesite="lax")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/auth/me", response_model=UserSession)
async def read_users_me(current_user: UserSession = Depends(get_current_user)):
    """Returns metadata for the currently logged-in session."""
    return current_user
