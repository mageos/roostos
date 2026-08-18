#!/usr/bin/env bash
# RoostOS Compute Node Installer
# Installs and registers a worker node to the RoostOS K3s cluster.

set -euo pipefail

MASTER_IP=""
CLUSTER_TOKEN=""

usage() {
    echo "Usage: $0 --master <MASTER_IP> --token <CLUSTER_TOKEN>"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --master)
            MASTER_IP="$2"
            shift 2
            ;;
        --token)
            CLUSTER_TOKEN="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

if [[ -z "$MASTER_IP" || -z "$CLUSTER_TOKEN" ]]; then
    echo "Error: Both --master and --token are required."
    usage
fi

# Ensure running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root." 
   exit 1
fi

echo "========================================="
echo "Starting RoostOS Compute Node Provisioning"
echo "========================================="

# 1. Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "Detected OS: $NAME ($VERSION)"
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" && "$LIKE" != *"debian"* ]]; then
        echo "Warning: This installer is optimized for Debian/Ubuntu systems."
    fi
else
    echo "Error: Cannot identify OS distribution."
    exit 1
fi

# 2. Check architecture
ARCH=$(uname -m)
echo "Architecture: $ARCH"

# 3. Install dependencies
echo "Installing prerequisites..."
apt-get update -y
apt-get install -y curl conntrack iptables

# 4. Install K3s agent
echo "Installing K3s Agent pointing to Master at https://${MASTER_IP}:6443..."
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" K3S_TOKEN="${CLUSTER_TOKEN}" sh -

echo "========================================="
echo "RoostOS Compute Node Successfully Configured!"
echo "Status: Active / Connecting"
echo "========================================="
