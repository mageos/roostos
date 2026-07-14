import os
import sys
import time
import subprocess
import pytest
import yaml

@pytest.fixture(scope="session")
def dbus_session():
    """Spawns a private, isolated dbus-daemon session for integration tests."""
    try:
        proc = subprocess.Popen(
            ["dbus-daemon", "--session", "--print-address", "--nofork"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        pytest.skip("dbus-daemon not found on host. Skipping.")

    dbus_address = ""
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
        pytest.skip("Failed to initialize private dbus-daemon session.")

    os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
    
    yield dbus_address

    proc.terminate()
    proc.wait()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Fixture to build a valid set of split configs in a temporary directory."""
    with open(tmp_path / "system.yaml", "w") as f:
        yaml.safe_dump({
            "system": {
                "hostname": "sdk-router",
                "timezone": "UTC"
            },
            "users": [
                {"username": "admin", "role": "admin"}
            ]
        }, f)
    
    with open(tmp_path / "network.yaml", "w") as f:
        yaml.safe_dump({
            "network": {
                "interfaces": [
                    {"name": "eth0", "role": "wan", "dhcp": True}
                ]
            }
        }, f)

    with open(tmp_path / "devices.yaml", "w") as f:
        yaml.safe_dump({
            "people": [],
            "buildings": [],
            "rooms": [],
            "devices": [
                {"mac": "a4:83:e7:12:34:56", "name": "Mom's Laptop"}
            ]
        }, f)

    with open(tmp_path / "schedules.yaml", "w") as f:
        yaml.safe_dump({"firewall": {}}, f)

    with open(tmp_path / "plugins.yaml", "w") as f:
        yaml.safe_dump({"plugins": []}, f)

    return tmp_path


@pytest.fixture
def running_daemon(dbus_session, temp_config_dir):
    """Spawns the RoostOS daemon in a background subprocess connected to the private D-Bus bus."""
    proc = subprocess.Popen([
        sys.executable, "-m", "roostos_engine.daemon",
        "--config-dir", str(temp_config_dir),
        "--session"
    ])
    
    time.sleep(3.0)
    
    yield proc

    proc.terminate()
    proc.wait()
