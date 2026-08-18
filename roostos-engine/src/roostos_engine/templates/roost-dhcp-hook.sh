#!/usr/bin/env bash
# RoostOS Kea DHCP run-script Hook
# Triggered by Kea DHCP server when leases are committed, renewed, or released.

set -e

# Debug: Dump all environment variables to diagnose variable names
env > /tmp/kea_hook_env.txt
echo "Event: $1" >> /tmp/kea_hook_env.txt


# Setup session argument for local testing sandbox runs (env var check)
DBUS_ARGS="--system"
if [ -n "$DBUS_SESSION_BUS_ADDRESS" ]; then
    DBUS_ARGS="--session"
fi

EVENT="$1" # Kea passes the event name as the first argument to the script

# Translate Kea variables (passed as env variables)
# Support the array-based format: LEASES4_AT0_HWADDR
# Fallback to KEA_LEASE_HWADDR and KEA_LEASE4_HWADDR
MAC="${LEASES4_AT0_HWADDR:-${KEA_LEASE_HWADDR:-$KEA_LEASE4_HWADDR}}"
IP="${LEASES4_AT0_ADDRESS:-${KEA_LEASE_ADDRESS:-$KEA_LEASE4_ADDRESS}}"
HOSTNAME="${LEASES4_AT0_HOSTNAME:-${KEA_LEASE_HOSTNAME:-${KEA_LEASE4_HOSTNAME:-""}}}"

if [ -z "$MAC" ] || [ -z "$IP" ]; then
    echo "Warning: DHCP hook triggered with empty MAC or IP (Event: $EVENT). Skipping." >&2
    exit 0
fi

# Locate dbus-send command using absolute path fallbacks
DBUS_SEND="dbus-send"
if [ -x "/usr/bin/dbus-send" ]; then
    DBUS_SEND="/usr/bin/dbus-send"
elif [ -x "/bin/dbus-send" ]; then
    DBUS_SEND="/bin/dbus-send"
fi

case "$EVENT" in
    "lease4_select" | "lease4_renew" | "leases4_committed" | "lease4_committed" | "lease4_commit")
        $DBUS_SEND $DBUS_ARGS \
            --dest=org.roostos.Daemon \
            --type=method_call \
            --print-reply \
            /org/roostos/Daemon \
            org.roostos.Daemon.RegisterLease \
            string:"$MAC" string:"$IP" string:"$HOSTNAME" > /dev/null
        ;;
    "lease4_release" | "lease4_expire" | "leases4_released" | "leases4_expired")
        $DBUS_SEND $DBUS_ARGS \
            --dest=org.roostos.Daemon \
            --type=method_call \
            --print-reply \
            /org/roostos/Daemon \
            org.roostos.Daemon.ReleaseLease \
            string:"$MAC" > /dev/null
        ;;
    *)
        # Unknown/other Kea lease events
        ;;
esac

exit 0
