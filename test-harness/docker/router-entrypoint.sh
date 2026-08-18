#!/bin/bash
set -e

echo "=== Starting RoostOS Router Test Node ==="

# 1. Enable IPv4 and IPv6 Forwarding in the container network namespace
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null 2>&1 || true

# 2. Set up D-Bus daemon
mkdir -p /var/run/dbus
if [ ! -f /var/run/dbus/pid ]; then
    dbus-daemon --system --fork || true
fi

# 3. Establish Config Directory
CONFIG_DIR="${ROOSTOS_CONFIG_DIR:-/etc/roostos}"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/system.yaml" ]; then
    echo "Seeding default test configs into $CONFIG_DIR..."
    cp -r /workspace/test-harness/scenarios/default/* "$CONFIG_DIR/" 2>/dev/null || true
fi

export ROOSTOS_CONFIG_DIR="$CONFIG_DIR"
export ROOSTOS_SESSION_BUS="0"
export ROOSTOS_MOCK_AUTH="1"
export ROOSTOS_WEB_PORT="8000"
export ROOSTOS_NFTABLES_CONF="/etc/nftables.conf"

# 4. Start RoostOS Engine Daemon in background
echo "Starting RoostOS Engine Daemon..."
python3 -m roostos_engine.daemon --config-dir "$CONFIG_DIR" &
ENGINE_PID=$!

# Wait briefly for D-Bus / engine setup
sleep 2

# 5. Start RoostOS Web API & UI Console
echo "Starting RoostOS Web Management Console on port 8000 (Host: 8080)..."
python3 -m roostos_web.main &
WEB_PID=$!

# Function to handle shutdown
cleanup() {
    echo "Terminating RoostOS services..."
    kill -TERM "$WEB_PID" "$ENGINE_PID" 2>/dev/null || true
    wait "$WEB_PID" "$ENGINE_PID" 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "RoostOS Router Node is ready."
wait -n "$ENGINE_PID" "$WEB_PID"
