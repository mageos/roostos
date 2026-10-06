#!/usr/bin/env bash
# RoostOS Unified Debian Package Build Script
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_VERSION="0.1.1"
if [[ -f "$SRC_DIR/VERSION" ]]; then
    PACKAGE_VERSION="$(tr -d '[:space:]' < "$SRC_DIR/VERSION")"
fi
BUILD_DIR="$SRC_DIR/build-deb-tmp"
DIST_DIR="$SRC_DIR/dist/debs"

if [[ -n "$1" ]]; then
    ARCHITECTURES="$*"
elif [[ -n "$ARCH" ]]; then
    ARCHITECTURES="$ARCH"
else
    ARCHITECTURES="${ARCHITECTURES:-"amd64"}"
fi
ARCHITECTURES="${ARCHITECTURES//,/ }"

# Detect host architecture
HOST_ARCH="$(dpkg --print-architecture 2>/dev/null || true)"
if [[ -z "$HOST_ARCH" ]]; then
    case "$(uname -m)" in
        x86_64) HOST_ARCH="amd64" ;;
        aarch64|arm64) HOST_ARCH="arm64" ;;
        armv7l|armhf) HOST_ARCH="armhf" ;;
        *) HOST_ARCH="$(uname -m)" ;;
    esac
fi

# Automatically dispatch foreign architectures to Docker if cross-building
if [[ -z "${ROOSTOS_DOCKER_BUILD:-}" ]]; then
    NATIVE_ARCHS=()
    DOCKER_ARCHS=()
    for arch in $ARCHITECTURES; do
        if [[ "$arch" == "$HOST_ARCH" ]]; then
            NATIVE_ARCHS+=("$arch")
        else
            DOCKER_ARCHS+=("$arch")
        fi
    done

    for arch in "${DOCKER_ARCHS[@]}"; do
        if ! command -v docker >/dev/null 2>&1; then
            echo "Error: Architecture '$arch' does not match host '$HOST_ARCH', and Docker is unavailable." >&2
            exit 1
        fi
        docker_platform="linux/$arch"
        if [[ "$arch" == "armhf" ]]; then
            docker_platform="linux/arm/v7"
        fi
        echo "============================================="
        echo "Cross-building Unified RoostOS Debian package for $arch via Docker ($docker_platform)"
        echo "============================================="
        BUILDER_IMAGE="roostos-deb-builder:$arch"
        if ! docker image inspect "$BUILDER_IMAGE" >/dev/null 2>&1; then
            docker build --platform "$docker_platform" -t "$BUILDER_IMAGE" -f "$SRC_DIR/packaging/debian/Dockerfile.builder" "$SRC_DIR/packaging/debian"
        fi
        HOST_UID=$(id -u)
        HOST_GID=$(id -g)
        docker run --rm \
            --platform "$docker_platform" \
            -v "$SRC_DIR:/workspace" \
            -v "roostos-uv-cache-$arch:/root/.cache/uv" \
            -w /workspace \
            -e ROOSTOS_DOCKER_BUILD=1 \
            "$BUILDER_IMAGE" \
            bash -c "bash scripts/build-all-debs.sh '$arch' && chown -R $HOST_UID:$HOST_GID dist build-deb-tmp 2>/dev/null || true"
    done

    if [[ ${#NATIVE_ARCHS[@]} -eq 0 ]]; then
        exit 0
    fi
    ARCHITECTURES="${NATIVE_ARCHS[*]}"
fi

echo "============================================="
echo "Building Unified RoostOS Debian Package"
echo "Version: $PACKAGE_VERSION"
echo "Target Architectures: $ARCHITECTURES"
echo "Output Directory: $DIST_DIR"
echo "============================================="

rm -rf "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

# 1. Prepare standalone Python 3.13 and locked requirements
uv python install 3.13
STANDALONE_PYTHON="$(uv python list --only-installed 2>/dev/null | grep -E '^cpython-3\.13' | awk '{print $2}' | head -n 1)"
if [[ -n "$STANDALONE_PYTHON" && -x "$STANDALONE_PYTHON" ]]; then
    REAL_PYTHON="$(readlink -f "$STANDALONE_PYTHON")"
elif [[ -x "$SRC_DIR/.venv/bin/python3" ]]; then
    REAL_PYTHON="$(readlink -f "$SRC_DIR/.venv/bin/python3")"
else
    REAL_PYTHON="$(which python3)"
fi
PYTHON_PREFIX="$(dirname "$(dirname "$REAL_PYTHON")")"
uv export --no-dev --no-emit-workspace > "$BUILD_DIR/requirements-runtime.txt"

for arch in $ARCHITECTURES; do
    STAGE_DIR="$BUILD_DIR/roostos-$arch"
    RUNTIME_TARGET="$STAGE_DIR/usr/lib/roostos/runtime"
    rm -rf "$STAGE_DIR"
    mkdir -p "$RUNTIME_TARGET" "$STAGE_DIR/usr/bin" "$STAGE_DIR/usr/local/bin" \
             "$STAGE_DIR/usr/share/roostos/web" "$STAGE_DIR/etc/systemd/system" \
             "$STAGE_DIR/etc/dbus-1/system.d" "$STAGE_DIR/DEBIAN"

    echo "--- Staging Runtime & Packages for $arch ---"
    cp -a "$PYTHON_PREFIX/"* "$RUNTIME_TARGET/"

    echo "Installing locked virtualenv dependencies..."
    uv pip install --break-system-packages --python "$RUNTIME_TARGET/bin/python3" -r "$BUILD_DIR/requirements-runtime.txt"
    uv pip install --break-system-packages --no-deps --python "$RUNTIME_TARGET/bin/python3" \
        "$SRC_DIR/roostos-sdk" \
        "$SRC_DIR/roostos-engine" \
        "$SRC_DIR/roostos-cli" \
        "$SRC_DIR/roostos-web" \
        "$SRC_DIR/roostos-timeguardd" \
        "$SRC_DIR/roostos-dns-technitium" \
        "$SRC_DIR/roostos-identity-samba"

    # Clean development editable references and standardize python shebangs
    find "$RUNTIME_TARGET" -name "*_editable_impl*.pth" -delete 2>/dev/null || true
    sed -i "s|#!.*python.*|#!/usr/lib/roostos/runtime/bin/python3|" "$RUNTIME_TARGET/bin/"* 2>/dev/null || true

    # 2. Binary and entrypoint wrappers
    cat << 'EOF' > "$STAGE_DIR/usr/bin/roostos"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_cli.main "$@"
EOF
    chmod 755 "$STAGE_DIR/usr/bin/roostos"

    cat << 'EOF' > "$STAGE_DIR/usr/bin/roostos-node"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_web.main "$@"
EOF
    chmod 755 "$STAGE_DIR/usr/bin/roostos-node"
    ln -s roostos-node "$STAGE_DIR/usr/bin/roostos-web"

    cat << 'EOF' > "$STAGE_DIR/usr/bin/roostos-engine"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_engine.daemon "$@"
EOF
    chmod 755 "$STAGE_DIR/usr/bin/roostos-engine"
    ln -s roostos-engine "$STAGE_DIR/usr/bin/roostd"

    cat << 'EOF' > "$STAGE_DIR/usr/local/bin/roostos-timeguardd"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_timeguardd.main "$@"
EOF
    chmod 755 "$STAGE_DIR/usr/local/bin/roostos-timeguardd"

    # Helper scripts and local bin symlinks
    ln -sf /usr/bin/roostos "$STAGE_DIR/usr/local/bin/roostos"
    ln -sf /usr/bin/roostd "$STAGE_DIR/usr/local/bin/roostd"
    ln -sf /usr/bin/roostos-engine "$STAGE_DIR/usr/local/bin/roostos-engine"
    ln -sf /usr/bin/roostos-node "$STAGE_DIR/usr/local/bin/roostos-node"
    ln -sf /usr/bin/roostos-web "$STAGE_DIR/usr/local/bin/roostos-web"
    cp "$SRC_DIR/roostos-engine/src/roostos_engine/templates/roost-dhcp-hook.sh" "$STAGE_DIR/usr/local/bin/roost-dhcp-hook" 2>/dev/null || true
    cp "$SRC_DIR/scripts/roostos-workstation-join.sh" "$STAGE_DIR/usr/local/bin/roostos-workstation-join" 2>/dev/null || true
    cp "$SRC_DIR/scripts/roostos-workstation-enroll.sh" "$STAGE_DIR/usr/local/bin/roostos-workstation-enroll" 2>/dev/null || true
    cp "$SRC_DIR/scripts/roostos-edge-setup.sh" "$STAGE_DIR/usr/local/bin/roostos-edge-setup" 2>/dev/null || true
    chmod 755 "$STAGE_DIR/usr/local/bin/"* 2>/dev/null || true

    # 3. Web UI Assets
    cp -r "$SRC_DIR/roostos-ui/"* "$STAGE_DIR/usr/share/roostos/web/" 2>/dev/null || true
    rm -rf "$STAGE_DIR/usr/share/roostos/web/node_modules" \
           "$STAGE_DIR/usr/share/roostos/web/"*.test.js \
           "$STAGE_DIR/usr/share/roostos/web/package.json" \
           "$STAGE_DIR/usr/share/roostos/web/package-lock.json" 2>/dev/null || true

    # 4. DBus configuration
    cp "$SRC_DIR/packaging/common/dbus/org.roostos.conf" "$STAGE_DIR/etc/dbus-1/system.d/" 2>/dev/null || true

    # 5. Systemd services
    cat << 'EOF' > "$STAGE_DIR/etc/systemd/system/roostos-node.service"
[Unit]
Description=RoostOS Local Node Agent and REST API
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/roostos-node
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
Alias=roostos-web.service
EOF
    ln -s roostos-node.service "$STAGE_DIR/etc/systemd/system/roostos-web.service"
    cp "$SRC_DIR/packaging/common/systemd/roostos-engine.service" "$STAGE_DIR/etc/systemd/system/" 2>/dev/null || true
    cp "$SRC_DIR/packaging/common/systemd/roostos-timeguardd.service" "$STAGE_DIR/etc/systemd/system/" 2>/dev/null || true

    # 6. Debian control and maintainer scripts
    cat << EOF > "$STAGE_DIR/DEBIAN/control"
Package: roostos
Version: $PACKAGE_VERSION
Section: admin
Priority: optional
Architecture: $arch
Depends: libc6 (>= 2.31)
Recommends: nftables, wireguard
Suggests: kea-dhcp4-server, mosquitto
Provides: roostos-runtime, roostos-cli, roostos-node, roostos-web, roostos-gateway, roostos-core, roostos-engine, roostos-workstation, roostos-timeguardd, roostos-edge-node, roostos-router, roostos-gateway-node, roostos-controller-node
Replaces: roostos-runtime, roostos-cli, roostos-node, roostos-web, roostos-gateway, roostos-core, roostos-engine, roostos-workstation, roostos-timeguardd, roostos-edge-node, roostos-router, roostos-gateway-node, roostos-controller-node
Conflicts: roostos-core (<< 0.1.0)
Maintainer: RoostOS Core Team <info@roostos.org>
Description: RoostOS Unified Family Router & Local Infrastructure Management System
 RoostOS provides unified routing, firewall management, parental screen-time controls,
 local DNS/DHCP administration, and cluster synchronization.
EOF

    cp "$SRC_DIR/packaging/debian/postinst" "$STAGE_DIR/DEBIAN/postinst"
    cp "$SRC_DIR/packaging/debian/prerm" "$STAGE_DIR/DEBIAN/prerm"
    cp "$SRC_DIR/packaging/debian/postrm" "$STAGE_DIR/DEBIAN/postrm"
    chmod 755 "$STAGE_DIR/DEBIAN/postinst" "$STAGE_DIR/DEBIAN/prerm" "$STAGE_DIR/DEBIAN/postrm"

    deb_filename="roostos_${PACKAGE_VERSION}_${arch}.deb"
    echo "--- Packing: $deb_filename ---"
    dpkg-deb --root-owner-group --build "$STAGE_DIR" "$DIST_DIR/$deb_filename"
    echo "✓ Built: $DIST_DIR/$deb_filename"
done

echo "============================================="
echo "RoostOS Unified Debian Package Built Successfully!"
echo "Artifacts located in: $DIST_DIR"
echo "============================================="
