#!/bin/bash
set -euo pipefail

# RoostOS Build Container Entrypoint
# Communicates with mounted containerd socket and builds image from source volume.

CONTAINERD_SOCK="${CONTAINERD_ADDRESS:-/run/containerd/containerd.sock}"
CONTAINERD_NS="${CONTAINERD_NAMESPACE:-roostos}"

TAG=""
DOCKERFILE="Dockerfile"
CONTEXT="/workspace"
TARGET_STAGE=""
BUILD_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)
            TAG="$2"
            shift 2
            ;;
        --dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        --context)
            CONTEXT="$2"
            shift 2
            ;;
        --target)
            TARGET_STAGE="$2"
            shift 2
            ;;
        --build-arg)
            BUILD_ARGS+=("--build-arg" "$2")
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            shift
            ;;
    esac
done

if [[ -z "$TAG" ]]; then
    echo "Error: --tag is required" >&2
    exit 1
fi

echo "=== RoostOS Build Container ==="
echo "Target Tag:        $TAG"
echo "Dockerfile:        $DOCKERFILE"
echo "Context:           $CONTEXT"
echo "Containerd Socket: $CONTAINERD_SOCK"
echo "Namespace:         $CONTAINERD_NS"

# Verify containerd socket exists
if [[ ! -S "$CONTAINERD_SOCK" ]]; then
    echo "Warning: Containerd socket not found at $CONTAINERD_SOCK" >&2
    if [[ -S "/var/run/docker.sock" ]]; then
        CONTAINERD_SOCK="/var/run/docker.sock"
        echo "Using fallback socket: $CONTAINERD_SOCK"
    fi
fi

# Execute build with nerdctl or docker
if command -v nerdctl >/dev/null 2>&1 && [[ -S "$CONTAINERD_SOCK" ]]; then
    CMD=(nerdctl --address "$CONTAINERD_SOCK" --namespace "$CONTAINERD_NS" build -t "$TAG" -f "$DOCKERFILE")
    if [[ -n "$TARGET_STAGE" ]]; then
        CMD+=(--target "$TARGET_STAGE")
    fi
    if [[ ${#BUILD_ARGS[@]} -gt 0 ]]; then
        CMD+=("${BUILD_ARGS[@]}")
    fi
    CMD+=("$CONTEXT")
    echo "Executing: ${CMD[*]}"
    exec "${CMD[@]}"
elif command -v docker >/dev/null 2>&1; then
    CMD=(docker build -t "$TAG" -f "$DOCKERFILE")
    if [[ -n "$TARGET_STAGE" ]]; then
        CMD+=(--target "$TARGET_STAGE")
    fi
    if [[ ${#BUILD_ARGS[@]} -gt 0 ]]; then
        CMD+=("${BUILD_ARGS[@]}")
    fi
    CMD+=("$CONTEXT")
    echo "Executing fallback: ${CMD[*]}"
    exec "${CMD[@]}"
else
    echo "Error: No suitable build engine (nerdctl/docker) found in build container" >&2
    exit 1
fi
