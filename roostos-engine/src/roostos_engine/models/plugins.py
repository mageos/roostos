from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, model_validator

class PortMapping(BaseModel):
    host_port: int
    container_port: int
    protocol: str = "tcp"

class VolumeMount(BaseModel):
    host_path: str
    container_path: str
    mode: str = "rw"

class ContainerConfig(BaseModel):
    name: str
    image: str
    ports: List[PortMapping] = Field(default_factory=list)
    volumes: List[VolumeMount] = Field(default_factory=list)
    environment: Dict[str, str] = Field(default_factory=dict)

class PluginConfig(BaseModel):
    id: str
    name: str
    type: str = "application"  # "core_service" or "application"
    enabled: bool = False
    network_mode: str = "bridge"  # "bridge", "host", or "service:<name>"
    requested_scopes: List[str] = Field(default_factory=list)
    containers: List[ContainerConfig] = Field(default_factory=list)
    ui_entrypoint: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    known_services: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def handle_known_service_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            services = []
            for key in ["known_services", "knownServices", "known_service", "knownService"]:
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        services.extend(val)
                    elif isinstance(val, str):
                        services.append(val)
            if services:
                data["known_services"] = list(dict.fromkeys(services))
        return data

class PluginsConfig(BaseModel):
    plugins: List[PluginConfig] = Field(default_factory=list)
