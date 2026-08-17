"""Authentication Provider Interfaces and Implementations."""

import grp
import os
import pwd
import sys
from typing import Optional, Protocol, Tuple, runtime_checkable
import pam
from roostos_engine.config import RoostConfig


@runtime_checkable
class AuthProvider(Protocol):
    """Protocol interface defining authentication and role resolution operations."""

    def authenticate(self, username: str, password: str) -> bool:
        """Validates credentials for a user."""
        ...

    def resolve_role(self, username: str, config: RoostConfig) -> Tuple[str, Optional[str]]:
        """Resolves the user's role and associated person profile ID."""
        ...


class PAMAuthProvider:
    """Production authentication provider using Linux Pluggable Authentication Modules (PAM)."""

    def authenticate(self, username: str, password: str) -> bool:
        p = pam.pam()
        try:
            res = p.authenticate(username, password)
            return bool(res)
        except Exception as e:
            print(f"[AUTH:PAM] Authentication exception for user '{username}': {e}", file=sys.stderr)
            return False

    def resolve_role(self, username: str, config: RoostConfig) -> Tuple[str, Optional[str]]:
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
        except (KeyError, Exception):
            pass

        if is_roostos_group_member:
            return "admin", (user_record.person if user_record else None)
        elif user_record:
            return user_record.role, user_record.person
        else:
            return "member", None


class MockAuthProvider:
    """Development and testing authentication provider allowing predefined mock credentials."""

    def __init__(self, mock_users: Optional[dict] = None):
        self.valid_mocks = mock_users or {
            "admin": "password",
            "mom": "password",
            "kid1": "password"
        }

    def authenticate(self, username: str, password: str) -> bool:
        # Accept matched mock password
        return self.valid_mocks.get(username) == password

    def resolve_role(self, username: str, config: RoostConfig) -> Tuple[str, Optional[str]]:
        user_record = next((u for u in config.users if u.username == username), None)
        if user_record:
            return user_record.role, user_record.person
        if username == "admin":
            return "admin", None
        return "member", None
