import os
from typing import List
from roostos_engine.config import RoostConfig

class FirewallManager:
    """Generates rulesets and update parameters for Linux nftables firewall."""

    def __init__(self, config: RoostConfig):
        self.config = config
        # Assign dynamic packet marks starting at 100 to non-default VPN gateways
        self.gateway_marks = {}
        mark_counter = 100
        if hasattr(self.config, "network") and self.config.network:
            for gw in self.config.network.gateways:
                if gw.id != "default":
                    self.gateway_marks[gw.id] = mark_counter
                    mark_counter += 1

    def _get_wan_interface(self) -> str:
        """Finds WAN interface name in configuration. Defaults to 'eth0'."""
        if hasattr(self.config, "network") and self.config.network:
            for interface in self.config.network.interfaces:
                if interface.role == "wan":
                    return interface.name
        return "eth0"

    def compile_ruleset(self) -> str:
        """Generates standard /etc/nftables.conf ruleset contents."""
        wan_if = self._get_wan_interface()
        
        # Identify LAN, Guest, and IoT interfaces
        lan_ifs: List[str] = []
        guest_ifs: List[str] = []
        iot_ifs: List[str] = []
        
        if hasattr(self.config, "network") and self.config.network:
            # Check bridges
            for bridge in self.config.network.bridges:
                if getattr(bridge, "isolate", False):
                    guest_ifs.append(bridge.name)
                else:
                    lan_ifs.append(bridge.name)
                     
            # Check VLAN interfaces
            for vlan in self.config.network.vlans:
                if getattr(vlan, "isolate", True):
                    guest_ifs.append(vlan.name)
                else:
                    lan_ifs.append(vlan.name)

        # Start building the config
        lines = [
            "#!/usr/sbin/nft -f",
            "flush ruleset",
            "",
            "table inet filter {",
            "    # Dynamic MAC set of clients currently quarantined/blocked by schedules",
            "    set blocked_clients {",
            "        type ether_addr",
            "    }",
            "",
            "    chain input {",
            "        type filter hook input priority filter; policy drop;",
            "        ct state established,related accept",
            "        iifname \"lo\" accept",
            "        ip protocol icmp accept",
        ]

        # Allow inputs (SSH, Web Config, DNS, DHCP) from LAN and Guest zones
        # SSH: 22, Cockpit/Web: 9090/443, DNS: 53, DHCP: 67
        all_local_ifs = lan_ifs + guest_ifs + iot_ifs
        for iif in all_local_ifs:
            # IoT is more restricted, only DNS (53) and DHCP (67) are allowed
            if iif in iot_ifs:
                lines.append(f"        iifname \"{iif}\" udp dport {{ 53, 67 }} accept")
                lines.append(f"        iifname \"{iif}\" tcp dport 53 accept")
            else:
                lines.append(f"        iifname \"{iif}\" tcp dport {{ 22, 443, 9090, 53 }} accept")
                lines.append(f"        iifname \"{iif}\" udp dport {{ 53, 67 }} accept")

        # User-defined firewall input rules (from schedules.yaml firewall.rules)
        if hasattr(self.config, "firewall") and self.config.firewall:
            for rule in self.config.firewall.rules:
                if not rule.enabled:
                    continue
                protos = ["tcp", "udp"] if rule.protocol == "tcp/udp" else [rule.protocol]
                for proto in protos:
                    parts = ["       "]
                    if rule.interface != "*":
                        parts.append(f"iifname \"{rule.interface}\"")
                    if rule.source:
                        parts.append(f"ip saddr {rule.source}")
                    parts.append(f"{proto} dport {rule.port}")
                    action = rule.action
                    if action in ("drop", "reject"):
                        safe_name = rule.name.replace(" ", "_")
                        action = f'log prefix "FIREWALL:BLOCKED:{safe_name} " {action}'
                    parts.append(action)
                    lines.append(" ".join(parts))

        lines.extend([
            "        log prefix \"FIREWALL:BLOCKED:Default_Input_Drop \"",
            "    }",
            "",
            "    chain forward {",
            "        type filter hook forward priority filter; policy drop;",
            "        ct state established,related accept",
            "        ",
            "        # Drop traffic from blocked/quarantined clients immediately",
            "        ether saddr @blocked_clients log prefix \"FIREWALL:BLOCKED:Blocked_Client \" drop",
        ])

        # LAN zone: can access WAN and other zones
        for lan in lan_ifs:
            lines.append(f"        iifname \"{lan}\" oifname \"{wan_if}\" accept")
            for guest in guest_ifs:
                lines.append(f"        iifname \"{lan}\" oifname \"{guest}\" accept")
            for iot in iot_ifs:
                lines.append(f"        iifname \"{lan}\" oifname \"{iot}\" accept")

        # Guest zone: can ONLY forward to WAN (cannot access LAN/IoT subnets)
        for guest in guest_ifs:
            lines.append(f"        iifname \"{guest}\" oifname \"{wan_if}\" accept")

        # IoT zone: can ONLY forward to WAN
        for iot in iot_ifs:
            lines.append(f"        iifname \"{iot}\" oifname \"{wan_if}\" accept")

        lines.extend([
            "        log prefix \"FIREWALL:BLOCKED:Default_Forward_Drop \"",
            "    }",
            "",
            "    chain output {",
            "        type filter hook output priority filter; policy accept;",
            "        ct state established,related accept",
            "    }",
            "}",
            "",
            "table inet nat {",
            "    chain prerouting {",
            "        type nat hook prerouting priority dstnat; policy accept;",
        ])

        # 1. DNS Hijacking: redirect port 53 (TCP/UDP) from LAN interfaces to local router address
        # Calculate bridge local addresses to redirect to
        if hasattr(self.config, "network") and self.config.network:
            for bridge in self.config.network.bridges:
                lines.append(f"        iifname \"{bridge.name}\" tcp dport 53 redirect to :53")
                lines.append(f"        iifname \"{bridge.name}\" udp dport 53 redirect to :53")

            for vlan in self.config.network.vlans:
                lines.append(f"        iifname \"{vlan.name}\" tcp dport 53 redirect to :53")
                lines.append(f"        iifname \"{vlan.name}\" udp dport 53 redirect to :53")

        # 2. Block DoT (Port 853) to enforce local DNS filtering profiles
        for iif in all_local_ifs:
            lines.append(f"        iifname \"{iif}\" tcp dport 853 drop")

        # 3. Policy-Based Routing: stamp packets from target devices with gateway overrides
        for dev in self.config.devices:
            if dev.gateway and dev.gateway in self.gateway_marks:
                mark = self.gateway_marks[dev.gateway]
                lines.append(f"        ether saddr {dev.mac} meta mark set {mark}")

        # 4. Dynamic Port Forwards compiled from firewall.yaml
        if hasattr(self.config, "firewall") and self.config.firewall:
            for pf in self.config.firewall.port_forwards:
                proto = pf.protocol.lower()
                lines.append(
                    f"        iifname \"{wan_if}\" {proto} dport {pf.external_port} "
                    f"dnat to {pf.internal_ip}:{pf.internal_port}"
                )

        lines.extend([
            "    }",
            "",
            "    chain postrouting {",
            "        type nat hook postrouting priority srcnat; policy accept;",
            f"        oifname \"{wan_if}\" masquerade",
        ])

        # Masquerade outbound traffic on VPN interfaces
        if hasattr(self.config, "network") and self.config.network:
            for gw in self.config.network.gateways:
                if gw.id != "default":
                    lines.append(f"        oifname \"{gw.interface}\" masquerade")

        lines.extend([
            "    }",
            "}",
            "",
            "# Compatibility with Docker (prevent Docker from dropping LAN forward traffic)",
            "table ip filter {",
            "    chain DOCKER-USER {",
            "        accept",
            "    }",
            "}",
            ""
        ])

        return "\n".join(lines)

    def write_ruleset(self, target_path: str = "/etc/nftables.conf") -> None:
        """Writes compiled ruleset contents to disk target path."""
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
            
        compiled = self.compile_ruleset()
        with open(target_path, "w") as f:
            f.write(compiled)
        print(f"nftables ruleset written successfully to {target_path}")

    def compile_routing_setup_cmds(self) -> List[List[str]]:
        """Compiles Linux policy routing rules and routes for non-default gateways."""
        cmds = []
        if hasattr(self.config, "network") and self.config.network:
            for gw in self.config.network.gateways:
                if gw.id != "default":
                    mark = self.gateway_marks.get(gw.id)
                    if mark:
                        cmds.append(["ip", "route", "replace", "default", "dev", gw.interface, "table", str(mark)])
                        cmds.append(["ip", "rule", "add", "fwmark", str(mark), "table", str(mark)])
        return cmds

    # ==========================================
    # CLI Command Generator Hooks
    # ==========================================

    def get_block_mac_cmd(self, mac: str) -> List[str]:
        """Returns command args to block a client MAC in the active nftables set."""
        return ["nft", "add", "element", "inet", "filter", "blocked_clients", f"{{ {mac.lower()} }}"]

    def get_unblock_mac_cmd(self, mac: str) -> List[str]:
        """Returns command args to unblock a client MAC in the active nftables set."""
        return ["nft", "delete", "element", "inet", "filter", "blocked_clients", f"{{ {mac.lower()} }}"]
