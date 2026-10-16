"""Network Interface and VLAN Manager Protocol."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from roostos_engine.config import RoostConfig


@runtime_checkable
class NetworkProvider(Protocol):
    """Protocol for network interface and VLAN backends (systemd-networkd, NetworkManager, mock)."""

    def apply_interfaces(self, config: RoostConfig) -> bool:
        """Applies interface, bridge, and bond configurations."""
        ...

    def apply_vlans(self, config: RoostConfig) -> bool:
        """Configures VLAN tags, interfaces, and isolated subnet boundaries."""
        ...

    def get_interface_states(self) -> List[Dict[str, Any]]:
        """Returns current hardware and virtual interface link states."""
        ...


class MockNetworkProvider:
    """In-memory mock network provider."""

    def __init__(self, config: Optional[RoostConfig] = None):
        self.config = config

    def apply_interfaces(self, config: RoostConfig) -> bool:
        return True

    def apply_vlans(self, config: RoostConfig) -> bool:
        return True

    def get_interface_states(self) -> List[Dict[str, Any]]:
        return [
            {"name": "eth0", "role": "wan", "carrier": True, "speed_mbps": 1000},
            {"name": "eth1", "role": "lan", "carrier": True, "speed_mbps": 1000},
            {"name": "br0", "role": "lan_bridge", "carrier": True, "speed_mbps": 1000},
        ]
