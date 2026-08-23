import os
import sys
import asyncio
import signal
from dbus_next.aio import MessageBus
from dbus_next import BusType

from roostos_engine.daemon.dbus_service import (
    RoostDaemonInterface,
    BUS_NAME,
    OBJECT_PATH,
)
from roostos_engine.daemon.backup_handler import BackupHandler
from roostos_engine.daemon.upnp_handler import UPnPHandler
from roostos_engine.daemon.allowance_tracker import AllowanceTracker
from roostos_engine.daemon.ui_extractor import extract_plugin_ui


async def start_daemon(config_dir: str, bus_type: BusType = BusType.SYSTEM, mock: bool = False):
    try:
        bus = await MessageBus(bus_type=bus_type).connect()
    except Exception as e:
        if bus_type == BusType.SYSTEM:
            print("System D-Bus connection failed. Falling back to Session D-Bus bus for local sandbox...", file=sys.stderr)
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
        else:
            raise e

    interface = RoostDaemonInterface(BUS_NAME, config_dir, mock=mock)
    bus.export(OBJECT_PATH, interface)
    await bus.request_name(BUS_NAME)
    print(f"RoostOS Engine Daemon registered on D-Bus: '{BUS_NAME}' at object path '{OBJECT_PATH}'")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def shutdown():
        print("\nShutdown signal received. Releasing D-Bus interfaces...")
        interface.stop_enforcer()
        bus.disconnect()
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass

    await stop_event.wait()


def main():
    import argparse
    from roostos_engine.di import load_providers_settings
    parser = argparse.ArgumentParser(description="RoostOS Engine core daemon service")
    parser.add_argument("--config-dir", default=os.environ.get("ROOSTOS_CONFIG_DIR", "/etc/roostos"), help="Path to split configurations folder")
    parser.add_argument("--providers-config", default=os.environ.get("ROOSTOS_PROVIDERS_CONFIG"), help="Path to custom providers.yaml")
    parser.add_argument("--config-repo", default=os.environ.get("ROOSTOS_CONFIG_REPO"), help="Override repository: 'staging', 'yaml', 'memory'")
    parser.add_argument("--firewall-manager", default=os.environ.get("ROOSTOS_FIREWALL_MANAGER"), help="Override firewall manager: 'nftables', 'mock'")
    parser.add_argument("--cert-manager", default=os.environ.get("ROOSTOS_CERT_MANAGER"), help="Override certificate manager: 'standard', 'mock'")
    parser.add_argument("--session", action="store_true", help="Force connecting to Session D-Bus bus instead of System D-Bus")
    parser.add_argument("--mock", action="store_true", help="Force mock mode, bypassing system modifications")
    args = parser.parse_args()

    bus_type = BusType.SESSION if args.session else BusType.SYSTEM

    overrides = {
        "config_repository": args.config_repo,
        "firewall_manager": args.firewall_manager,
        "cert_manager": args.cert_manager,
    }
    if args.mock:
        overrides["firewall_manager"] = "mock"

    providers_settings = load_providers_settings(
        config_dir=args.config_dir,
        providers_config_path=args.providers_config,
        overrides=overrides
    )
    
    try:
        asyncio.run(start_daemon(args.config_dir, bus_type, args.mock or providers_settings.firewall_manager == "mock"))
    except KeyboardInterrupt:
        pass
    print("Daemon stopped cleanly.")


__all__ = [
    "RoostDaemonInterface",
    "BUS_NAME",
    "OBJECT_PATH",
    "BackupHandler",
    "UPnPHandler",
    "AllowanceTracker",
    "extract_plugin_ui",
    "start_daemon",
    "main",
]
