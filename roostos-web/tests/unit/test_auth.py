import os
import jwt
import pytest
import datetime
from fastapi import HTTPException
from roostos_web.auth import (
    authenticate_user, create_access_token, get_current_user,
    SECRET_KEY, ALGORITHM, UserSession,
    generate_authorization_code, validate_authorization_code
)

@pytest.fixture(autouse=True)
def enable_mock_auth():
    os.environ["ROOSTOS_MOCK_AUTH"] = "1"
    yield
    del os.environ["ROOSTOS_MOCK_AUTH"]

def test_authenticate_user_success():
    assert authenticate_user("admin", "password") is True
    assert authenticate_user("mom", "password") is True
    assert authenticate_user("kid1", "password") is True

def test_authenticate_user_failed():
    assert authenticate_user("admin", "wrongpassword") is False
    assert authenticate_user("nonexistent", "password") is False

def test_create_access_token():
    payload = {"sub": "mom", "role": "parent", "person": "mom_profile"}
    token = create_access_token(payload)
    
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "mom"
    assert decoded["role"] == "parent"
    assert decoded["person"] == "mom_profile"
    assert "exp" in decoded

@pytest.mark.asyncio
async def test_get_current_user_valid():
    token = create_access_token({"sub": "admin", "role": "admin"})
    user = await get_current_user(token)
    
    assert isinstance(user, UserSession)
    assert user.username == "admin"
    assert user.role == "admin"

@pytest.mark.asyncio
async def test_get_current_user_invalid():
    with pytest.raises(HTTPException) as exc:
        await get_current_user("invalid-token-string")
    assert exc.value.status_code == 401

def test_authorization_code_flow_success():
    redirect_uri = "http://localhost:8000/callback"
    code = generate_authorization_code("mom", redirect_uri)
    assert code is not None
    
    # Validation should succeed
    username = validate_authorization_code(code, redirect_uri)
    assert username == "mom"
    
    # Consumed code should not work again (single use)
    assert validate_authorization_code(code, redirect_uri) is None

def test_authorization_code_flow_invalid_uri():
    redirect_uri = "http://localhost:8000/callback"
    code = generate_authorization_code("mom", redirect_uri)
    
    # Validation with mismatching redirect_uri should fail
    username = validate_authorization_code(code, "http://localhost:8000/wrong-callback")
    assert username is None

@pytest.mark.asyncio
async def test_get_current_user_service_token():
    token = create_access_token({
        "sub": "service-timeguardd",
        "role": "service",
        "service_id": "timeguardd",
        "scopes": ["timeguard:sync", "devices:read"]
    })
    user = await get_current_user(token)
    assert isinstance(user, UserSession)
    assert user.username == "service-timeguardd"
    assert user.role == "service"
    assert user.service_id == "timeguardd"
    assert "timeguard:sync" in user.scopes

@pytest.mark.asyncio
async def test_require_scope_dependency():
    from roostos_web.auth import require_scope
    
    service_user = UserSession(
        username="service-timeguardd",
        role="service",
        service_id="timeguardd",
        scopes=["timeguard:sync"]
    )
    admin_user = UserSession(username="admin", role="admin")

    sync_dep = require_scope("timeguard:sync")
    write_dep = require_scope("firewall:write")

    # Service with matching scope passes
    res = await sync_dep(service_user)
    assert res.username == "service-timeguardd"

    # Admin always passes
    assert (await write_dep(admin_user)).username == "admin"

    # Service without matching scope fails with 403
    with pytest.raises(HTTPException) as exc:
        await write_dep(service_user)
    assert exc.value.status_code == 403

def test_oauth_token_client_certificate_auth(tmp_path):
    from fastapi.testclient import TestClient
    from roostos_web.main import app
    from roostos_engine.cert_manager import CertificateManager
    from roostos_web.routers.auth import get_cert_manager
    from roostos_web.services import get_repository
    from roostos_engine.repository import YAMLConfigRepository

    cert_dir = str(tmp_path / "certs")
    cm = CertificateManager(cert_dir=cert_dir)
    app.dependency_overrides[get_cert_manager] = lambda: cm

    config_dir = str(tmp_path / "config")
    os.makedirs(config_dir, exist_ok=True)
    mock_repo = YAMLConfigRepository(config_dir=config_dir)
    app.dependency_overrides[get_repository] = lambda: mock_repo

    # Issue a service cert
    cert_data = cm.issue_service_cert("timeguardd", ["timeguard:sync", "devices:read"])

    client = TestClient(app)

    # 1. Authenticate with certificate
    resp = client.post("/oauth/token", data={
        "grant_type": "client_certificate",
        "client_certificate": cert_data["cert_pem"]
    })
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert "timeguard:sync" in token_data["scope"]

    # Verify decoded token
    decoded = jwt.decode(token_data["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "service-timeguardd"
    assert decoded["role"] == "service"
    assert "timeguard:sync" in decoded["scopes"]

    # 2. Missing certificate returns 400
    bad_resp = client.post("/oauth/token", data={"grant_type": "client_certificate"})
    assert bad_resp.status_code == 400

    # 3. Invalid/untrusted certificate returns 401
    cm_other = CertificateManager(cert_dir=str(tmp_path / "other_certs"))
    other_cert = cm_other.issue_service_cert("other-service", ["admin"])
    untrusted_resp = client.post("/oauth/token", data={
        "grant_type": "client_certificate",
        "client_certificate": other_cert["cert_pem"]
    })
    assert untrusted_resp.status_code == 401

    app.dependency_overrides.pop(get_cert_manager, None)
    app.dependency_overrides.pop(get_repository, None)



