import os
import sys
import subprocess
from roostos_engine.subsystems.base import Subsystem

class NetworkInterfacesSubsystem(Subsystem):
    name = "network"
    dependencies = ["system_settings"]

    def update(self) -> None:
        """Generates systemd-networkd configuration files dynamically from network settings."""
        network_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR")
        if not network_dir:
            if self.mock:
                return
            network_dir = "/etc/systemd/network"

        if not os.path.isdir(network_dir):
            try:
                os.makedirs(network_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create network dir {network_dir}: {e}", file=sys.stderr)
                return

        try:
            print(f"Generating systemd-networkd configurations in {network_dir}...")
            generated_files = set()

            # 1. Generate Bridge NetDev and Network configs
            for bridge in self.config.network.bridges:
                netdev_file = f"20-{bridge.name}.netdev"
                netdev_path = os.path.join(network_dir, netdev_file)
                generated_files.add(netdev_file)
                
                with open(netdev_path, "w") as f:
                    f.write(f"[NetDev]\nName={bridge.name}\nKind=bridge\n")

                network_file = f"20-{bridge.name}.network"
                network_path = os.path.join(network_dir, network_file)
                generated_files.add(network_file)
                
                with open(network_path, "w") as f:
                    f.write(f"[Match]\nName={bridge.name}\n\n[Network]\nAddress={bridge.ip}\nIPMasquerade=yes\nIPForward=yes\n")

            # 2. Generate Physical Interface configs
            etc_dir = os.environ.get("ROOSTOS_ETC_DIR", "/etc")
            pppoe_active = False
            pppoe_iface = ""

            for interface in self.config.network.interfaces:
                if interface.network == "wan":
                    target_iface_name = interface.name
                    
                    # If VLAN tag is present, create a netdev and write network config for parent
                    if interface.vlan_tag:
                        target_iface_name = f"{interface.name}.{interface.vlan_tag}"
                        
                        netdev_file = f"10-{interface.name}.{interface.vlan_tag}.netdev"
                        netdev_path = os.path.join(network_dir, netdev_file)
                        generated_files.add(netdev_file)
                        with open(netdev_path, "w") as f:
                            f.write(f"[NetDev]\nName={target_iface_name}\nKind=vlan\n\n[VLAN]\nId={interface.vlan_tag}\n")
                        
                        # Parent interface only needs matching and linking the VLAN
                        parent_file = f"10-{interface.name}.network"
                        parent_path = os.path.join(network_dir, parent_file)
                        generated_files.add(parent_file)
                        with open(parent_path, "w") as f:
                            f.write(f"[Match]\nName={interface.name}\nKernelCommandLine=!nfsroot\n\n[Network]\nVLAN={target_iface_name}\n")
                    
                    network_file = f"10-{target_iface_name}.network"
                    network_path = os.path.join(network_dir, network_file)
                    generated_files.add(network_file)
                    
                    with open(network_path, "w") as f:
                        if interface.protocol == "pppoe":
                            # Standard systemd-networkd profile to just bring the physical/VLAN link UP
                            f.write(f"[Match]\nName={target_iface_name}\n\n[Network]\nKeepConfiguration=yes\nLinkLocalAddressing=no\n")
                            pppoe_active = True
                            pppoe_iface = target_iface_name
                        else:
                            f.write(f"[Match]\nName={target_iface_name}\nKernelCommandLine=!nfsroot\n\n[Network]\n")
                            if interface.protocol == "dhcp" or (interface.protocol is None and interface.dhcp is not False):
                                if interface.ipv6 is False:
                                    f.write("DHCP=ipv4\nIPv6AcceptRA=no\nLinkLocalAddressing=ipv4\n")
                                else:
                                    f.write("DHCP=yes\nIPv6AcceptRA=yes\n")
                            else:  # Static config
                                if interface.ip:
                                    f.write(f"Address={interface.ip}\n")
                                if interface.gateway:
                                    f.write(f"Gateway={interface.gateway}\n")
                                if self.config.system.dns and self.config.system.dns.forwarders:
                                    for dns in self.config.system.dns.forwarders:
                                        f.write(f"DNS={dns}\n")
                                if interface.ipv6 is False:
                                    f.write("IPv6AcceptRA=no\nLinkLocalAddressing=ipv4\n")
                                else:
                                    f.write("IPv6AcceptRA=yes\n")
                
                elif interface.network == "lan" and interface.bridge:
                    network_file = f"25-{interface.name}.network"
                    network_path = os.path.join(network_dir, network_file)
                    generated_files.add(network_file)
                    
                    with open(network_path, "w") as f:
                        f.write(f"[Match]\nName={interface.name}\n\n[Network]\nBridge={interface.bridge}\n")

            # PPPoE configuration writing
            if pppoe_active:
                wan_if = next((i for i in self.config.network.interfaces if i.network == "wan" and i.protocol == "pppoe"), None)
                if wan_if and wan_if.pppoe:
                    username = wan_if.pppoe.username
                    password = wan_if.pppoe.password
                    
                    ppp_dir = os.path.join(etc_dir, "ppp", "peers")
                    try:
                        os.makedirs(ppp_dir, exist_ok=True)
                        peer_path = os.path.join(ppp_dir, "roost-wan")
                        with open(peer_path, "w") as f:
                            f.write(f'plugin rp-pppoe.so\n{pppoe_iface}\nuser "{username}"\nnoipdefault\nusepeerdns\ndefaultroute\npersist\nmaxfail 0\n')
                        
                        # Update chap-secrets / pap-secrets
                        for secret_file in ["chap-secrets", "pap-secrets"]:
                            secret_path = os.path.join(etc_dir, "ppp", secret_file)
                            secret_line = f'"{username}" * "{password}"\n'
                            lines = []
                            if os.path.exists(secret_path):
                                with open(secret_path, "r") as sf:
                                    lines = sf.readlines()
                            lines = [l for l in lines if username not in l]
                            lines.append(secret_line)
                            with open(secret_path, "w") as sf:
                                sf.writelines(lines)
                            os.chmod(secret_path, 0o600)
                    except Exception as e:
                        print(f"Warning: Failed to write PPPoE configuration: {e}", file=sys.stderr)
                    
                    if os.getuid() == 0 and not self.mock:
                        print("Starting PPPoE connection...")
                        subprocess.run(["pon", "roost-wan"], check=False)
            else:
                if os.getuid() == 0 and not self.mock:
                    peer_file = os.path.join(etc_dir, "ppp", "peers", "roost-wan")
                    if os.path.exists(peer_file):
                        print("Stopping PPPoE connection...")
                        subprocess.run(["poff", "roost-wan"], check=False)

            # 3. Clean up any stale configuration files starting with 10-, 20-, or 25-
            for filename in os.listdir(network_dir):
                if (filename.startswith("10-") or filename.startswith("20-") or filename.startswith("25-")) \
                        and (filename.endswith(".network") or filename.endswith(".netdev")):
                    if filename not in generated_files:
                        try:
                            os.remove(os.path.join(network_dir, filename))
                        except Exception as e:
                            print(f"Warning: Could not remove stale network config {filename}: {e}", file=sys.stderr)

            if os.getuid() == 0 and not self.mock:
                print("Restarting systemd-networkd service...")
                subprocess.run(["systemctl", "restart", "systemd-networkd"], check=True)
        except Exception as e:
            print(f"Error updating network interfaces: {e}", file=sys.stderr)
