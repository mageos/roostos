#!/usr/bin/env bash
# RoostOS Automated Debian Package Installation & Purge Verification in Docker
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$SRC_DIR/dist/debs"
DOCKER_IMAGE="${IMAGE:-"debian:12-slim"}"
FORCE_BUILD=false

for arg in "$@"; do
    case "$arg" in
        --build)
            FORCE_BUILD=true
            ;;
        --image=*)
            DOCKER_IMAGE="${arg#*=}"
            ;;
        --help|-h)
            echo "Usage: $0 [--build] [--image=<docker_image>]"
            echo "Defaults: image=debian:12-slim"
            exit 0
            ;;
    esac
done

echo "============================================================"
echo "RoostOS Debian Package Docker Verification"
echo "Target Image: $DOCKER_IMAGE"
echo "Packages Directory: $DIST_DIR"
echo "============================================================"

# Verify Docker availability
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running or inaccessible." >&2
    exit 1
fi

# Detect host architecture
HOST_ARCH="$(dpkg --print-architecture 2>/dev/null || uname -m)"
case "$HOST_ARCH" in
    x86_64) HOST_ARCH="amd64" ;;
    aarch64) HOST_ARCH="arm64" ;;
esac

# Build packages if missing or requested
RUNTIME_DEB="$(ls "$DIST_DIR"/roostos-runtime_*_"${HOST_ARCH}".deb 2>/dev/null | head -n 1 || true)"
if [[ "$FORCE_BUILD" == "true" ]] || [[ -z "$RUNTIME_DEB" ]]; then
    echo "[1/4] Building latest RoostOS Debian packages for $HOST_ARCH..."
    ARCH="$HOST_ARCH" bash "$SRC_DIR/scripts/build-all-debs.sh" "$HOST_ARCH"
else
    echo "[1/4] Using existing packages in $DIST_DIR"
fi

echo "[2/4] Pulling test docker image: $DOCKER_IMAGE..."
docker pull "$DOCKER_IMAGE"

echo "[3/4] Running installation and execution verification..."
docker run --rm \
    -v "$DIST_DIR:/tmp/debs:ro" \
    "$DOCKER_IMAGE" \
    bash -euo pipefail -c "
        export DEBIAN_FRONTEND=noninteractive
        echo '--- Updating package lists ---'
        apt-get update -qq

        echo '--- Step A: Testing roostos-runtime install ---'
        apt-get install -y /tmp/debs/roostos-runtime_*_${HOST_ARCH}.deb

        echo '--- Step B: Verifying bundled Python 3.13 runtime ---'
        /usr/lib/roostos/runtime/bin/python3 -c \"import sys, pydantic, fastapi, yaml; print(f'✓ Python runtime operational: {sys.version}')\"

        echo '--- Step C: Installing all RoostOS modular packages ---'
        apt-get install -y /tmp/debs/*_${HOST_ARCH}.deb /tmp/debs/*_all.deb

        echo '--- Step D: Verifying binary entrypoints and CLI tools ---'
        roostos --version
        roostos --help >/dev/null
        echo '✓ roostos CLI operational'

        roostos-node --help >/dev/null
        echo '✓ roostos-node operational'

        roostos-engine --help >/dev/null
        echo '✓ roostos-engine operational'

        /usr/local/bin/roostos-timeguardd --help >/dev/null
        echo '✓ roostos-timeguardd operational'

        echo '--- Step E: Verifying internal Python module imports ---'
        /usr/lib/roostos/runtime/bin/python3 -c \"import roostos_engine, roostos_web, roostos_cli, roostos_timeguardd, roostos_sdk; print('✓ All RoostOS modules imported cleanly')\"

        echo '--- Step F: Testing package uninstallation and purge ---'
        apt-get purge -y roostos roostos-*
        
        echo '--- Step G: Verifying filesystem cleanup ---'
        if [ -f /usr/bin/roostos ]; then
            echo 'Error: /usr/bin/roostos still exists after purge!' >&2
            exit 1
        fi
        if [ -d /usr/lib/roostos ]; then
            echo 'Error: /usr/lib/roostos still exists after purge!' >&2
            exit 1
        fi
        echo '✓ Package purge verified cleanly'
    "

echo "============================================================"
echo "✓ SUCCESS: All RoostOS Debian packages verified on $DOCKER_IMAGE!"
echo "============================================================"
