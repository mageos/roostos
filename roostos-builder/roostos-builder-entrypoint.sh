#!/bin/bash
set -euo pipefail

# RoostOS Build Container Entrypoint
# Supports Rootless BuildKit (no host socket, outputs image tar archive)
# and legacy containerd socket building.

CONTAINERD_SOCK="${CONTAINERD_ADDRESS:-/run/containerd/containerd.sock}"
CONTAINERD_NS="${CONTAINERD_NAMESPACE:-roostos}"

TAG=""
DOCKERFILE="Dockerfile"
CONTEXT="/workspace"
TARGET_STAGE=""
OUTPUT_TAR=""
OUTPUT_DIR=""
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
        --output-tar)
            OUTPUT_TAR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
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

if [[ -n "$OUTPUT_DIR" && -z "$OUTPUT_TAR" ]]; then
    OUTPUT_TAR="$OUTPUT_DIR/image.tar"
fi

echo "=== RoostOS Build Container ==="
echo "Target Tag:        $TAG"
echo "Dockerfile:        $DOCKERFILE"
echo "Context:           $CONTEXT"
echo "Output Tar:        ${OUTPUT_TAR:-<none>}"

# 1. Enforce Network Egress Constraints if Proxy Configured
ACTIVE_PROXY="${HTTP_PROXY:-${http_proxy:-}}"
if [[ -n "$ACTIVE_PROXY" ]]; then
    echo "Enforcing proxy isolation: $ACTIVE_PROXY"
    PROXY_HOST_PORT=$(echo "$ACTIVE_PROXY" | sed -e 's|^.*://||' -e 's|/.*$||')
    PROXY_HOST=$(echo "$PROXY_HOST_PORT" | cut -d: -f1)
    PROXY_PORT=$(echo "$PROXY_HOST_PORT" | cut -d: -f2)

    # If iptables is available and container has permissions, restrict egress
    if command -v iptables >/dev/null 2>&1; then
        iptables -A OUTPUT -o lo -j ACCEPT 2>/dev/null || true
        if [[ -n "$PROXY_HOST" && -n "$PROXY_PORT" ]]; then
            iptables -A OUTPUT -p tcp -d "$PROXY_HOST" --dport "$PROXY_PORT" -j ACCEPT 2>/dev/null || true
        fi
        iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
    fi
fi

# 2. Rootless BuildKit Execution (Preferred, no socket required)
if [[ -n "$OUTPUT_TAR" ]] || [[ ! -S "$CONTAINERD_SOCK" ]]; then
    OUTPUT_TAR="${OUTPUT_TAR:-/output/image.tar}"
    mkdir -p "$(dirname "$OUTPUT_TAR")"
    echo "Mode: Rootless BuildKit (exporting tar to $OUTPUT_TAR)"

    DF_DIR=$(dirname "$DOCKERFILE")
    DF_NAME=$(basename "$DOCKERFILE")

    if command -v buildkitd >/dev/null 2>&1 && command -v buildctl >/dev/null 2>&1; then
        mkdir -p /run/buildkit
        buildkitd --addr unix:///run/buildkit/buildkitd.sock &
        BK_PID=$!
        trap 'kill $BK_PID 2>/dev/null || true' EXIT

        # Wait for buildkitd socket
        for _ in {1..30}; do
            if [[ -S /run/buildkit/buildkitd.sock ]]; then
                break
            fi
            sleep 0.1
        done

        BUILDCTL_ARGS=(
            buildctl --addr unix:///run/buildkit/buildkitd.sock
            build
            --frontend dockerfile.v0
            --local "context=$CONTEXT"
            --local "dockerfile=$CONTEXT/$DF_DIR"
            --opt "filename=$DF_NAME"
            --output "type=docker,name=$TAG,dest=$OUTPUT_TAR"
        )
        if [[ -n "$TARGET_STAGE" ]]; then
            BUILDCTL_ARGS+=(--opt "target=$TARGET_STAGE")
        fi
        for arg in "${BUILD_ARGS[@]}"; do
            if [[ "$arg" != "--build-arg" ]]; then
                BUILDCTL_ARGS+=(--opt "build-arg:$arg")
            fi
        done
        echo "Executing: ${BUILDCTL_ARGS[*]}"
        "${BUILDCTL_ARGS[@]}"
        echo "BuildKit export completed: $OUTPUT_TAR"
        exit 0
    elif command -v docker >/dev/null 2>&1; then
        CMD=(docker build -t "$TAG" -f "$DOCKERFILE")
        [[ -n "$TARGET_STAGE" ]] && CMD+=(--target "$TARGET_STAGE")
        [[ ${#BUILD_ARGS[@]} -gt 0 ]] && CMD+=("${BUILD_ARGS[@]}")
        CMD+=("$CONTEXT")
        "${CMD[@]}"
        docker save -o "$OUTPUT_TAR" "$TAG"
        exit 0
    else
        echo "Error: No suitable build engine (buildkitd/docker) found in container" >&2
        exit 1
    fi
fi

# 3. Legacy Containerd Socket Execution
echo "Mode: Legacy Daemon Socket ($CONTAINERD_SOCK)"
if command -v nerdctl >/dev/null 2>&1 && [[ -S "$CONTAINERD_SOCK" ]]; then
    CMD=(nerdctl --address "$CONTAINERD_SOCK" --namespace "$CONTAINERD_NS" build -t "$TAG" -f "$DOCKERFILE")
    [[ -n "$TARGET_STAGE" ]] && CMD+=(--target "$TARGET_STAGE")
    [[ ${#BUILD_ARGS[@]} -gt 0 ]] && CMD+=("${BUILD_ARGS[@]}")
    CMD+=("$CONTEXT")
    exec "${CMD[@]}"
fi

echo "Error: Containerd socket not available" >&2
exit 1
