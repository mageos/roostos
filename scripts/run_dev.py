#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess
import yaml
from typing import List

# Paths inside dev_root
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_ROOT = os.path.join(WORKSPACE_DIR, "dev_root")
CONFIG_DIR = os.path.join(DEV_ROOT, "etc", "roostos")
NETWORK_DIR = os.path.join(DEV_ROOT, "etc", "systemd", "network")
KEA_DIR = os.path.join(DEV_ROOT, "etc", "kea")
NFTABLES_CONF = os.path.join(DEV_ROOT, "etc", "nftables.conf")
ETC_DIR = os.path.join(DEV_ROOT, "etc")

def seed_default_configs() -> None:
    """Seed dev_root/etc/roostos with default YAML configuration files if missing."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    # 1. system.yaml
    sys_path = os.path.join(CONFIG_DIR, "system.yaml")
    if not os.path.exists(sys_path):
        print(f"Seeding default config: {sys_path}")
        with open(sys_path, "w") as f:
            yaml.safe_dump({
                "system": {
                    "hostname": "dev-roost-router",
                    "domain": "dev.lan",
                    "timezone": "UTC",
                    "dns": {
                        "forwarders": ["1.1.1.1", "8.8.8.8"]
                    }
                },
                "users": [
                    {"username": "admin", "role": "admin", "person": "dad_profile"}
                ]
            }, f)

    # 2. network.yaml
    net_path = os.path.join(CONFIG_DIR, "network.yaml")
    if not os.path.exists(net_path):
        print(f"Seeding default config: {net_path}")
        with open(net_path, "w") as f:
            yaml.safe_dump({
                "network": {
                    "interfaces": [
                        {"name": "eth0", "role": "wan", "dhcp": True},
                        {"name": "eth1", "role": "lan", "bridge": "br0"}
                    ],
                    "bridges": [
                        {
                            "name": "br0",
                            "ip": "192.168.1.1/24",
                            "dhcp_enabled": True,
                            "dhcp_pool_start": "192.168.1.100",
                            "dhcp_pool_end": "192.168.1.250"
                        }
                    ]
                }
            }, f)

    # 3. devices.yaml
    dev_path = os.path.join(CONFIG_DIR, "devices.yaml")
    if not os.path.exists(dev_path):
        print(f"Seeding default config: {dev_path}")
        with open(dev_path, "w") as f:
            yaml.safe_dump({
                "people": [
                    {"id": "dad_profile", "name": "Dad"}
                ],
                "buildings": [],
                "rooms": [],
                "devices": []
            }, f)

    # 4. schedules.yaml
    sch_path = os.path.join(CONFIG_DIR, "schedules.yaml")
    if not os.path.exists(sch_path):
        print(f"Seeding default config: {sch_path}")
        with open(sch_path, "w") as f:
            yaml.safe_dump({
                "firewall": {
                    "schedules": [],
                    "rules": [],
                    "port_forwards": []
                }
            }, f)

    # 5. plugins.yaml
    plg_path = os.path.join(CONFIG_DIR, "plugins.yaml")
    if not os.path.exists(plg_path):
        print(f"Seeding default config: {plg_path}")
        with open(plg_path, "w") as f:
            yaml.safe_dump({
                "plugins": []
            }, f)

    # 6. providers.yaml
    prov_path = os.path.join(CONFIG_DIR, "providers.yaml")
    if not os.path.exists(prov_path):
        print(f"Seeding default config: {prov_path}")
        with open(prov_path, "w") as f:
            yaml.safe_dump({
                "providers": {
                    "auth_provider": "mock",
                    "config_repository": "staging",
                    "system_client": "dbus",
                    "cert_manager": "standard",
                    "firewall_manager": "mock"
                }
            }, f)

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RoostOS Dev Sandbox Runner")
    parser.add_argument("--providers-config", default=None, help="Custom path to providers.yaml")
    parser.add_argument("--auth-provider", default=None, help="Override auth provider ('mock', 'pam')")
    parser.add_argument("--config-repo", default=None, help="Override config repository ('staging', 'yaml', 'memory')")
    parser.add_argument("--system-client", default=None, help="Override system client ('dbus', 'mock')")
    parser.add_argument("--firewall-manager", default=None, help="Override firewall manager ('mock', 'nftables')")
    parser.add_argument("--cert-manager", default=None, help="Override cert manager ('standard', 'mock')")
    args = parser.parse_args()

    print("===================================================")
    print("        Starting RoostOS Local Dev Sandbox        ")
    print("===================================================")

    # Ensure python virtualenv is present
    venv_python = os.path.join(WORKSPACE_DIR, ".venv", "bin", "python")
    if not os.path.exists(venv_python):
        print("Error: Virtualenv python not found at .venv/bin/python. Run uv pip install or make first.", file=sys.stderr)
        sys.exit(1)

    seed_default_configs()

    # Create directories
    os.makedirs(NETWORK_DIR, exist_ok=True)
    os.makedirs(KEA_DIR, exist_ok=True)
    os.makedirs(ETC_DIR, exist_ok=True)

    processes = []
    
    # 1. Start private D-Bus daemon session
    print("Starting isolated private D-Bus daemon...")
    try:
        dbus_proc = subprocess.Popen(
            ["dbus-daemon", "--session", "--print-address", "--nofork"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
    except FileNotFoundError:
        print("Error: dbus-daemon command not found. Please install dbus.", file=sys.stderr)
        sys.exit(1)

    processes.append(dbus_proc)

    # Read the D-Bus bus address from stdout
    dbus_address = ""
    for _ in range(30):
        if dbus_proc.poll() is not None:
            break
        line = dbus_proc.stdout.readline().strip()
        if line.startswith("unix:"):
            dbus_address = line
            break
        time.sleep(0.1)

    if not dbus_address:
        print("Error: Failed to obtain private D-Bus address.", file=sys.stderr)
        dbus_proc.terminate()
        sys.exit(1)

    print(f"Isolated D-Bus Session started at: {dbus_address}")

    # Configure environmental variables for child processes
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
    env["DBUS_SYSTEM_BUS_ADDRESS"] = dbus_address
    env["ROOSTOS_SESSION_BUS"] = "1"
    env["ROOSTOS_MOCK_AUTH"] = "1"
    env["ROOSTOS_CONFIG_DIR"] = CONFIG_DIR
    env["ROOSTOS_CERT_DIR"] = os.path.join(CONFIG_DIR, "certs")
    env["ROOSTOS_STAGED_CONFIG_DIR"] = os.path.join(DEV_ROOT, "var", "lib", "roostos", "staged_config")
    env["ROOSTOS_SYSTEMD_NETWORK_DIR"] = NETWORK_DIR
    env["ROOSTOS_KEA_CONF_DIR"] = KEA_DIR
    env["ROOSTOS_NFTABLES_CONF"] = NFTABLES_CONF
    env["ROOSTOS_ETC_DIR"] = ETC_DIR
    env["ROOSTOS_WEB_ASSETS"] = os.path.join(WORKSPACE_DIR, "roostos-ui")

    if args.providers_config:
        env["ROOSTOS_PROVIDERS_CONFIG"] = args.providers_config
    if args.auth_provider:
        env["ROOSTOS_AUTH_PROVIDER"] = args.auth_provider
    if args.config_repo:
        env["ROOSTOS_CONFIG_REPO"] = args.config_repo
    if args.system_client:
        env["ROOSTOS_SYSTEM_CLIENT"] = args.system_client
    if args.firewall_manager:
        env["ROOSTOS_FIREWALL_MANAGER"] = args.firewall_manager
    if args.cert_manager:
        env["ROOSTOS_CERT_MANAGER"] = args.cert_manager

    os.makedirs(os.path.join(CONFIG_DIR, "certs"), exist_ok=True)
    os.makedirs(os.path.join(DEV_ROOT, "var", "lib", "roostos", "staged_config"), exist_ok=True)

    # 2. Start roostd daemon
    print("Starting roostd core daemon service (mock)...")
    daemon_proc = subprocess.Popen(
        [
            venv_python, 
            os.path.join(WORKSPACE_DIR, "roostos-engine", "src", "roostos_engine", "daemon.py"),
            "--config-dir", CONFIG_DIR,
            "--session",
            "--mock"
        ],
        env=env
    )
    processes.append(daemon_proc)

    # Give the daemon a moment to register on D-Bus
    time.sleep(1)

    # 3. Start roostos-web FastApi server
    print("Starting roostos-web FastAPI server (local UI assets)...")
    web_proc = subprocess.Popen(
        [
            venv_python, 
            os.path.join(WORKSPACE_DIR, "roostos-web", "src", "roostos_web", "main.py")
        ],
        env=env
    )
    processes.append(web_proc)

    print("\n---------------------------------------------------")
    print("RoostOS Dev Sandbox is RUNNING!")
    print("Access the Web UI at: http://127.0.0.1:8000")
    print("Login credentials: Username: admin | Password: password")
    print("Configuration folder: ./dev_root/etc/roostos/")
    print("Generated systemd network files: ./dev_root/etc/systemd/network/")
    print("Isolated D-Bus: Yes (using private bus)")
    print("Mock Mode: Yes (no root modifications, mock network file writes only)")
    print("Press Ctrl+C to stop the sandbox.")
    print("---------------------------------------------------\n")

    # Keep script running and handle graceful shutdown
    def graceful_shutdown(signum: int, frame: any) -> None:
        print("\nShutting down dev sandbox and processes...")
        # Terminate in reverse order (web -> daemon -> dbus)
        for proc in reversed(processes):
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("Dev sandbox stopped successfully.")
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Wait for processes
    try:
        while True:
            # Check if any child process died unexpectedly
            for proc in processes:
                if proc.poll() is not None:
                    print(f"Child process {proc.pid} died unexpectedly. Shutting down...", file=sys.stderr)
                    graceful_shutdown(None, None)
            time.sleep(1)
    except KeyboardInterrupt:
        graceful_shutdown(None, None)

if __name__ == "__main__":
    main()
