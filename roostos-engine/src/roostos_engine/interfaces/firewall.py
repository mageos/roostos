"""Firewall Provider Protocol and Mock Implementations."""

from typing import List, Optional, Protocol, Set, runtime_checkable
from roostos_engine.config import RoostConfig


@runtime_checkable
class FirewallProvider(Protocol):
    """Protocol for pluggable firewall backends (nftables, iptables, ebpf, mock)."""

    def compile_ruleset(self) -> str:
        """Generates the raw firewall ruleset text."""
        ...

    def write_ruleset(self, target_path: str = "/etc/nftables.conf") -> None:
        """Writes the compiled ruleset to a file."""
        ...

    def compile_routing_setup_cmds(self) -> List[List[str]]:
        """Generates policy routing setup shell commands."""
        ...

    def get_block_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        """Returns command to dynamically block a MAC address."""
        ...

    def get_unblock_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        """Returns command to dynamically unblock a MAC address."""
        ...


class MockFirewallProvider:
    """In-memory mock firewall provider for tests and exploratory UI."""

    def __init__(self, config: Optional[RoostConfig] = None):
        self.config = config
        self.blocked_macs: Set[str] = set()

    def compile_ruleset(self) -> str:
        return "# Mock nftables/firewall ruleset\ntable inet filter { chain forward { type filter hook forward priority 0; policy accept; } }\n"

    def write_ruleset(self, target_path: str = "/etc/nftables.conf") -> None:
        pass

    def compile_routing_setup_cmds(self) -> List[List[str]]:
        return []

    def get_block_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        self.blocked_macs.add(mac)
        return ["echo", f"mock blocked mac {mac}"]

    def get_unblock_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        self.blocked_macs.discard(mac)
        return ["echo", f"mock unblocked mac {mac}"]
