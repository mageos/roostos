"""Shared Firewall domain service for RoostOS."""

from typing import List, Dict, Any, Optional
from roostos_engine.config import (
    FirewallConfig,
    FirewallSettings,
    InputRuleConfig,
    PortForwardConfig,
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class FirewallService:
    """Application service for managing firewall rules, port forwards, and security shields."""

    def __init__(self, repo: ConfigRepository, dbus: Optional[RoostClient] = None) -> None:
        self.repo = repo
        self.dbus = dbus

    def get_firewall_config(self) -> FirewallConfig:
        config = self.repo.get_config()
        return FirewallConfig(firewall=config.firewall)

    def save_firewall_config(self, config: FirewallConfig) -> None:
        self.repo.save_firewall_config(config)

    def add_port_forward(
        self,
        name: str,
        proto: str,
        ext_port: int,
        int_ip: str,
        int_port: int,
        description: str = "",
        enabled: bool = True,
    ) -> PortForwardConfig:
        """Adds or updates a destination NAT port forwarding rule."""
        fw_cfg = self.get_firewall_config()
        fw = fw_cfg.firewall
        pf = next((p for p in fw.port_forwards if p.name == name), None)
        if pf:
            pf.protocol = proto
            pf.external_port = ext_port
            pf.internal_ip = int_ip
            pf.internal_port = int_port
            pf.enabled = enabled
            target = pf
        else:
            target = PortForwardConfig(
                name=name,
                protocol=proto,
                external_port=ext_port,
                internal_ip=int_ip,
                internal_port=int_port,
                enabled=enabled,
            )
            fw.port_forwards.append(target)
        self.save_firewall_config(fw_cfg)
        return target

    def delete_port_forward(self, name: str) -> bool:
        """Removes a port forwarding rule by name."""
        fw_cfg = self.get_firewall_config()
        fw = fw_cfg.firewall
        orig_len = len(fw.port_forwards)
        fw.port_forwards = [p for p in fw.port_forwards if p.name != name]
        if len(fw.port_forwards) == orig_len:
            return False
        self.save_firewall_config(fw_cfg)
        return True

    def add_rule(
        self,
        name: str,
        protocol: str = "tcp",
        port: int = 80,
        source: str = "",
        action: str = "accept",
        enabled: bool = True,
        interface: str = "*",
    ) -> InputRuleConfig:
        """Adds or updates an input firewall filter rule."""
        fw_cfg = self.get_firewall_config()
        fw = fw_cfg.firewall
        rule = next((r for r in fw.rules if r.name == name), None)
        if rule:
            rule.protocol = protocol
            rule.port = port
            rule.source = source or None
            rule.action = action
            rule.enabled = enabled
            rule.interface = interface
            target = rule
        else:
            target = InputRuleConfig(
                name=name,
                interface=interface,
                protocol=protocol,
                port=port,
                source=source or None,
                action=action,
                enabled=enabled,
            )
            fw.rules.append(target)
        self.save_firewall_config(fw_cfg)
        return target

    def delete_rule(self, name: str) -> bool:
        """Removes a firewall rule by name."""
        fw_cfg = self.get_firewall_config()
        fw = fw_cfg.firewall
        orig_len = len(fw.rules)
        fw.rules = [r for r in fw.rules if r.name != name]
        if len(fw.rules) == orig_len:
            return False
        self.save_firewall_config(fw_cfg)
        return True
