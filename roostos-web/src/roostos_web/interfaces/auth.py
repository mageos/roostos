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

    def authenticate(self, username: str, password: str, authority: Optional[str] = None) -> bool:
        """Validates credentials for a user against the requested authority."""
        ...

    def resolve_role(
        self, username: str, config: RoostConfig, authority: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """Resolves the user's role and associated person profile ID."""
        ...


class PAMAuthProvider:
    """Production authentication provider using Linux Pluggable Authentication Modules (PAM)."""

    def authenticate(self, username: str, password: str, authority: Optional[str] = None) -> bool:
        p = pam.pam()
        try:
            res = p.authenticate(username, password)
            return bool(res)
        except Exception as e:
            print(f"[AUTH:PAM] Authentication exception for user '{username}': {e}", file=sys.stderr)
            return False

    def resolve_role(
        self, username: str, config: RoostConfig, authority: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
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

    def __init__(
        self,
        mock_users: Optional[dict] = None,
        central_mock_users: Optional[dict] = None
    ):
        self.valid_mocks = mock_users or {
            "admin": "password",
            "mom": "password",
            "kid1": "password"
        }
        self.central_mocks = central_mock_users or {
            "centraladmin": "centralpass",
            "matt": "domainpass"
        }

    def authenticate(self, username: str, password: str, authority: Optional[str] = None) -> bool:
        auth = (authority or "local").lower()
        if auth == "central":
            return self.central_mocks.get(username) == password
        return self.valid_mocks.get(username) == password

    def resolve_role(
        self, username: str, config: RoostConfig, authority: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        user_record = next((u for u in config.users if u.username == username), None)
        if user_record:
            return user_record.role, user_record.person
        if username == "admin" or username.endswith("admin"):
            return "admin", None
        return "member", None


class MultiAuthorityAuthProvider:
    """Dispatches credentials to Local or Central authorities based on explicit selection or prefix."""

    def __init__(
        self,
        local_provider: AuthProvider,
        central_provider: Optional[AuthProvider] = None,
        default_authority: str = "local"
    ):
        self.local_provider = local_provider
        self.central_provider = central_provider
        self.default_authority = default_authority

    def parse_authority(self, username: str, authority: Optional[str] = None) -> Tuple[str, str]:
        """Parses username prefixes or explicit parameter to determine target authority and clean username."""
        # 1. Prefix: .\user or local\user
        if username.startswith(".\\") or username.lower().startswith("local\\"):
            clean_user = username.split("\\", 1)[1]
            return clean_user, "local"

        # 2. Suffix: user@local
        if username.lower().endswith("@local"):
            clean_user = username.rsplit("@", 1)[0]
            return clean_user, "local"

        # 3. Domain prefix: DOMAIN\user
        if "\\" in username:
            _, clean_user = username.split("\\", 1)
            return clean_user, "central"

        # 4. Explicit authority parameter
        target_auth = (authority or self.default_authority).lower()
        return username, target_auth

    def authenticate(self, username: str, password: str, authority: Optional[str] = None) -> bool:
        clean_user, target_auth = self.parse_authority(username, authority)
        if target_auth == "local" or self.central_provider is None:
            return self.local_provider.authenticate(clean_user, password, authority="local")
        return self.central_provider.authenticate(clean_user, password, authority="central")

    def resolve_role(
        self, username: str, config: RoostConfig, authority: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        clean_user, target_auth = self.parse_authority(username, authority)
        if target_auth == "local" or self.central_provider is None:
            return self.local_provider.resolve_role(clean_user, config, authority="local")
        return self.central_provider.resolve_role(clean_user, config, authority="central")
