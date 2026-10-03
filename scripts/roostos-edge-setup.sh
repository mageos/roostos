#!/usr/bin/env bash
# RoostOS Edge Gateway VPS Automated Setup & Provisioning Script
# Prepares a Debian/Ubuntu VPS to serve as an ingress static IP entrypoint and CGNAT bypass.

set -euo pipefail

WAN_IF=""
TTL_MINUTES="15"
PORT="8000"

usage() {
    echo "Usage: sudo $0 [--wan <INTERFACE>] [--port <PORT>] [--ttl <MINUTES>]"
    echo "Example: sudo $0 --wan eth0 --ttl 15"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan)
            WAN_IF="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --ttl)
            TTL_MINUTES="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            ;;
    esac
done

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Error: This installer must be run as root (sudo)." >&2
    exit 1
fi

echo "========================================================"
echo "         RoostOS Cloud Edge Gateway Provisioner         "
echo "========================================================"

# 1. Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "Detected OS: $NAME ($VERSION)"
else
    echo "Error: Cannot identify OS distribution."
    exit 1
fi

# 2. Detect public IP
echo "[1/5] Detecting VPS network configuration..."
PUBLIC_IP=$(curl -s -4 --max-time 3 https://ifconfig.me || curl -s -4 --max-time 3 https://api.ipify.org || true)
if [[ -z "$PUBLIC_IP" ]]; then
    PUBLIC_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' || echo "127.0.0.1")
fi
echo "Public Static IP: $PUBLIC_IP"

# 3. Detect WAN interface
if [[ -z "$WAN_IF" ]]; then
    WAN_IF=$(ip route show default 2>/dev/null | awk '/default/ {print $5}' | head -n 1 || echo "eth0")
fi
echo "Default Network Interface: $WAN_IF"

# 4. Install dependencies
echo "[2/5] Installing core networking and proxy packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wireguard wireguard-tools nftables python3 python3-pip python3-jwt curl docker.io

# 5. Provision Nginx Ingress Container
echo "[3/5] Starting containerized Nginx ingress proxy..."
mkdir -p /etc/roostos/nginx/conf.d
mkdir -p /etc/roostos/certs

# Generate initial fallback config
cat << 'EOF' > /etc/roostos/nginx/conf.d/default.conf
server {
    listen 80 default_server;
    server_name _;
    location / {
        return 200 "RoostOS Edge Gateway Ingress is Active.\n";
    }
}
EOF

if command -v docker >/dev/null 2>&1; then
    docker stop roostos-ingress 2>/dev/null || true
    docker rm roostos-ingress 2>/dev/null || true
    docker run -d \
        --name roostos-ingress \
        --restart always \
        --network host \
        -v /etc/roostos/nginx/conf.d:/etc/nginx/conf.d:ro \
        -v /etc/roostos/certs:/etc/roostos/certs:ro \
        nginx:alpine || true
fi

# 6. Configure RoostOS Node role
echo "[4/5] Configuring RoostOS Edge Gateway role..."
if command -v roostos >/dev/null 2>&1; then
    roostos setup --role edge-gateway --wan "$WAN_IF" --non-interactive || true
    systemctl restart roostos-node 2>/dev/null || true
fi

# 7. Generate Bootstrap Token
echo "[5/5] Generating single-use bootstrap enrollment token..."
TOKEN_CMD="roostos edge token --ip ${PUBLIC_IP} --port ${PORT} --ttl ${TTL_MINUTES}"
if command -v roostos >/dev/null 2>&1; then
    $TOKEN_CMD
else
    # Fallback direct python token generation
    python3 -c "
from roostos_engine.edge_manager import EdgeManager
mgr = EdgeManager()
t = mgr.create_bootstrap_token('$PUBLIC_IP', port=$PORT, ttl_minutes=$TTL_MINUTES)
print('\n==================================================')
print('         RoostOS Edge Gateway Bootstrap Token     ')
print('==================================================\n')
print(f'roost-edge://$PUBLIC_IP:$PORT?token={t.token}\n')
print('Expires in $TTL_MINUTES minutes (single-use)')
print('==================================================')
"
fi
