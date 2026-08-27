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

        # Anti-evasion config settings
        block_doh = False
        block_vpns = False
        block_quic = False
        doh_ips = [
            "1.1.1.1", "1.0.0.1", "162.159.36.1", "162.159.46.1",  # Cloudflare
            "8.8.8.8", "8.8.4.4",                                  # Google
            "9.9.9.9", "149.112.112.112",                          # Quad9
            "208.67.222.222", "208.67.220.220",                    # OpenDNS
            "45.90.28.0/24", "45.90.30.0/24",                      # NextDNS
            "194.242.2.2", "194.242.2.3", "194.242.2.4",          # Mullvad
            "76.76.2.0/24", "76.76.10.0/24"                        # Control D
        ]
        vpn_ips = []
        if hasattr(self.config, "firewall") and self.config.firewall:
            fw = self.config.firewall
            block_doh = getattr(fw, "block_doh", False)
            block_vpns = getattr(fw, "block_vpns", False)
            block_quic = getattr(fw, "block_quic", False)
            if getattr(fw, "custom_doh_ips", None):
                doh_ips.extend(fw.custom_doh_ips)
            if getattr(fw, "custom_vpn_ips", None):
                vpn_ips.extend(fw.custom_vpn_ips)

        # Format elements string for nftables set
        doh_elements = ", ".join(doh_ips)
        vpn_elements_clause = f"\n        elements = {{ {', '.join(vpn_ips)} }}" if vpn_ips else ""

        # Start building the config
        lines = [
            "#!/usr/sbin/nft -f",
            "flush ruleset",
            "",
            "table inet filter {",
            "    # 1. Dynamic MAC set of unknown devices when unregistered_device_policy: deny",
            "    set quarantined {",
            "        type ether_addr",
            "    }",
            "    # 2. Dynamic MAC set of clients blocked by time schedules or screen time limits",
            "    set schedule_blocked {",
            "        type ether_addr",
            "    }",
            "    # 3. Dynamic MAC set of clients blocked permanently by administrator policy",
            "    set admin_blocked {",
            "        type ether_addr",
            "    }",
            "    # Legacy alias for backwards compatibility",
            "    set blocked_clients {",
            "        type ether_addr",
            "    }",
            "    # 4. Anti-Evasion DoH IP Set",
            "    set doh_server_ips {",
            "        type ipv4_addr",
            "        flags interval",
            f"        elements = {{ {doh_elements} }}",
            "    }",
            "    # 5. Anti-Evasion Commercial VPN Endpoint Set",
            "    set vpn_server_ips {",
            "        type ipv4_addr",
            "        flags interval" + vpn_elements_clause,
            "    }",
            "",
            "    chain input {",
            "        type filter hook input priority filter; policy drop;",
            "        ct state established,related accept",
            "        iifname \"lo\" accept",
            "        ip protocol icmp accept",
            "        ether saddr @quarantined log prefix \"FIREWALL:BLOCKED:Quarantine_Input_Drop \" drop",
            "    }",
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
            "        # 1. Drop traffic from quarantined clients completely",
            f"        ether saddr @quarantined log prefix \"FIREWALL:BLOCKED:Quarantined \" drop",
            "        ",
            "        # 2. Drop WAN-bound traffic for schedule-blocked clients (LAN access preserved)",
            f"        ether saddr @schedule_blocked oifname \"{wan_if}\" log prefix \"FIREWALL:BLOCKED:Schedule_Block \" drop",
            "        ",
            "        # 3. Drop WAN-bound traffic for admin-blocked clients",
            f"        ether saddr @admin_blocked oifname \"{wan_if}\" log prefix \"FIREWALL:BLOCKED:Admin_Block \" drop",
            "        ",
            "        # Legacy backward-compatibility drop",
            "        ether saddr @blocked_clients log prefix \"FIREWALL:BLOCKED:Blocked_Client \" drop",
        ])

        # Anti-Evasion Forward Drops
        if block_doh:
            lines.extend([
                "        # Anti-Evasion: Drop direct HTTPS/QUIC connections to known DoH resolver IPs",
                "        ip daddr @doh_server_ips tcp dport 443 log prefix \"FIREWALL:BLOCKED:DoH_Direct_IP \" drop",
                "        ip daddr @doh_server_ips udp dport 443 log prefix \"FIREWALL:BLOCKED:DoH_Direct_IP \" drop",
            ])

        if block_quic:
            lines.append("        # Anti-Evasion: Drop QUIC (HTTP/3) UDP 443 to force TLS/TCP fallback")
            lines.append("        udp dport 443 log prefix \"FIREWALL:BLOCKED:QUIC_Drop \" drop")

        if block_vpns:
            lines.extend([
                "        # Anti-Evasion: Drop Commercial VPN protocols and standard ports",
                "        udp dport { 500, 1194, 1701, 4500, 51820 } log prefix \"FIREWALL:BLOCKED:VPN_Protocol \" drop",
                "        tcp dport { 1194, 1723 } log prefix \"FIREWALL:BLOCKED:VPN_Protocol \" drop",
                "        ip protocol { esp, ah } log prefix \"FIREWALL:BLOCKED:VPN_Protocol \" drop",
            ])
            if vpn_ips:
                lines.append("        ip daddr @vpn_server_ips log prefix \"FIREWALL:BLOCKED:VPN_Endpoint \" drop")


        # Dynamic Zone Forwarding Rules
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
                            dest_ifaces = zone_map[dest_zone_id].interfaces or []
                            for iif in z_ifaces:
                                for oif in dest_ifaces:
                                    lines.append(f'        iifname "{iif}" oifname "{oif}" accept')
                else:
                    # Default policy if allow_zones not explicitly set
                    if z.isolate:
                        for iif in z_ifaces:
                            lines.append(f'        iifname "{iif}" oifname "{wan_if}" accept')
                    else:
                        for iif in z_ifaces:
                            lines.append(f'        iifname "{iif}" oifname "{wan_if}" accept')
                            for oif in all_local_ifs:
                                if oif != iif:
                                    lines.append(f'        iifname "{iif}" oifname "{oif}" accept')
        else:
            # Fallback for simple flat configurations
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

    def get_block_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        """Returns command args to block a client MAC in the active nftables set."""
        return ["nft", "add", "element", "inet", "filter", set_name, f"{{ {mac.lower()} }}"]

    def get_unblock_mac_cmd(self, mac: str, set_name: str = "blocked_clients") -> List[str]:
        """Returns command args to unblock a client MAC in the active nftables set."""
        return ["nft", "delete", "element", "inet", "filter", set_name, f"{{ {mac.lower()} }}"]

    def get_quarantine_mac_cmd(self, mac: str) -> List[str]:
        """Returns command args to quarantine an unknown client MAC."""
        return ["nft", "add", "element", "inet", "filter", "quarantined", f"{{ {mac.lower()} }}"]

    def get_unquarantine_mac_cmd(self, mac: str) -> List[str]:
        """Returns command args to unquarantine a client MAC."""
        return ["nft", "delete", "element", "inet", "filter", "quarantined", f"{{ {mac.lower()} }}"]

    def get_add_doh_ip_cmd(self, ip_cidr: str) -> List[str]:
        """Returns command args to dynamically add a DoH IP/CIDR to the active nftables set."""
        return ["nft", "add", "element", "inet", "filter", "doh_server_ips", f"{{ {ip_cidr} }}"]

    def get_delete_doh_ip_cmd(self, ip_cidr: str) -> List[str]:
        """Returns command args to delete a DoH IP/CIDR from the active nftables set."""
        return ["nft", "delete", "element", "inet", "filter", "doh_server_ips", f"{{ {ip_cidr} }}"]

    def get_add_vpn_ip_cmd(self, ip_cidr: str) -> List[str]:
        """Returns command args to dynamically add a VPN IP/CIDR to the active nftables set."""
        return ["nft", "add", "element", "inet", "filter", "vpn_server_ips", f"{{ {ip_cidr} }}"]

    def get_delete_vpn_ip_cmd(self, ip_cidr: str) -> List[str]:
        """Returns command args to delete a VPN IP/CIDR from the active nftables set."""
        return ["nft", "delete", "element", "inet", "filter", "vpn_server_ips", f"{{ {ip_cidr} }}"]

