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

