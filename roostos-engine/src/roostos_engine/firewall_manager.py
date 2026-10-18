import os
from typing import List
from roostos_engine.config import RoostConfig


class FirewallManager:
    """Generates rulesets and update parameters for Linux nftables firewall."""

    def __init__(self, config: RoostConfig):
        self.config = config
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

    def _is_local_dns_active(self) -> bool:
        """Determines if a local DNS resolver/plugin is active or filtering enabled."""
        if hasattr(self.config, "plugins") and any(
            getattr(p, "enabled", True) and "dnsServer" in getattr(p, "known_services", []) for p in self.config.plugins
        ):
            return True
        if getattr(getattr(self.config.system, "dns", None), "ad_blocking_enabled", False):
            return True
        if os.environ.get("ROOSTOS_MOCK", "0") != "1" and os.environ.get("ROOSTOS_ETC_DIR") is None:
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.05)
                res = s.connect_ex(("127.0.0.1", 53))
                s.close()
                if res == 0:
                    return True
            except Exception:
                pass
        return False

    def compile_ruleset(self) -> str:
        """Generates standard /etc/nftables.conf ruleset contents."""
        wan_if = self._get_wan_interface()
        lan_ifs, guest_ifs, iot_ifs = [], [], []
        if hasattr(self.config, "network") and self.config.network:
            for bridge in self.config.network.bridges:
                (guest_ifs if getattr(bridge, "isolate", False) else lan_ifs).append(bridge.name)
            for vlan in self.config.network.vlans:
                (guest_ifs if getattr(vlan, "isolate", True) else lan_ifs).append(vlan.name)

        block_doh, block_vpns, block_quic = False, False, False
        doh_ips = [
            "1.1.1.1", "1.0.0.1", "162.159.36.1", "162.159.46.1", "8.8.8.8", "8.8.4.4",
            "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220", "45.90.28.0/24",
            "45.90.30.0/24", "194.242.2.2", "194.242.2.3", "194.242.2.4", "76.76.2.0/24", "76.76.10.0/24"
        ]
        vpn_ips: List[str] = []
        if hasattr(self.config, "firewall") and self.config.firewall:
            fw = self.config.firewall
            block_doh, block_vpns, block_quic = getattr(fw, "block_doh", False), getattr(fw, "block_vpns", False), getattr(fw, "block_quic", False)
            doh_ips.extend(getattr(fw, "custom_doh_ips", None) or [])
            vpn_ips.extend(getattr(fw, "custom_vpn_ips", None) or [])

        doh_elements = ", ".join(doh_ips)
        vpn_elements_clause = f"\n        elements = {{ {', '.join(vpn_ips)} }}" if vpn_ips else ""

        lines = [
            "#!/usr/sbin/nft -f",
            "flush ruleset",
            "",
            "table inet filter {",
            "    set quarantined {\n        type ether_addr\n    }",
            "    set schedule_blocked {\n        type ether_addr\n    }",
            "    set admin_blocked {\n        type ether_addr\n    }",
            "    set blocked_clients {\n        type ether_addr\n    }",
            f"    set doh_server_ips {{\n        type ipv4_addr\n        flags interval\n        elements = {{ {doh_elements} }}\n    }}",
            f"    set vpn_server_ips {{\n        type ipv4_addr\n        flags interval{vpn_elements_clause}\n    }}",
            "",
            "    chain input {",
            "        type filter hook input priority filter; policy drop;",
            "        ct state established,related accept",
            "        iifname \"lo\" accept",
            "        ip protocol icmp accept",
            "        iifname \"wg-edge\" tcp dport { 22, 443, 8000, 9090, 53 } accept",
            "        iifname \"wg-edge\" udp dport { 53, 51820 } accept",
            "        udp dport 51820 accept",
            "        ether saddr @quarantined log prefix \"FIREWALL:BLOCKED:Quarantine_Input_Drop \" drop",
        ]

        all_local_ifs = lan_ifs + guest_ifs + iot_ifs
        for iif in all_local_ifs:
            if iif in iot_ifs:
                lines.append(f"        iifname \"{iif}\" udp dport {{ 53, 67 }} accept")
                lines.append(f"        iifname \"{iif}\" tcp dport 53 accept")
            else:
                lines.append(f"        iifname \"{iif}\" tcp dport {{ 22, 443, 9090, 53 }} accept")
                lines.append(f"        iifname \"{iif}\" udp dport {{ 53, 67 }} accept")

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
            "        ether saddr @quarantined log prefix \"FIREWALL:BLOCKED:Quarantined \" drop",
            f"        ether saddr @schedule_blocked oifname \"{wan_if}\" log prefix \"FIREWALL:BLOCKED:Schedule_Block \" drop",
            f"        ether saddr @admin_blocked oifname \"{wan_if}\" log prefix \"FIREWALL:BLOCKED:Admin_Block \" drop",
            "        ether saddr @blocked_clients log prefix \"FIREWALL:BLOCKED:Blocked_Client \" drop",
        ])

        if block_doh:
            lines.extend([
                "        ip daddr @doh_server_ips tcp dport 443 log prefix \"FIREWALL:BLOCKED:DoH_Direct_IP \" drop",
                "        ip daddr @doh_server_ips udp dport 443 log prefix \"FIREWALL:BLOCKED:DoH_Direct_IP \" drop",
            ])

        if block_quic:
            lines.append("        udp dport 443 log prefix \"FIREWALL:BLOCKED:QUIC_Drop \" drop")

        if block_vpns:
            lines.extend([
                "        udp dport { 500, 1194, 1701, 4500, 51820 } log prefix \"FIREWALL:BLOCKED:VPN_Protocol \" drop",
                "        tcp dport { 1194, 1723 } log prefix \"FIREWALL:BLOCKED:VPN_Protocol \" drop",
                "        ip protocol { esp, ah } log prefix \"FIREWALL:BLOCKED:VPN_Protocol \" drop",
            ])
            if vpn_ips:
                lines.append("        ip daddr @vpn_server_ips log prefix \"FIREWALL:BLOCKED:VPN_Endpoint \" drop")

        # Bidirectional forwarding between Main LAN interfaces and Edge Gateway tunnel (wg-edge)
        for lan in lan_ifs:
            lines.append(f'        iifname "{lan}" oifname "wg-edge" accept')
            lines.append(f'        iifname "wg-edge" oifname "{lan}" accept')

        zones_defined = hasattr(self.config, "network") and self.config.network and bool(self.config.network.zones)
        if zones_defined:
            zone_map = {z.id: z for z in self.config.network.zones}
            for z in self.config.network.zones:
                if z.id == "wan":
                    continue
                z_ifaces = z.interfaces or []
                if z.allow_zones:
                    for dest_zone_id in z.allow_zones:
                        if dest_zone_id == "wan":
                            for iif in z_ifaces:
                                lines.append(f'        iifname "{iif}" oifname "{wan_if}" accept')
                        elif dest_zone_id in zone_map:
                            for iif in z_ifaces:
                                for oif in (zone_map[dest_zone_id].interfaces or []):
                                    lines.append(f'        iifname "{iif}" oifname "{oif}" accept')
                else:
                    for iif in z_ifaces:
                        lines.append(f'        iifname "{iif}" oifname "{wan_if}" accept')
                        if not z.isolate:
                            for oif in all_local_ifs:
                                if oif != iif:
                                    lines.append(f'        iifname "{iif}" oifname "{oif}" accept')
        else:
            for lan in lan_ifs:
                lines.append(f'        iifname "{lan}" oifname "{wan_if}" accept')
                for guest in guest_ifs:
                    lines.append(f'        iifname "{lan}" oifname "{guest}" accept')
                for iot in iot_ifs:
                    lines.append(f'        iifname "{lan}" oifname "{iot}" accept')
            for guest in guest_ifs:
                lines.append(f'        iifname "{guest}" oifname "{wan_if}" accept')
            for iot in iot_ifs:
                lines.append(f'        iifname "{iot}" oifname "{wan_if}" accept')

        lines.extend([
            "        log prefix \"FIREWALL:BLOCKED:Default_Forward_Drop \"",
            "    }",
            "",
            "    chain output {\n        type filter hook output priority filter; policy accept;\n        ct state established,related accept\n    }",
            "}",
            "",
            "table inet nat {",
            "    chain prerouting {",
            "        type nat hook prerouting priority dstnat; policy accept;",
        ])

        if self._is_local_dns_active():
            if hasattr(self.config, "network") and self.config.network:
                for obj in [*self.config.network.bridges, *self.config.network.vlans]:
                    lines.append(f'        iifname "{obj.name}" tcp dport 53 redirect to :53')
                    lines.append(f'        iifname "{obj.name}" udp dport 53 redirect to :53')
            for iif in all_local_ifs:
                lines.append(f'        iifname "{iif}" tcp dport 853 drop')
        else:
            forwarders = getattr(getattr(self.config.system, "dns", None), "forwarders", [])
            primary_dns = forwarders[0] if forwarders else "1.1.1.1"
            if hasattr(self.config, "network") and self.config.network:
                for obj in [*self.config.network.bridges, *self.config.network.vlans]:
                    ip_addr = obj.ip.split("/")[0]
                    lines.append(f'        iifname "{obj.name}" ip daddr {ip_addr} tcp dport 53 dnat to {primary_dns}:53')
                    lines.append(f'        iifname "{obj.name}" ip daddr {ip_addr} udp dport 53 dnat to {primary_dns}:53')

        for dev in self.config.devices:
            if dev.gateway and dev.gateway in self.gateway_marks:
                lines.append(f"        ether saddr {dev.mac} meta mark set {self.gateway_marks[dev.gateway]}")

        if hasattr(self.config, "firewall") and self.config.firewall:
            for pf in self.config.firewall.port_forwards:
                lines.append(f'        iifname "{wan_if}" {pf.protocol.lower()} dport {pf.external_port} dnat to {pf.internal_ip}:{pf.internal_port}')

        lines.extend([
            "    }",
            "",
            "    chain postrouting {",
            "        type nat hook postrouting priority srcnat; policy accept;",
            f"        oifname \"{wan_if}\" masquerade",
        ])

        if hasattr(self.config, "network") and self.config.network:
            for gw in self.config.network.gateways:
                if gw.id != "default":
                    lines.append(f"        oifname \"{gw.interface}\" masquerade")

        lines.extend([
            "    }",
            "}",
            "",
            "table ip filter {\n    chain DOCKER-USER {\n        accept\n    }\n}\n",
        ])
        return "\n".join(lines)

    def write_ruleset(self, target_path: str = "/etc/nftables.conf") -> None:
        """Writes compiled ruleset contents to disk target path."""
        if os.path.dirname(target_path):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w") as f:
            f.write(self.compile_ruleset())
        print(f"nftables ruleset written successfully to {target_path}")

    def compile_routing_setup_cmds(self) -> List[List[str]]:
        """Compiles Linux policy routing rules and routes for non-default gateways."""
        cmds = []
        if hasattr(self.config, "network") and self.config.network:
            for gw in self.config.network.gateways:
                mark = self.gateway_marks.get(gw.id) if gw.id != "default" else None
                if mark:
                    cmds.append(["ip", "route", "replace", "default", "dev", gw.interface, "table", str(mark)])
                    cmds.append(["ip", "rule", "add", "fwmark", str(mark), "table", str(mark)])
        return cmds

    def get_block_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        return ["nft", "add", "element", "inet", "filter", set_name, f"{{ {mac.lower()} }}"]

    def get_unblock_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        return ["nft", "delete", "element", "inet", "filter", set_name, f"{{ {mac.lower()} }}"]

    def get_quarantine_mac_cmd(self, mac: str) -> List[str]:
        return ["nft", "add", "element", "inet", "filter", "quarantined", f"{{ {mac.lower()} }}"]

    def get_unquarantine_mac_cmd(self, mac: str) -> List[str]:
        return ["nft", "delete", "element", "inet", "filter", "quarantined", f"{{ {mac.lower()} }}"]

    def get_add_doh_ip_cmd(self, ip_cidr: str) -> List[str]:
        return ["nft", "add", "element", "inet", "filter", "doh_server_ips", f"{{ {ip_cidr} }}"]

    def get_delete_doh_ip_cmd(self, ip_cidr: str) -> List[str]:
        return ["nft", "delete", "element", "inet", "filter", "doh_server_ips", f"{{ {ip_cidr} }}"]

    def get_add_vpn_ip_cmd(self, ip_cidr: str) -> List[str]:
        return ["nft", "add", "element", "inet", "filter", "vpn_server_ips", f"{{ {ip_cidr} }}"]

    def get_delete_vpn_ip_cmd(self, ip_cidr: str) -> List[str]:
        return ["nft", "delete", "element", "inet", "filter", "vpn_server_ips", f"{{ {ip_cidr} }}"]

