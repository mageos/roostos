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
    image: str = ""
    pull_policy: str = "if_not_present"
    network_mode: str = "bridge"
    ports: List[PortMapping] = Field(default_factory=list)
    volumes: List[VolumeMount] = Field(default_factory=list)
    environment: Dict[str, str] = Field(default_factory=dict)
    restart_policy: str = "unless-stopped"


class SandboxConfig(BaseModel):
    """Security and resource limits for the build sandbox environment."""
    network_required: bool = False
    allowed_endpoints: List[str] = Field(default_factory=list)
    network_justification: str = ""
    user_approved: bool = False
    approved_endpoints: List[str] = Field(default_factory=list)
    allow_network: bool = True
    max_memory_mb: int = 2048
    max_cpu_cores: float = 2.0
    timeout_seconds: int = 600
    no_new_privileges: bool = True
    drop_capabilities: List[str] = Field(default_factory=lambda: ["ALL"])
    disallowed_mounts: List[str] = Field(
        default_factory=lambda: ["/proc", "/sys", "/dev", "/etc"]
    )
    use_build_container: bool = True
    builder_image: str = "roostos-builder:latest"
    containerd_socket: str = "/run/containerd/containerd.sock"
    rootless_build: bool = True
    restricted_network: bool = True
    isolated_network_name: str = "roostos-build-net"


class BuildManifest(BaseModel):
    """Build specification manifest (roost-build.yaml) for RoostOS build engine."""
    schema_version: str = "1.0"
    app_id: Optional[str] = None
    builder: str = "dockerfile"
    context_path: str = "."
    dockerfile: str = "Dockerfile"
    build_args: Dict[str, str] = Field(default_factory=dict)
    target_stage: Optional[str] = None
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    pre_build_validation: bool = True

    def to_source_build_spec(self) -> "SourceBuildSpec":
        return SourceBuildSpec(
            context_path=self.context_path,
            dockerfile=self.dockerfile,
            build_args=self.build_args,
            target_stage=self.target_stage,
            sandbox=self.sandbox,
        )


class SourceBuildSpec(BaseModel):
    """Specification for building an application container from source."""
    git_repo: Optional[str] = None
    git_ref: str = "main"
    context_path: str = "."
    dockerfile: str = "Dockerfile"
    build_args: Dict[str, str] = Field(default_factory=dict)
    target_stage: Optional[str] = None
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)


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
    source_build: Optional[SourceBuildSpec] = None
    container: CatalogContainerSpec
    ingress_preset: Optional[IngressPreset] = None
    catalog_id: str = "official"
    installed: bool = False
    source_repo: Optional[str] = None
    source_ref: str = "main"
    last_commit_built: Optional[str] = None
    latest_commit: Optional[str] = None
    update_available: bool = False
    imported: bool = False


class PackageManifest(BaseModel):
    """Standalone package manifest (roost-app.yaml) for source-based applications."""
    schema_version: str = "1.0"
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: str = "tools"
    author: str = ""
    homepage: str = ""
    architectures: List[str] = Field(default_factory=lambda: ["amd64", "arm64"])
    recommended_role: str = "compute"
    requested_scopes: List[str] = Field(default_factory=list)
    build: Optional[SourceBuildSpec] = None
    container: Optional[CatalogContainerSpec] = None
    ingress_preset: Optional[IngressPreset] = None

    def to_app_entry(self, catalog_id: str = "source") -> CatalogAppEntry:
        """Converts package manifest into a CatalogAppEntry."""
        container_spec = self.container or CatalogContainerSpec(
            image=f"roostos-local/{self.id}:{self.version}",
            pull_policy="never",
            ports=[],
            volumes=[],
            environment={},
        )
        return CatalogAppEntry(
            id=self.id,
            name=self.name,
            version=self.version,
            category=self.category,
            description=self.description,
            author=self.author,
            homepage=self.homepage,
            architectures=self.architectures,
            recommended_role=self.recommended_role,
            requested_scopes=self.requested_scopes,
            source_build=self.build,
            container=container_spec,
            ingress_preset=self.ingress_preset,
            catalog_id=catalog_id,
            imported=(catalog_id == "local"),
        )


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


class ImportFromSourceRequest(BaseModel):
    """Parameters for importing and building an application from source into local catalog."""
    source_url_or_path: str
    git_ref: str = "main"
    dockerfile: str = "Dockerfile"
    context_path: str = "."
    build_args: Dict[str, str] = Field(default_factory=dict)
    sandbox: Optional[SandboxConfig] = None
    approve_network: bool = False
    approved_endpoints: List[str] = Field(default_factory=list)
    app_id_override: Optional[str] = None


class UpdateImportedAppRequest(BaseModel):
    """Parameters for updating an imported application from its git repository."""
    app_id: str
    approve_network: bool = False
    approved_endpoints: List[str] = Field(default_factory=list)
    reinstall_if_running: bool = True


class InstallFromSourceRequest(ImportFromSourceRequest):
    """Parameters for building and installing an application from source (git/local)."""
    target_node_id: Optional[str] = None
    expose_edge_ingress: bool = False
    ingress_domain: Optional[str] = None
    custom_environment: Dict[str, str] = Field(default_factory=dict)
    custom_ports: Dict[int, int] = Field(default_factory=dict)
