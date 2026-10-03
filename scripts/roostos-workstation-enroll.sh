#!/usr/bin/env bash
# RoostOS Workstation Unified Enrollment Utility
# Configures a client workstation with RoostOS TimeGuard parental controls and optional Samba AD domain membership.
set -euo pipefail

CONTROLLER_HOST=""
TOKEN=""
REALM="ROOSTOS.LOCAL"
ENABLE_DOMAIN=false
DRY_RUN=false
USERNAME=""

usage() {
    echo "Usage: sudo $0 [--controller <HOST>] [--token <TOKEN>] [--domain] [--user <USERNAME>] [--dry-run]"
    echo "Example: sudo $0 --controller 192.168.1.10 --token roost-1234 --domain --user matt"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --controller)
            CONTROLLER_HOST="$2"
            shift 2
            ;;
        --token)
            TOKEN="$2"
            shift 2
            ;;
        --domain)
            ENABLE_DOMAIN=true
            shift
            ;;
        --user)
            USERNAME="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
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

echo "========================================================"
echo "      RoostOS Client Workstation Enrollment             "
echo "========================================================"

# Auto-discover controller if not specified
if [[ -z "$CONTROLLER_HOST" ]]; then
    echo "Attempting to auto-discover RoostOS Controller..."
    if command -v getent >/dev/null 2>&1 && getent hosts roostos.local >/dev/null 2>&1; then
        CONTROLLER_HOST=$(getent hosts roostos.local | awk '{print $1}')
        echo "Discovered RoostOS Controller via DNS: $CONTROLLER_HOST"
    else
        DEFAULT_GW=$(ip route show default 2>/dev/null | awk '/via/ {print $3}' || true)
        if [[ -n "$DEFAULT_GW" ]]; then
            CONTROLLER_HOST="$DEFAULT_GW"
            echo "Using default gateway as Controller fallback: $CONTROLLER_HOST"
        else
            CONTROLLER_HOST="127.0.0.1"
            echo "Warning: Could not discover controller. Defaulting to 127.0.0.1."
        fi
    fi
fi

if [[ "$DRY_RUN" = true ]]; then
    echo "[DRY-RUN] Controller: $CONTROLLER_HOST"
    echo "[DRY-RUN] Would install roostos-workstation."
    echo "[DRY-RUN] Would configure /etc/roostos-timeguardd/config.json with controller $CONTROLLER_HOST."
    if [[ "$ENABLE_DOMAIN" = true ]]; then
        echo "[DRY-RUN] Would enroll workstation into realm '$REALM' using SSSD."
    fi
    exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

# 1. Install required client packages
echo "[1/3] Installing RoostOS Workstation Client stack..."
if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq || true
    PACKAGES="python3-paho-mqtt dbus"
    if [[ "$ENABLE_DOMAIN" = true ]]; then
        PACKAGES="$PACKAGES sssd-ad sssd-tools realmd adcli packagekit libpam-sss libnss-sss oddjob-mkhomedir"
    fi
    apt-get install -y -qq $PACKAGES || true
fi

# 2. Configure TimeGuard Screen Time Daemon
echo "[2/3] Configuring RoostOS TimeGuard Screen Time Client..."
mkdir -p /etc/roostos-timeguardd
cat << EOF > /etc/roostos-timeguardd/config.json
{
  "mqtt_host": "$CONTROLLER_HOST",
  "mqtt_port": 1883,
  "join_token": "$TOKEN",
  "users": {
    "${USERNAME:-default}": {
      "daily_limit_seconds": 7200
    }
  }
}
EOF

# Setup PAM curfew check hook
if [[ -f /etc/pam.d/common-auth ]]; then
    if ! grep -q "roostos-timeguardd pam-check" /etc/pam.d/common-auth; then
        TMP_PAM=$(mktemp)
        echo "auth    required    pam_exec.so stdout /usr/local/bin/roostos-timeguardd pam-check" | cat - /etc/pam.d/common-auth > "$TMP_PAM" && mv "$TMP_PAM" /etc/pam.d/common-auth
    fi
fi

# Restart TimeGuard service if present
if systemctl is-active --quiet roostos-timeguardd 2>/dev/null; then
    systemctl restart roostos-timeguardd || true
fi

# 3. Optional Domain Enrollment
if [[ "$ENABLE_DOMAIN" = true ]]; then
    echo "[3/3] Enrolling Workstation in RoostOS Active Directory Domain ($REALM)..."
    if command -v realm >/dev/null 2>&1; then
        realm discover "$REALM" || true
        realm join "$REALM" || true
        if command -v pam-auth-update >/dev/null 2>&1; then
            pam-auth-update --enable mkhomedir || true
        fi
        systemctl restart sssd 2>/dev/null || true
    fi
else
    echo "[3/3] Skipping domain join (Local user mode active)."
fi

echo "========================================================"
echo "  Success! Workstation enrolled in RoostOS."
echo "  Connected to Controller: $CONTROLLER_HOST"
echo "========================================================"
