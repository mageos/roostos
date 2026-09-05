"""Central Identity & Active Directory Management for RoostOS."""

import json
import os
import subprocess
from typing import List, Optional, Tuple, Dict, Any

from roostos_engine.models.identity import (
    DomainUser,
    DomainUserCreate,
    DomainUserUpdate,
    DomainStatus,
    WorkstationEnrollmentInfo,
)
from roostos_engine.repository import ConfigRepository


class IdentityManager:
    """Manages Centralized Identity, Samba AD DC user accounts, and DNS discovery."""

    def __init__(
        self,
        repo: ConfigRepository,
        realm: str = "ROOSTOS.LOCAL",
        workgroup: str = "ROOSTOS",
        dc_hostname: str = "roost-dc",
        state_file: Optional[str] = None
    ):
        self.repo = repo
        self.realm = realm.upper()
        self.workgroup = workgroup.upper()
        self.dc_hostname = dc_hostname
        self.state_file = state_file or os.environ.get(
            "ROOSTOS_IDENTITY_STATE_FILE",
            "/var/lib/roostos/identity/users.json"
        )
        self._in_memory_users: Dict[str, DomainUser] = {}
        self._load_state()

    def _load_state(self) -> None:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    for item in data.get("users", []):
                        u = DomainUser.model_validate(item)
                        self._in_memory_users[u.username] = u
            except Exception as e:
                print(f"Warning: Failed to load identity state file: {e}")
        else:
            # Seed default domain administrator if empty
            admin_user = DomainUser(
                username="Administrator",
                first_name="Domain",
                last_name="Administrator",
                role="admin",
                groups=["Domain Admins", "Enterprise Admins", "Schema Admins"],
                enabled=True
            )
            self._in_memory_users[admin_user.username] = admin_user

    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(
                    {"users": [u.model_dump() for u in self._in_memory_users.values()]},
                    f,
                    indent=2
                )
        except Exception as e:
            print(f"Warning: Failed to persist identity state file: {e}")

    def get_status(self) -> DomainStatus:
        """Returns the current operational status of the domain controller."""
        return DomainStatus(
            realm=self.realm,
            workgroup=self.workgroup,
            dc_hostname=self.dc_hostname,
            provider="samba_ad",
            status="running",
            user_count=len(self._in_memory_users),
            joined_workstations_count=0,
            ldap_port=389,
            ldaps_port=636,
            kerberos_port=88
        )

    def list_users(self) -> List[DomainUser]:
        """Returns all registered domain accounts."""
        return list(self._in_memory_users.values())

    def get_user(self, username: str) -> Optional[DomainUser]:
        """Returns a domain user by username."""
        return self._in_memory_users.get(username)

    def create_user(self, payload: DomainUserCreate) -> DomainUser:
        """Creates a new centralized domain account and syncs with RoostOS person."""
        if payload.username in self._in_memory_users:
            raise ValueError(f"Domain user '{payload.username}' already exists")

        # Validate linked person if specified
        config = self.repo.get_config()
        if payload.person and not any(p.id == payload.person for p in config.people):
            raise ValueError(f"Person ID '{payload.person}' not found in registered people")

        user = DomainUser(
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            role=payload.role,
            person=payload.person,
            groups=payload.groups,
            enabled=True,
            password=payload.password
        )
        self._in_memory_users[user.username] = user
        self._save_state()
        return user

    def update_user(self, username: str, payload: DomainUserUpdate) -> DomainUser:
        """Updates properties of an existing domain account."""
        user = self._in_memory_users.get(username)
        if not user:
            raise ValueError(f"Domain user '{username}' not found")

        if payload.person is not None:
            if payload.person != "":
                config = self.repo.get_config()
                if not any(p.id == payload.person for p in config.people):
                    raise ValueError(f"Person ID '{payload.person}' not found")
                user.person = payload.person
            else:
                user.person = None

        if payload.first_name is not None:
            user.first_name = payload.first_name
        if payload.last_name is not None:
            user.last_name = payload.last_name
        if payload.email is not None:
            user.email = payload.email
        if payload.role is not None:
            user.role = payload.role
        if payload.groups is not None:
            user.groups = payload.groups
        if payload.enabled is not None:
            user.enabled = payload.enabled
        if payload.password:
            user.password = payload.password

        self._in_memory_users[username] = user
        self._save_state()
        return user

    def delete_user(self, username: str) -> bool:
        """Removes a domain account from the directory."""
        if username.lower() == "administrator":
            raise ValueError("The built-in Domain Administrator cannot be deleted")
        if username in self._in_memory_users:
            del self._in_memory_users[username]
            self._save_state()
            return True
        return False

    def reset_password(self, username: str, new_password: str) -> bool:
        """Resets the password for a domain user."""
        user = self._in_memory_users.get(username)
        if not user:
            raise ValueError(f"Domain user '{username}' not found")
        user.password = new_password
        self._save_state()
        return True

    def get_enrollment_info(self, router_ip: str = "192.168.1.1") -> WorkstationEnrollmentInfo:
        """Returns enrollment metadata and one-line join commands for workstations."""
        join_cmd = f"curl -sSf http://{router_ip}:8000/api/v1/identity/join.sh | sudo bash"
        ps_cmd = f"Add-Computer -DomainName '{self.realm}' -Restart"
        return WorkstationEnrollmentInfo(
            realm=self.realm,
            domain=self.realm.lower(),
            dc_ip=router_ip,
            dns_server=router_ip,
            enrollment_command=join_cmd,
            powershell_command=ps_cmd
        )

    def get_dns_srv_records(self, dc_ip: str = "192.168.1.1") -> List[Dict[str, Any]]:
        """Returns the standard DNS SRV records required for Active Directory & Kerberos discovery."""
        domain_lower = self.realm.lower()
        return [
            {"name": f"_ldap._tcp.{domain_lower}", "priority": 0, "weight": 100, "port": 389, "target": f"{self.dc_hostname}.{domain_lower}"},
            {"name": f"_ldap._tcp.dc._msdcs.{domain_lower}", "priority": 0, "weight": 100, "port": 389, "target": f"{self.dc_hostname}.{domain_lower}"},
            {"name": f"_kerberos._tcp.{domain_lower}", "priority": 0, "weight": 100, "port": 88, "target": f"{self.dc_hostname}.{domain_lower}"},
            {"name": f"_kerberos._udp.{domain_lower}", "priority": 0, "weight": 100, "port": 88, "target": f"{self.dc_hostname}.{domain_lower}"},
            {"name": f"_kpasswd._tcp.{domain_lower}", "priority": 0, "weight": 100, "port": 464, "target": f"{self.dc_hostname}.{domain_lower}"},
            {"name": f"_kpasswd._udp.{domain_lower}", "priority": 0, "weight": 100, "port": 464, "target": f"{self.dc_hostname}.{domain_lower}"},
        ]
