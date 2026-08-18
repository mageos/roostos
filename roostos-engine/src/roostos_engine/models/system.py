from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class SystemHTTPSConfig(BaseModel):
    enabled: bool = False
    domain: Optional[str] = None
    email: Optional[str] = None
    acme_provider: Optional[str] = "letsencrypt"
    challenge_type: Optional[str] = "dns-01"
    dns_provider: Optional[str] = None
    dns_credentials_file: Optional[str] = None

class SystemUpdatesRebootWindow(BaseModel):
    days: List[str] = Field(default_factory=lambda: ["Sun"])
    time: str = "03:00"

class SystemUpdatesConfig(BaseModel):
    auto_install: bool = True
    auto_reboot: bool = True
    reboot_window: SystemUpdatesRebootWindow = Field(default_factory=SystemUpdatesRebootWindow)

class SystemDNSConfig(BaseModel):
    forwarders: List[str] = Field(default_factory=list)
    ad_blocking_enabled: bool = False

class ClusterSettingsConfig(BaseModel):
    node_id: Optional[str] = "node-01"
    controller_url: Optional[str] = None
    join_token: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    sync_interval_seconds: int = 30

class SystemSettings(BaseModel):
    hostname: str = "roost-router"
    domain: str = "lan"
    realm: str = "ROOSTOS.LOCAL"  # Active Directory / Kerberos realm equivalent
    timezone: str = "UTC"
    unregistered_device_policy: str = "deny"
    docker_registry: Optional[str] = None
    https: Optional[SystemHTTPSConfig] = Field(default_factory=SystemHTTPSConfig)
    updates: Optional[SystemUpdatesConfig] = Field(default_factory=SystemUpdatesConfig)
    dns: Optional[SystemDNSConfig] = Field(default_factory=SystemDNSConfig)
    cluster: Optional[ClusterSettingsConfig] = Field(default_factory=ClusterSettingsConfig)

    @field_validator("unregistered_device_policy")
    @classmethod
    def validate_unregistered_policy(cls, v: str) -> str:
        if v.lower() not in ("allow", "deny"):
            raise ValueError("unregistered_device_policy must be 'allow' or 'deny'")
        return v.lower()

class UserConfig(BaseModel):
    username: str
    role: str
    person: Optional[str] = None
    ssh_keys: List[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "parent", "member"):
            raise ValueError(f"Role '{v}' must be 'admin', 'parent', or 'member'")
        return v

class SystemConfig(BaseModel):
    system: SystemSettings = Field(default_factory=SystemSettings)
    users: List[UserConfig] = Field(default_factory=list)
