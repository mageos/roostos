#!/usr/bin/env python3
import os
import sys
import yaml

def generate_mock_configs(target_dir):
    os.makedirs(target_dir, exist_ok=True)
    print(f"Generating mock configurations inside: {target_dir}")

    # 1. system.yaml
    system_data = {
        "system": {
            "hostname": "roost-home-router",
            "domain": "home.lan",
            "timezone": "America/New_York",
            "https": {
                "enabled": False,
                "domain": "router.home.lan"
            },
            "updates": {
                "auto_install": True,
                "auto_reboot": True,
                "reboot_window": {
                    "days": ["Sun", "Wed"],
                    "time": "03:30"
                }
            }
        },
        "users": [
            {"username": "admin", "role": "admin", "person": "dad_profile"},
            {"username": "mom", "role": "parent", "person": "mom_profile"},
            {"username": "kid1", "role": "member", "person": "alice_profile"}
        ]
    }
    with open(os.path.join(target_dir, "system.yaml"), "w") as f:
        yaml.safe_dump(system_data, f, default_flow_style=False, sort_keys=False)

    # 2. network.yaml
    network_data = {
        "network": {
            "interfaces": [
                {"name": "eth0", "role": "wan", "dhcp": True},
                {"name": "eth1", "role": "lan", "bridge": "br-lan"},
                {"name": "eth2", "role": "lan", "bridge": "br-lan"}
            ],
            "bridges": [
                {"name": "br-lan", "ip": "192.168.1.1/24"}
            ],
            "vlans": [
                {"name": "vlan-guest", "id": 10, "interface": "br-lan", "ip": "192.168.10.1/24", "isolate": True},
                {"name": "vlan-iot", "id": 20, "interface": "br-lan", "ip": "192.168.20.1/24", "isolate": True}
            ],
            "gateways": [
                {"id": "default", "name": "Standard ISP Gateway", "interface": "eth0"},
                {"id": "vpn_eu", "name": "NordVPN Europe", "interface": "wg-vpn-eu", "type": "static"}
            ]
        },
        "wifi": {
            "access_points": [
                {"ssid": "RoostHome", "interface": "wlan0", "passphrase": "supersecurepass", "security": "wpa3", "bridge": "br-lan"},
                {"ssid": "RoostHome-Guest", "interface": "wlan0.10", "passphrase": "guestpassword", "security": "wpa2", "vlan": 10},
                {"ssid": "RoostHome-IoT", "interface": "wlan0.20", "passphrase": "iotpassword", "security": "wpa2", "vlan": 20}
            ],
            "mesh": {
                "enabled": True,
                "interface": "wlan1",
                "ssid": "RoostMeshBackhaul",
                "passphrase": "meshbackhaulpassword",
                "frequency": 5180
            }
        }
    }
    with open(os.path.join(target_dir, "network.yaml"), "w") as f:
        yaml.safe_dump(network_data, f, default_flow_style=False, sort_keys=False)

    # 3. devices.yaml
    devices_data = {
        "people": [
            {"id": "dad_profile", "name": "Dad"},
            {"id": "mom_profile", "name": "Mom"},
            {"id": "alice_profile", "name": "Alice (Kid)", "dns_profile": "strict-parental"},
            {"id": "bob_profile", "name": "Bob (Kid)", "dns_profile": "strict-parental"}
        ],
        "buildings": [
            {"id": "main_house", "name": "Main House"}
        ],
        "rooms": [
            {"id": "living_room", "name": "Living Room", "building": "main_house"},
            {"id": "kitchen", "name": "Kitchen", "building": "main_house"},
            {"id": "kids_bedroom", "name": "Kids Bedroom", "building": "main_house"},
            {"id": "hallway", "name": "Hallway", "building": "main_house"}
        ],
        "devices": [
            # Parents Devices
            {"mac": "1a:2b:3c:4d:5e:6f", "name": "Dad's Phone", "owner": "dad_profile", "location": "living_room", "tags": ["personal"]},
            {"mac": "2a:3b:4c:5d:6e:7f", "name": "Mom's Laptop", "owner": "mom_profile", "location": "kitchen", "tags": ["personal", "work"], "static_ip": "192.168.1.100"},
            
            # Kids Devices
            {"mac": "3a:4b:5c:6d:7e:8f", "name": "Alice's iPad", "owner": "alice_profile", "location": "kids_bedroom", "tags": ["kids", "entertainment"], "static_ip": "192.168.1.150"},
            {"mac": "4a:5b:6c:7d:8e:9f", "name": "Bob's Nintendo Switch", "owner": "bob_profile", "location": "kids_bedroom", "tags": ["kids", "gaming"]},
            
            # Smart Home / IoT
            {"mac": "5a:6b:7c:8d:9e:0f", "name": "Living Room Smart TV", "location": "living_room", "tags": ["entertainment", "media"], "gateway": "vpn_eu"},
            {"mac": "6a:7b:8c:9d:0e:1f", "name": "Smart Thermostat", "location": "hallway", "tags": ["iot"], "static_ip": "192.168.20.10"},
            {"mac": "7a:8b:9c:0d:1e:2f", "name": "Kitchen Fridge Smart Screen", "location": "kitchen", "tags": ["iot"]}
        ]
    }
    with open(os.path.join(target_dir, "devices.yaml"), "w") as f:
        yaml.safe_dump(devices_data, f, default_flow_style=False, sort_keys=False)

    # 4. schedules.yaml
    schedules_data = {
        "firewall": {
            "port_forwards": [
                {"name": "Plex Server Port", "protocol": "tcp", "external_port": 32400, "internal_ip": "192.168.1.100", "internal_port": 32400},
                {"name": "Minecraft Server LAN", "protocol": "tcp", "external_port": 25565, "internal_ip": "192.168.1.150", "internal_port": 25565}
            ],
            "rules": [
                {"name": "Allow SSH from Internet", "interface": "eth0", "protocol": "tcp", "port": 22, "action": "accept", "enabled": True},
                {"name": "Allow HTTPS from Internet", "interface": "eth0", "protocol": "tcp", "port": 443, "action": "accept", "enabled": True},
                {"name": "Allow WireGuard VPN", "interface": "eth0", "protocol": "udp", "port": 51820, "action": "accept", "enabled": False}
            ],
            "schedules": [
                {
                    "name": "Kids School Night Bedtime",
                    "targets": [{"person": "alice_profile"}, {"person": "bob_profile"}],
                    "days": ["Sun", "Mon", "Tue", "Wed", "Thu"],
                    "start_time": "20:30",
                    "end_time": "06:00",
                    "action": "block_internet"
                },
                {
                    "name": "Weekend Screen Time Limit",
                    "targets": [{"tag": "kids"}],
                    "days": ["Fri", "Sat"],
                    "daily_limit": 120, # 2 hours
                    "action": "block_internet"
                },
                {
                    "name": "No IoT Internet Access",
                    "targets": [{"tag": "iot"}],
                    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "action": "block_internet"
                }
            ]
        }
    }
    with open(os.path.join(target_dir, "schedules.yaml"), "w") as f:
        yaml.safe_dump(schedules_data, f, default_flow_style=False, sort_keys=False)

    plugins_data = {
        "plugins": [
            {"id": "local-dns-resolver", "name": "Local DNS Resolver", "enabled": True, "containers": []},
            {"id": "adblock-pihole", "name": "Pi-hole Adblocker", "enabled": False, "containers": []}
        ]
    }
    with open(os.path.join(target_dir, "plugins.yaml"), "w") as f:
        yaml.safe_dump(plugins_data, f, default_flow_style=False, sort_keys=False)

    print(f"Mock configurations generated successfully!")

if __name__ == "__main__":
    target = "/tmp/roostos-fake-configs"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    generate_mock_configs(target)
