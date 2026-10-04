#!/usr/bin/env bash
# RoostOS Master Multi-Package Build Script
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_VERSION="0.1.1"
if [[ -f "$SRC_DIR/VERSION" ]]; then
    PACKAGE_VERSION="$(tr -d '[:space:]' < "$SRC_DIR/VERSION")"
fi
BUILD_DIR="$SRC_DIR/build-deb-tmp"
DIST_DIR="$SRC_DIR/dist/debs"

if [[ -n "$ARCH" ]]; then
    ARCHITECTURES="$ARCH"
else
    ARCHITECTURES="${ARCHITECTURES:-"amd64"}"
fi

echo "============================================="
echo "Building RoostOS Modular Debian Packages"
echo "Version: $PACKAGE_VERSION"
echo "Target Architectures: $ARCHITECTURES"
echo "Output Directory: $DIST_DIR"
echo "============================================="

rm -rf "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

build_pkg() {
    local pkg_name="$1"
    local pkg_arch="$2"
    local pkg_desc="$3"
    local pkg_deps="$4"
    local stage_path="$BUILD_DIR/$pkg_name"
    local extra_headers="$5"

    echo "--- Building Package: $pkg_name ($pkg_arch) ---"
    mkdir -p "$stage_path/DEBIAN"

    cat <<EOF > "$stage_path/DEBIAN/control"
Package: $pkg_name
Version: $PACKAGE_VERSION
Section: admin
Priority: optional
Architecture: $pkg_arch
Depends: $pkg_deps
Maintainer: RoostOS Core Team <info@roostos.org>
Description: $pkg_desc
EOF

    if [[ -n "$extra_headers" ]]; then
        echo -e "$extra_headers" >> "$stage_path/DEBIAN/control"
    fi

    deb_filename="${pkg_name}_${PACKAGE_VERSION}_${pkg_arch}.deb"
    dpkg-deb --root-owner-group --build "$stage_path" "$DIST_DIR/$deb_filename"
    echo "✓ Built: $DIST_DIR/$deb_filename"
}

# 1. roostos-runtime (Bundled Python 3.13 Runtime & Locked Virtual Environment)
REAL_PYTHON="$(readlink -f "$SRC_DIR/.venv/bin/python3" 2>/dev/null || which python3)"
PYTHON_PREFIX="$(dirname "$(dirname "$REAL_PYTHON")")"
uv export --no-dev > "$BUILD_DIR/requirements-runtime.txt"

for arch in $ARCHITECTURES; do
    STAGE_RUNTIME="$BUILD_DIR/roostos-runtime"
    RUNTIME_TARGET="$STAGE_RUNTIME/usr/lib/roostos/runtime"
    rm -rf "$STAGE_RUNTIME"
    mkdir -p "$RUNTIME_TARGET"
    
    echo "Copying standalone Python runtime into roostos-runtime ($arch)..."
    cp -a "$PYTHON_PREFIX/"* "$RUNTIME_TARGET/"

    echo "Installing locked dependencies into roostos-runtime..."
    uv pip install --break-system-packages --python "$RUNTIME_TARGET/bin/python3" -r "$BUILD_DIR/requirements-runtime.txt"
    uv pip install --break-system-packages --python "$RUNTIME_TARGET/bin/python3" \
        "$SRC_DIR/roostos-sdk" \
        "$SRC_DIR/roostos-engine" \
        "$SRC_DIR/roostos-cli" \
        "$SRC_DIR/roostos-web" \
        "$SRC_DIR/roostos-timeguardd"

    sed -i "s|#!.*python.*|#!/usr/lib/roostos/runtime/bin/python3|" "$RUNTIME_TARGET/bin/"* 2>/dev/null || true
    build_pkg "roostos-runtime" "$arch" "Standalone Python 3.13 runtime and locked virtual environment for RoostOS" "libc6 (>= 2.31)"
done

# 2. roostos-cli (Root Base CLI and Setup Wizard)
STAGE_CLI="$BUILD_DIR/roostos-cli"
mkdir -p "$STAGE_CLI/usr/bin"
cat << 'EOF' > "$STAGE_CLI/usr/bin/roostos"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_cli.main "$@"
EOF
chmod 755 "$STAGE_CLI/usr/bin/roostos"
build_pkg "roostos-cli" "all" "RoostOS root CLI and universal hardware-aware setup wizard" "roostos-runtime" "Provides: roostos\nReplaces: roostos"

