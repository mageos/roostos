"""Pydantic models for Centralized Domain Identity and User Management."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class DomainUser(BaseModel):
    """Represents a centralized domain account stored in Samba AD / LDAP."""
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "member"
    person: Optional[str] = None
    groups: List[str] = Field(default_factory=list)
    enabled: bool = True
    locked: bool = False
    password: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "parent", "member"):
            raise ValueError(f"Role '{v}' must be 'admin', 'parent', or 'member'")
        return v


class DomainUserCreate(BaseModel):
    """Payload for creating a new centralized domain account."""
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "member"
    person: Optional[str] = None
    groups: List[str] = Field(default_factory=list)


class DomainUserUpdate(BaseModel):
    """Payload for updating an existing centralized domain account."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    person: Optional[str] = None
    groups: Optional[List[str]] = None
    enabled: Optional[bool] = None
    password: Optional[str] = None


class DomainPasswordReset(BaseModel):
    """Payload for resetting a user's domain password."""
    new_password: str


class DomainGroup(BaseModel):
    """Represents a directory group."""
    name: str
    description: Optional[str] = None
    members: List[str] = Field(default_factory=list)


class DomainStatus(BaseModel):
    """Runtime status of the centralized domain controller."""
    realm: str
    workgroup: str
    dc_hostname: str
    provider: str = "samba_ad"
    status: str = "running"
    user_count: int = 0
    joined_workstations_count: int = 0
    ldap_port: int = 389
    ldaps_port: int = 636
    kerberos_port: int = 88


class WorkstationEnrollmentInfo(BaseModel):
    """Information and script payload to enroll client workstations."""
    realm: str
    domain: str
    dc_ip: str
    dns_server: str
    enrollment_command: str
    powershell_command: str
