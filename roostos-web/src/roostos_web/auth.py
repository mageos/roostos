import os
import sys
import secrets
import threading
import datetime
from typing import Optional
import jwt
import pam
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from roostos_engine.repository import ConfigRepository

SECRET_KEY = os.environ.get("ROOSTOS_JWT_SECRET", "super-secret-dev-key-not-for-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# In-memory storage for short-lived authorization codes
_auth_codes = {}
_auth_codes_lock = threading.Lock()

def generate_authorization_code(username: str, redirect_uri: str) -> str:
    """Generates a secure, 5-minute single-use authorization code."""
    code = secrets.token_urlsafe(32)
    expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    with _auth_codes_lock:
        _auth_codes[code] = {
            "username": username,
            "redirect_uri": redirect_uri,
            "expires_at": expiry
        }
    return code

def validate_authorization_code(code: str, redirect_uri: str) -> Optional[str]:
    """Validates and consumes an authorization code, returning the username if valid."""
    with _auth_codes_lock:
        if code not in _auth_codes:
            return None
        record = _auth_codes.pop(code)  # Single-use (consume instantly)
        
    if record["expires_at"] < datetime.datetime.now(datetime.timezone.utc):
        return None
    if record["redirect_uri"] != redirect_uri:
        return None
    return record["username"]

from fastapi import Cookie

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

class UserSession(BaseModel):
    username: str
    role: str
    person: Optional[str] = None


def authenticate_user(username: str, password: str) -> bool:
    """Authenticates credentials against local PAM or mock dictionary for testing."""
    mock_auth = os.environ.get("ROOSTOS_MOCK_AUTH")
    print(f"[AUTH] Attempt: '{username}', ROOSTOS_MOCK_AUTH='{mock_auth}'", file=sys.stderr)
    if mock_auth == "1":
        valid_mocks = {
            "admin": "password",
            "mom": "password",
            "kid1": "password"
        }
        res = valid_mocks.get(username) == password
        print(f"[AUTH] Mock validation result: {res}", file=sys.stderr)
        return res

    p = pam.pam()
    try:
        res = p.authenticate(username, password)
        print(f"[AUTH] PAM validation result: {res}", file=sys.stderr)
        return res
    except Exception as e:
        print(f"[AUTH] PAM authentication exception: {e}", file=sys.stderr)
        return False


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# To inject ConfigRepository, we need a helper dependency to get the repository instance.
# We will define this helper in main.py, but for now we define a dependency that resolves current user.
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    roostos_token: Optional[str] = Cookie(None)
) -> UserSession:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    actual_token = token or roostos_token
    if not actual_token:
        raise credentials_exception
    try:
        payload = jwt.decode(actual_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        person: Optional[str] = payload.get("person")
        if username is None or role is None:
            raise credentials_exception
        return UserSession(username=username, role=role, person=person)
    except jwt.PyJWTError:
        raise credentials_exception


async def get_current_parent(current_user: UserSession = Depends(get_current_user)) -> UserSession:
    """Restricts access to parent or admin users."""
    if current_user.role not in ("admin", "parent"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to administrative roles."
        )
    return current_user


async def get_current_admin(current_user: UserSession = Depends(get_current_user)) -> UserSession:
    """Restricts access strictly to admin users."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted strictly to system administrators."
        )
    return current_user
