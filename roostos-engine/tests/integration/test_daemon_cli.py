import os
import json
import pytest
from click.testing import CliRunner
from roostos_engine.cli import main as cli_main
from roostos_engine.config import load_config_directory

def test_daemon_status_and_device_management(dbus_session, running_daemon, temp_config_dir):
    """Integration test checking status queries, device listings, registrations, YAML updates, and config validations."""
    runner = CliRunner()
    
    # 1. Verify status command outputs expected metadata
    res = runner.invoke(cli_main, ["status", "--session"])
    if res.exit_code != 0:
        print(f"Exception: {res.exception}")
        print(f"Output: {res.output}")
    assert res.exit_code == 0
    assert "RoostOS Engine Daemon: RUNNING" in res.output
    assert "sandbox-router" in res.output

    # 2. Verify default devices are listed
    res = runner.invoke(cli_main, ["device", "list", "--session"])
    assert res.exit_code == 0
    assert "a4:83:e7:12:34:56" in res.output
    assert "Mom's Laptop" in res.output
    assert "Alice's iPad" in res.output

    # 3. Register a new device through CLI invocation
    res = runner.invoke(cli_main, [
        "device", "register",
        "00:aa:bb:cc:dd:ee", "Integration Test Client",
        "--owner", "mom_profile",
        "--location", "living_room",
        "--tags", "test,temp",
        "--session"
    ])
    assert res.exit_code == 0
    assert "Successfully registered device" in res.output

    # 4. Verify validation of host-side YAML write-backs
    config = load_config_directory(temp_config_dir)
    assert any(d.mac == "00:aa:bb:cc:dd:ee" for d in config.devices)
    dev = next(d for d in config.devices if d.mac == "00:aa:bb:cc:dd:ee")
    assert dev.name == "Integration Test Client"
    assert dev.owner == "mom_profile"
    assert "test" in dev.tags

    # 5. Verify the device list command displays the newly registered client
    res = runner.invoke(cli_main, ["device", "list", "--session"])
    assert res.exit_code == 0
    assert "00:aa:bb:cc:dd:ee" in res.output
    assert "Integration Test Client" in res.output

    # 6. Verify config validate command checks out successfully
    res = runner.invoke(cli_main, ["config", "validate", "--dir", str(temp_config_dir)])
    assert res.exit_code == 0
    assert "Validation Success!" in res.output


import asyncio
from roostos_sdk.client import RoostClient

@pytest.mark.asyncio
async def test_dhcp_lease_signals_via_sdk(dbus_session, running_daemon):
    """Integration test checking RegisterLease triggers expected signal callbacks in RoostClient."""
    client = RoostClient(session=True)
    await client.connect()

    connected_signal = asyncio.Event()
    unknown_signal = asyncio.Event()

    def on_connected(mac, ip, hostname):
        assert mac == "a4:83:e7:12:34:56"
        assert ip == "192.168.1.10"
        connected_signal.set()

    def on_unknown(mac, ip, hostname):
        assert mac == "aa:bb:cc:dd:ee:ff"
        assert ip == "192.168.1.200"
        unknown_signal.set()

    client.on_device_connected(on_connected)
    client.on_unknown_device_discovered(on_unknown)

    try:
        # 1. Register lease for a registered device (Mom's Laptop)
        success = await client.register_lease("a4:83:e7:12:34:56", "192.168.1.10", "moms-laptop")
        assert success is True

        # Wait for DeviceConnected signal
        await asyncio.wait_for(connected_signal.wait(), timeout=2.0)
        assert connected_signal.is_set()

        # 2. Register lease for an unregistered device
        success = await client.register_lease("aa:bb:cc:dd:ee:ff", "192.168.1.200", "unknown-phone")
        assert success is True

        # Wait for UnknownDeviceDiscovered signal
        await asyncio.wait_for(unknown_signal.wait(), timeout=2.0)
        assert unknown_signal.is_set()

        # 3. Check active leases count
        leases = await client.get_active_leases()
        assert len(leases) == 2
        assert any(l["mac"] == "a4:83:e7:12:34:56" for l in leases)
        assert any(l["mac"] == "aa:bb:cc:dd:ee:ff" for l in leases)

    finally:
        client.disconnect()


def test_daemon_bypass_time_extension(dbus_session, running_daemon):
    """Integration test checking that CLI bypass grant/revoke updates active daemon bypass state."""
    runner = CliRunner()
    
    # 1. Grant a time extension bypass of 60 minutes
    res = runner.invoke(cli_main, [
        "bypass", "grant", "4c:32:75:98:76:54", "60", "--session"
    ])
    assert res.exit_code == 0
    assert "Granted" in res.output

    # 2. Revoke the bypass
    res = runner.invoke(cli_main, [
        "bypass", "revoke", "4c:32:75:98:76:54", "--session"
    ])
    assert res.exit_code == 0
    assert "Revoked" in res.output
