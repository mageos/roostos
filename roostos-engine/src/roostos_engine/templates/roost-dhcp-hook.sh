#!/usr/bin/env bash
# RoostOS Kea DHCP run-script Hook
# Triggered by Kea DHCP server when leases are committed, renewed, or released.

set -e

# Setup session argument for local testing sandbox runs (env var check)
DBUS_ARGS="--system"
if [ -n "$DBUS_SESSION_BUS_ADDRESS" ]; then
    DBUS_ARGS="--session"
fi

EVENT="$1" # Kea passes the event name as the first argument to the script

# Translate Kea variables (passed as env variables)
MAC="$KEA_LEASE4_HWADDR"
IP="$KEA_LEASE4_ADDRESS"
HOSTNAME="${KEA_LEASE4_HOSTNAME:-""}"

if [ -z "$MAC" ] || [ -z "$IP" ]; then
    echo "Warning: DHCP hook triggered with empty MAC or IP. Skipping." >&2
    exit 0
fi

case "$EVENT" in
    "lease4_select" | "lease4_renew" | "lease4_commit")
        dbus-send $DBUS_ARGS \
            --dest=org.roostos.Daemon \
            --type=method_call \
            --print-reply \
            /org/roostos/Daemon \
            org.roostos.Daemon.RegisterLease \
            string:"$MAC" string:"$IP" string:"$HOSTNAME" > /dev/null
        ;;
    "lease4_release" | "lease4_expire")
        dbus-send $DBUS_ARGS \
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
