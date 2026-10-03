"""Data models for RoostOS decentralized application catalog and packaging."""

from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

from roostos_engine.models.plugins import PortMapping, VolumeMount


class PullPolicy(str, Enum):
    ALWAYS = "always"
    IF_NOT_PRESENT = "if_not_present"
    NEVER = "never"


class IngressPreset(BaseModel):
    """Suggested Edge Gateway ingress proxy settings for an application."""
    target_port: int
    suggested_subdomain: str = ""
    ssl_required: bool = True


class CatalogContainerSpec(BaseModel):
    """Container runtime specification for catalog application."""
    image: str
    pull_policy: str = "if_not_present"
    network_mode: str = "bridge"
    ports: List[PortMapping] = Field(default_factory=list)
    volumes: List[VolumeMount] = Field(default_factory=list)
    environment: Dict[str, str] = Field(default_factory=dict)
    restart_policy: str = "unless-stopped"


class CatalogAppEntry(BaseModel):
    """Metadata and deployment spec for an application published in a catalog."""
    id: str
    name: str
    version: str
    category: str = "tools"
    description: str
    icon: str = ""
    author: str = ""
    homepage: str = ""
    architectures: List[str] = Field(default_factory=lambda: ["amd64", "arm64"])
    recommended_role: str = "compute"  # "compute", "gateway", or "any"
    requested_scopes: List[str] = Field(default_factory=list)
    container: CatalogContainerSpec
    ingress_preset: Optional[IngressPreset] = None
    catalog_id: str = "official"
    installed: bool = False


class CatalogIndex(BaseModel):
    """Manifest of an application catalog repository (index.json)."""
    catalog_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    maintainer: str = ""
    homepage: str = ""
    applications: List[CatalogAppEntry] = Field(default_factory=list)


class CatalogSourceConfig(BaseModel):
    """Configuration definition for a remote or local catalog repository source."""
    id: str
    name: str
    url: str
    enabled: bool = True
    public_key: Optional[str] = None  # Ed25519 public key hex or base64
    allow_insecure: bool = False
    last_updated: Optional[str] = None


class InstallAppRequest(BaseModel):
    """Parameters for installing an application from a catalog."""
    app_id: str
    catalog_id: str = "official"
    target_node_id: Optional[str] = None
    expose_edge_ingress: bool = False
    ingress_domain: Optional[str] = None
    custom_environment: Dict[str, str] = Field(default_factory=dict)
    custom_ports: Dict[int, int] = Field(default_factory=dict)
