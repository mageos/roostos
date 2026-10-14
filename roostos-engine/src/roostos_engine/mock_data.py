"""Mock seed data generator providing a rich in-memory RoostOS configuration for UI development."""

from roostos_engine.config import (
    RoostConfig,
    SystemSettings,
    SystemDNSConfig,
    UserConfig,
    PersonConfig,
    BuildingConfig,
    RoomConfig,
    DeviceConfig,
    NetworkSettings,
    NetworkBridge,
    NetworkVlan,
    ZoneConfig,
    WifiSettings,
    WifiAccessPoint,
    FirewallSettings,
    PortForwardConfig,
    InputRuleConfig,
    NodeConfig,
)


def create_mock_config() -> RoostConfig:
    """Builds a fully populated, realistic RoostConfig for local UI development and testing."""
    return RoostConfig(
        system=SystemSettings(
            hostname="roost-home-router",
            domain="lan.roost",
            dns=SystemDNSConfig(
                subsystem="technitium",
                forwarders=["1.1.1.1", "1.0.0.1"],
                ad_blocking_enabled=True,
                dnssec_validation=True,
            ),
        ),
        users=[
            UserConfig(username="admin", role="admin", person="dad"),
            UserConfig(username="mom", role="parent", person="mom"),
        ],
        people=[
            PersonConfig(id="dad", name="Dad", role="parent", dns_profile="Standard"),
            PersonConfig(id="mom", name="Mom", role="parent", dns_profile="Standard"),
            PersonConfig(id="alice", name="Alice", role="kid", dns_profile="Strict Kids"),
            PersonConfig(id="bob", name="Bob", role="kid", dns_profile="SafeSearch + AdBlock"),
        ],
        buildings=[
            BuildingConfig(id="main", name="Main House"),
        ],
        rooms=[
            RoomConfig(id="living_room", name="Living Room", building="main"),
            RoomConfig(id="office", name="Office", building="main"),
            RoomConfig(id="kids_bedroom", name="Kids Bedroom", building="main"),
        ],
        devices=[
            DeviceConfig(
                mac="dc:a6:32:11:22:33",
                name="Dad's MacBook Pro",
                owner="dad",
                location="office",
                tags=["lan", "laptop"],
                static_ip="192.168.1.101",
            ),
            DeviceConfig(
                mac="f4:d4:88:44:55:66",
                name="Alice's iPad",
                owner="alice",
                location="kids_bedroom",
                tags=["lan", "tablet"],
                static_ip="192.168.1.105",
            ),
            DeviceConfig(
                mac="b8:27:eb:77:88:99",
                name="Living Room Apple TV",
                owner=None,
                location="living_room",
                tags=["entertainment", "lan"],
                static_ip="192.168.1.120",
            ),
            DeviceConfig(
                mac="50:ec:50:aa:bb:cc",
                name="Front Door Nest Cam",
                owner=None,
                location="living_room",
                tags=["iot"],
                static_ip="192.168.40.10",
            ),
        ],
        network=NetworkSettings(
            interfaces=[],
            bridges=[
                NetworkBridge(name="br-lan", ip="192.168.1.1", netmask="255.255.255.0", interfaces=["eth1", "eth2"]),
                NetworkBridge(name="br-guest", ip="192.168.20.1", netmask="255.255.255.0"),
                NetworkBridge(name="br-iot", ip="192.168.40.1", netmask="255.255.255.0"),
            ],
            vlans=[
                NetworkVlan(name="Guest Network", id=20, interface="eth1", ip="192.168.20.1", isolate=True),
                NetworkVlan(name="Smart Home IoT", id=40, interface="eth1", ip="192.168.40.1", isolate=True),
            ],
            gateways=[],
            zones=[
                ZoneConfig(id="lan", name="Household LAN", isolation=False),
                ZoneConfig(id="guest", name="Guest Wi-Fi", isolation=True),
                ZoneConfig(id="iot", name="Smart Home IoT", isolation=True),
            ],
        ),
        wifi=WifiSettings(
            access_points=[
                WifiAccessPoint(
                    name="Home Wi-Fi",
                    ssid="RoostHome",
                    passphrase="HomeSecretKey2026",
                    radio="wlan0",
                    bridge="br-lan",
                    enabled=True,
                ),
                WifiAccessPoint(
                    name="Guest Wi-Fi",
                    ssid="RoostHome-Guest",
                    passphrase="GuestWelcome2026",
                    radio="wlan0",
                    bridge="br-guest",
                    enabled=True,
                ),
            ]
        ),
        firewall=FirewallSettings(
            port_forwards=[
                PortForwardConfig(name="Plex Media Server", proto="tcp", ext_port=32400, int_ip="192.168.1.120", int_port=32400),
                PortForwardConfig(name="WireGuard Tunnel", proto="udp", ext_port=51820, int_ip="192.168.1.1", int_port=51820),
            ],
            rules=[
                InputRuleConfig(name="Allow Web Admin", proto="tcp", port=8000, action="accept"),
                InputRuleConfig(name="Allow SSH", proto="tcp", port=22, action="accept"),
            ],
        ),
        nodes=[
            NodeConfig(id="roost-gateway-01", name="Roost Gateway 01", role="gateway", ip="192.168.1.1", status="online"),
            NodeConfig(id="roost-controller-01", name="Roost App Controller", role="worker", ip="192.168.1.2", status="online"),
        ],
        schedules=[],
        plugins=[],
        vpns=[],
    )
