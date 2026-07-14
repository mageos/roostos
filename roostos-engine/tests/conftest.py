import os
import sys
import time
import subprocess
import pytest
import yaml

@pytest.fixture(scope="session")
def dbus_session():
    """Spawns a private, isolated dbus-daemon session for integration tests."""
    # Launch dbus-daemon in a new session
    # Normally --session uses /usr/share/dbus-1/session.conf or similar default config.
    try:
        proc = subprocess.Popen(
            ["dbus-daemon", "--session", "--print-address", "--nofork"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        pytest.skip("dbus-daemon not found on host. Skipping D-Bus integration tests.")

    # Read the D-Bus bus address printed to stdout
    dbus_address = ""
    # Wait for the address to be printed
    for _ in range(30):
        if proc.poll() is not None:
            break
        line = proc.stdout.readline().strip()
        if line.startswith("unix:"):
            dbus_address = line
            break
        time.sleep(0.1)

    if not dbus_address:
        proc.terminate()
        proc.wait()
        pytest.skip("Failed to initialize private dbus-daemon session. Skipping.")

    # Set the session bus address for all tests in this process
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
    
    yield dbus_address

    # Terminate private bus
    proc.terminate()
    proc.wait()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Fixture to build a valid set of split configs in a temporary directory."""
    # 1. system.yaml
    with open(tmp_path / "system.yaml", "w") as f:
        yaml.safe_dump({
            "system": {
                "hostname": "sandbox-router",
                "timezone": "America/Chicago"
            },
            "users": [
                {"username": "admin", "role": "admin"},
                {"username": "mom", "role": "parent", "person": "mom_profile"}
            ]
        }, f)
    
    # 2. network.yaml
    with open(tmp_path / "network.yaml", "w") as f:
        yaml.safe_dump({
            "network": {
                "interfaces": [
                    {"name": "eth0", "role": "wan", "dhcp": True},
                    {"name": "eth1", "role": "lan", "bridge": "br0"}
                ],
                "bridges": [
                    {"name": "br0", "ip": "192.168.1.1/24"}
                ]
            }
        }, f)

    # 3. devices.yaml
    with open(tmp_path / "devices.yaml", "w") as f:
        yaml.safe_dump({
            "people": [
                {"id": "mom_profile", "name": "Mom"},
                {"id": "alice_profile", "name": "Alice (Kid)"}
            ],
            "buildings": [
                {"id": "main_house", "name": "Main House"}
            ],
            "rooms": [
                {"id": "living_room", "name": "Living Room", "building": "main_house"},
                {"id": "kids_bedroom", "name": "Kids Bedroom", "building": "main_house"}
            ],
            "devices": [
                {"mac": "a4:83:e7:12:34:56", "name": "Mom's Laptop", "owner": "mom_profile", "location": "living_room", "tags": ["personal", "work"], "static_ip": "192.168.1.10"},
                {"mac": "4c:32:75:98:76:54", "name": "Alice's iPad", "owner": "alice_profile", "location": "kids_bedroom", "tags": ["kids", "gaming"], "static_ip": "192.168.1.50"}
            ]
        }, f)

    # 4. schedules.yaml
    with open(tmp_path / "schedules.yaml", "w") as f:
        yaml.safe_dump({
            "firewall": {
                "schedules": [
                    {
                        "name": "Kids Bedtime Block",
                        "targets": [{"tag": "kids"}],
                        "days": ["Mon", "Tue"],
                        "start_time": "21:00",
                        "end_time": "06:00",
                        "action": "block_internet"
                    }
                ]
            }
        }, f)

    # 5. plugins.yaml
    with open(tmp_path / "plugins.yaml", "w") as f:
        yaml.safe_dump({
            "plugins": [
                {"id": "local-dns-resolver", "name": "Local DNS Resolver", "enabled": True, "containers": []}
            ]
        }, f)

    return tmp_path


@pytest.fixture
def running_daemon(dbus_session, temp_config_dir):
    """Spawns the RoostOS daemon in a background subprocess connected to the private D-Bus bus."""
    # Start the daemon
    proc = subprocess.Popen([
        sys.executable, "-m", "roostos_engine.daemon",
        "--config-dir", str(temp_config_dir),
        "--session"
    ])
    
    # Wait for the daemon to initialize and acquire bus name
    time.sleep(3.0)
    
    yield proc

    # Stop daemon cleanly
    proc.terminate()
    proc.wait()
