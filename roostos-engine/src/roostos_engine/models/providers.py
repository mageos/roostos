"""Pydantic model definitions for dependency injection container provider bindings."""

from typing import Optional
from pydantic import BaseModel, Field


class ProvidersSettings(BaseModel):
    """Configuration settings determining which implementations are bound in the DI container."""
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this container configuration profile"
    )
    auth_provider: str = Field(
        default="pam",
        description="Authentication provider implementation ('pam', 'mock', 'ldap', 'centralized', 'multi_authority')"
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
        description="Firewall manager implementation ('nftables', 'iptables', 'ebpf', 'mock')"
    )
    dhcp_manager: str = Field(
        default="kea",
        description="DHCP server provider implementation ('kea', 'dnsmasq', 'isc-dhcp', 'mock')"
    )
    dns_manager: str = Field(
        default="local",
        description="DNS resolver and blocking provider implementation ('local', 'technitium', 'dnsmasq', 'mock')"
    )
    network_manager: str = Field(
        default="systemd",
        description="Network interface and VLAN manager implementation ('systemd', 'networkmanager', 'mock')"
    )
    data_seeder: str = Field(
        default="concept1",
        description="Seed data strategy for in-memory repositories ('concept1', 'empty', or directory path)"
    )
    auto_auth: bool = Field(
        default=False,
        description="Automatically grant admin session to unauthenticated requests for exploratory UI testing"
    )


# Alias ContainerConfig to ProvidersSettings for expressive container configuration files
ContainerConfig = ProvidersSettings


class ProvidersConfigFile(BaseModel):
    """Schema for /etc/roostos/providers.yaml or custom container YAML files."""
    providers: Optional[ProvidersSettings] = None
    container: Optional[ContainerConfig] = None
    description: Optional[str] = None


ContainerConfigFile = ProvidersConfigFile
