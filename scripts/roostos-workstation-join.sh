#!/usr/bin/env bash
# RoostOS Workstation Domain Join Utility
# Joins a Linux client (Ubuntu/Debian, Arch Linux, Fedora) to the RoostOS Active Directory / Samba Domain.
set -euo pipefail

REALM="ROOSTOS.LOCAL"
DC_HOST="roost-router.lan"
ADMIN_USER="Administrator"
DRY_RUN=false
POS_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            echo "Usage: $0 [REALM] [DC_HOST] [ADMIN_USER] [--dry-run]"
            echo "Example: sudo $0 ROOSTOS.LOCAL 192.168.1.1 Administrator"
            exit 0
            ;;
        *)
            POS_ARGS+=("$arg")
            ;;
    esac
done

if [ ${#POS_ARGS[@]} -ge 1 ]; then REALM="${POS_ARGS[0]}"; fi
if [ ${#POS_ARGS[@]} -ge 2 ]; then DC_HOST="${POS_ARGS[1]}"; fi
if [ ${#POS_ARGS[@]} -ge 3 ]; then ADMIN_USER="${POS_ARGS[2]}"; fi

echo "========================================================"
echo "  RoostOS Client Workstation Domain Enrollment"
echo "  Target Realm: $REALM"
echo "  Domain Controller: $DC_HOST"
echo "========================================================"

if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] Would install SSSD, realmd, adcli, krb5 packages."
    echo "[DRY-RUN] Would discover realm '$REALM'."
    echo "[DRY-RUN] Would configure PAM automatic home directory creation."
    echo "[DRY-RUN] Would join workstation to realm '$REALM' using '$ADMIN_USER'."
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)." >&2
    exit 1
fi

# 1. Package Installation
echo "[1/4] Installing Required SSSD & Realm Packages..."
if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq sssd-ad sssd-tools realmd adcli packagekit libpam-sss libnss-sss oddjob-mkhomedir
elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm sssd adcli realmd krb5
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y -q sssd realmd adcli oddjob-mkhomedir krb5-workstation
else
    echo "Warning: Unsupported package manager. Ensure sssd and realmd are installed manually."
fi

# 2. Discover Domain
echo "[2/4] Discovering Realm '$REALM'..."
realm discover "$REALM" || echo "Discovery complete."

# 3. Configure PAM Home Directory Creation
echo "[3/4] Enabling PAM Home Directory Creation..."
if command -v pam-auth-update >/dev/null 2>&1; then
    pam-auth-update --enable mkhomedir
elif command -v authselect >/dev/null 2>&1; then
    authselect select sssd with-mkhomedir --force || true
fi

# 4. Join Domain
echo "[4/4] Joining Workstation to Realm '$REALM'..."
realm join --user="$ADMIN_USER" "$REALM"

# Restart SSSD service
systemctl restart sssd || true

echo "========================================================"
echo "  Success! This workstation is now enrolled in $REALM."
echo "  Users can log in with: username (or $REALM\\username)"
echo "========================================================"