# 3. roostos-sdk
STAGE_SDK="$BUILD_DIR/roostos-sdk"
mkdir -p "$STAGE_SDK/DEBIAN"
build_pkg "roostos-sdk" "all" "Python SDK for RoostOS services and plugins" "roostos-runtime"

# 4. roostos-node (Base Node Agent & Local REST API)
STAGE_NODE="$BUILD_DIR/roostos-node"
mkdir -p "$STAGE_NODE/usr/bin"
mkdir -p "$STAGE_NODE/usr/share/roostos/web"
mkdir -p "$STAGE_NODE/etc/systemd/system"
cp -r "$SRC_DIR/roostos-ui/"* "$STAGE_NODE/usr/share/roostos/web/" 2>/dev/null || true
rm -rf "$STAGE_NODE/usr/share/roostos/web/node_modules"
cat << 'EOF' > "$STAGE_NODE/usr/bin/roostos-node"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_web.main "$@"
EOF
chmod 755 "$STAGE_NODE/usr/bin/roostos-node"
cat << 'EOF' > "$STAGE_NODE/etc/systemd/system/roostos-node.service"
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
EOF
build_pkg "roostos-node" "all" "RoostOS local node agent and REST API service" "roostos-runtime, roostos-cli" "Provides: roostos-web\nReplaces: roostos-web"

# Compatibility transitional package: roostos-web -> roostos-node
STAGE_WEB="$BUILD_DIR/roostos-web"
mkdir -p "$STAGE_WEB/DEBIAN"
build_pkg "roostos-web" "all" "Transitional package for roostos-node" "roostos-node"

# 5. roostos-gateway (Edge Router Stack - formerly roostos-core)
STAGE_GW="$BUILD_DIR/roostos-gateway"
mkdir -p "$STAGE_GW/usr/local/bin"
mkdir -p "$STAGE_GW/etc/dbus-1/system.d"
mkdir -p "$STAGE_GW/DEBIAN"
cp "$SRC_DIR/debian/org.roostos.conf" "$STAGE_GW/etc/dbus-1/system.d/" 2>/dev/null || true
cp "$SRC_DIR/roostos-engine/src/roostos_engine/templates/roost-dhcp-hook.sh" "$STAGE_GW/usr/local/bin/roost-dhcp-hook" 2>/dev/null || true
chmod 755 "$STAGE_GW/usr/local/bin/roost-dhcp-hook" 2>/dev/null || true
if [ -f "$SRC_DIR/packaging/debian/postinst" ]; then
    cp "$SRC_DIR/packaging/debian/postinst" "$STAGE_GW/DEBIAN/postinst"
    cp "$SRC_DIR/packaging/debian/prerm" "$STAGE_GW/DEBIAN/prerm"
    cp "$SRC_DIR/packaging/debian/postrm" "$STAGE_GW/DEBIAN/postrm"
    chmod 755 "$STAGE_GW/DEBIAN/postinst" "$STAGE_GW/DEBIAN/prerm" "$STAGE_GW/DEBIAN/postrm"
fi
for arch in $ARCHITECTURES; do
    build_pkg "roostos-gateway" "$arch" "RoostOS edge gateway routing stack with nftables firewall, Kea DHCP, and networkd" "roostos-node, nftables, kea-dhcp4-server, wireguard, systemd" "Provides: roostos-core\nReplaces: roostos-core"
done

# Compatibility transitional package: roostos-core -> roostos-gateway
STAGE_CORE="$BUILD_DIR/roostos-core"
mkdir -p "$STAGE_CORE/DEBIAN"
for arch in $ARCHITECTURES; do
    build_pkg "roostos-core" "$arch" "Transitional package for roostos-gateway" "roostos-gateway"
done

