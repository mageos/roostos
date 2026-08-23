#!/bin/bash
set -e

ROUTER_GATEWAY="${ROUTER_GATEWAY:-}"

if [ -n "$ROUTER_GATEWAY" ]; then
    echo "Configuring default gateway via $ROUTER_GATEWAY..."
    # Replace default route with the router gateway
    ip route del default 2>/dev/null || true
    ip route add default via "$ROUTER_GATEWAY" 2>/dev/null || true
fi

echo "Client Node started with IP $(hostname -I)"

# Keep container running and responsive to signals
exec tail -f /dev/null
