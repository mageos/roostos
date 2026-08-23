from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """Result of an executed command on a network node."""
    command: str = Field(description="Command that was executed")
    exit_code: int = Field(description="Exit code of the process")
    stdout: str = Field(default="", description="Standard output string")
    stderr: str = Field(default="", description="Standard error string")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")

    @property
    def success(self) -> bool:
        """Returns True if the command exited with code 0."""
        return self.exit_code == 0


class SocketProbeResult(BaseModel):
    """Result of a socket connection attempt from a node."""
    host: str
    port: int
    protocol: str = "tcp"
    connected: bool
    error_message: Optional[str] = None
    response_data: Optional[str] = None
    latency_ms: float = 0.0


class NodeInfo(BaseModel):
    """Metadata describing a container node in the test network."""
    name: str
    container_name: str
    role: str
    ip_address: str
    mac_address: Optional[str] = None
    gateway: Optional[str] = None
    network_interface: str = "eth0"


class ScenarioConfig(BaseModel):
    """Configuration for a specific deployment scenario."""
    name: str
    description: str
    config_dir: str
    expected_interfaces: List[str] = Field(default_factory=list)
    gateway_id: str = "default"
    custom_environment: Dict[str, str] = Field(default_factory=dict)
