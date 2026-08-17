"""Pydantic model definitions for dependency injection provider bindings."""

from typing import Optional
from pydantic import BaseModel, Field


class ProvidersSettings(BaseModel):
    """Configuration settings determining which implementations are bound in the DI container."""
    auth_provider: str = Field(
        default="pam",
        description="Authentication provider implementation ('pam', 'mock', 'ldap')"
    )
    config_repository: str = Field(
        default="staging",
        description="Configuration repository implementation ('staging', 'yaml', 'memory')"
    )
    system_client: str = Field(
        default="dbus",
        description="System IPC client implementation ('dbus', 'mock')"
    )
    cert_manager: str = Field(
        default="standard",
        description="Certificate manager implementation ('standard', 'mock')"
    )
    firewall_manager: str = Field(
        default="nftables",
        description="Firewall manager implementation ('nftables', 'mock')"
    )


class ProvidersConfigFile(BaseModel):
    """Schema for /etc/roostos/providers.yaml."""
    providers: ProvidersSettings = Field(default_factory=ProvidersSettings)
