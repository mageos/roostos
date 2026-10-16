"""DHCP Provider Protocol and Mock Implementations."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from roostos_engine.config import RoostConfig


@runtime_checkable
class DHCPProvider(Protocol):
    """Protocol for pluggable DHCP server backends (kea, dnsmasq, isc-dhcp, mock)."""

    def write_config(self) -> None:
        """Writes the compiled DHCP configuration to target service directory."""
        ...

    def compile_config(self) -> Any:
        """Compiles the internal DHCP configuration structure."""
        ...


class MockDHCPProvider:
    """In-memory mock DHCP provider."""

    def __init__(self, config: Optional[RoostConfig] = None, target_path: Optional[str] = None):
        self.config = config
        self.target_path = target_path

    def write_config(self) -> None:
        pass

    def compile_config(self) -> Dict[str, Any]:
        return {
            "Dhcp4": {
                "interfaces-config": {"interfaces": ["br0"]},
                "subnet4": [
                    {
                        "subnet": "192.168.1.0/24",
                        "pools": [{"pool": "192.168.1.100 - 192.168.1.200"}],
                    }
                ],
            }
        }