# 6. roostos-engine (Central Controller Stack)
STAGE_ENGINE="$BUILD_DIR/roostos-engine"
mkdir -p "$STAGE_ENGINE/usr/bin"
mkdir -p "$STAGE_ENGINE/etc/roostos"
mkdir -p "$STAGE_ENGINE/etc/systemd/system"
cat << 'EOF' > "$STAGE_ENGINE/usr/bin/roostos-engine"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_engine.daemon "$@"
EOF
chmod 755 "$STAGE_ENGINE/usr/bin/roostos-engine"
ln -s roostos-engine "$STAGE_ENGINE/usr/bin/roostd"
cp "$SRC_DIR/packaging/common/systemd/roostos-engine.service" "$STAGE_ENGINE/etc/systemd/system/roostos-engine.service" 2>/dev/null || true
build_pkg "roostos-engine" "all" "Central domain object controller, cluster sync, and configuration storage service" "roostos-runtime, mosquitto"

# 7. roostos-workstation (Consolidated Client Workstation Stack)
STAGE_WS="$BUILD_DIR/roostos-workstation"
mkdir -p "$STAGE_WS/usr/local/bin"
mkdir -p "$STAGE_WS/etc/systemd/system"
cat << 'EOF' > "$STAGE_WS/usr/local/bin/roostos-timeguardd"
#!/usr/bin/env sh
exec /usr/lib/roostos/runtime/bin/python3 -m roostos_timeguardd.main "$@"
EOF
chmod 755 "$STAGE_WS/usr/local/bin/roostos-timeguardd"
cp "$SRC_DIR/scripts/roostos-workstation-join.sh" "$STAGE_WS/usr/local/bin/roostos-workstation-join" 2>/dev/null || true
chmod 755 "$STAGE_WS/usr/local/bin/roostos-workstation-join" 2>/dev/null || true
cp "$SRC_DIR/scripts/roostos-workstation-enroll.sh" "$STAGE_WS/usr/local/bin/roostos-workstation-enroll" 2>/dev/null || true
chmod 755 "$STAGE_WS/usr/local/bin/roostos-workstation-enroll" 2>/dev/null || true
cp "$SRC_DIR/packaging/common/systemd/roostos-timeguardd.service" "$STAGE_WS/etc/systemd/system/" 2>/dev/null || true
build_pkg "roostos-workstation" "all" "Screen time, parental controls, and domain enrollment for RoostOS client workstations" "roostos-runtime, systemd, dbus" "Provides: roostos-timeguardd\nReplaces: roostos-timeguardd"

# Compatibility transitional package: roostos-timeguardd -> roostos-workstation
STAGE_TG="$BUILD_DIR/roostos-timeguardd"
mkdir -p "$STAGE_TG/DEBIAN"
build_pkg "roostos-timeguardd" "all" "Transitional package for roostos-workstation" "roostos-workstation"

# 8. Meta-Packages
STAGE_ROUTER="$BUILD_DIR/roostos-router"
build_pkg "roostos-router" "all" "All-in-one standalone RoostOS router distribution" "roostos-gateway, roostos-engine"

STAGE_GW_NODE="$BUILD_DIR/roostos-gateway-node"
build_pkg "roostos-gateway-node" "all" "Dedicated RoostOS edge gateway router node meta-package" "roostos-cli, roostos-gateway"

STAGE_CTRL_NODE="$BUILD_DIR/roostos-controller-node"
build_pkg "roostos-controller-node" "all" "Dedicated RoostOS central controller node meta-package" "roostos-cli, roostos-engine"

STAGE_EDGE_NODE="$BUILD_DIR/roostos-edge-node"
mkdir -p "$STAGE_EDGE_NODE/usr/local/bin"
cp "$SRC_DIR/scripts/roostos-edge-setup.sh" "$STAGE_EDGE_NODE/usr/local/bin/roostos-edge-setup" 2>/dev/null || true
chmod 755 "$STAGE_EDGE_NODE/usr/local/bin/roostos-edge-setup" 2>/dev/null || true
build_pkg "roostos-edge-node" "all" "Dedicated RoostOS VPS Edge Gateway & Ingress proxy node meta-package" "roostos-cli, roostos-node, wireguard, nftables"

# Compatibility root meta-package: roostos -> roostos-cli
STAGE_ROOT_META="$BUILD_DIR/roostos"
mkdir -p "$STAGE_ROOT_META/DEBIAN"
build_pkg "roostos" "all" "RoostOS root CLI metapackage" "roostos-cli"

echo "============================================="
echo "All RoostOS Modular Debian Packages Built Successfully!"
echo "Package Artifacts in: $DIST_DIR"
echo "============================================="
