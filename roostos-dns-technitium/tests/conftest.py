import os
import time
import subprocess
import pytest

@pytest.fixture(scope="session")
def dbus_session():
    """Spawns an isolated dbus-daemon session for integration tests."""
    try:
        proc = subprocess.Popen(
            ["dbus-daemon", "--session", "--print-address", "--nofork"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        pytest.skip("dbus-daemon not found. Skipping D-Bus integration tests.")

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
