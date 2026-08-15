#!/usr/bin/env bash
# RoostOS Debian Package Build Script
set -e

# Base directories
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$SRC_DIR/build-deb-tmp"
STAGE_DIR="$BUILD_DIR/stage"
DEBIAN_DIR="$SRC_DIR/debian"
PACKAGE_VERSION=0.1.59

echo "============================================="
echo "Building RoostOS Debian Package"
echo "Source: $SRC_DIR"
echo "============================================="

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$STAGE_DIR/DEBIAN"
mkdir -p "$STAGE_DIR/etc/systemd/system"
mkdir -p "$STAGE_DIR/etc/systemd/network"
mkdir -p "$STAGE_DIR/opt/roostos/wheels"

# 1. Copy maintainer scripts
echo "Adding package maintainer scripts..."
cp "$DEBIAN_DIR/postinst" "$STAGE_DIR/DEBIAN/postinst"
cp "$DEBIAN_DIR/prerm" "$STAGE_DIR/DEBIAN/prerm"
cp "$DEBIAN_DIR/postrm" "$STAGE_DIR/DEBIAN/postrm"
chmod 755 "$STAGE_DIR/DEBIAN/postinst"
chmod 755 "$STAGE_DIR/DEBIAN/prerm"
chmod 755 "$STAGE_DIR/DEBIAN/postrm"

# 2. Copy systemd configs and overlays
echo "Adding system configurations..."
mkdir -p "$STAGE_DIR/etc/dbus-1/system.d"
mkdir -p "$STAGE_DIR/etc/roostos"
echo "$PACKAGE_VERSION" > "$STAGE_DIR/etc/roostos/version"
cp "$DEBIAN_DIR/org.roostos.conf" "$STAGE_DIR/etc/dbus-1/system.d/"
cp "$SRC_DIR/roostos-debos/overlays/etc/systemd/system/roostd.service" "$STAGE_DIR/etc/systemd/system/"
cp "$SRC_DIR/roostos-debos/overlays/etc/systemd/system/roostos-web.service" "$STAGE_DIR/etc/systemd/system/"
cp "$SRC_DIR/roostos-debos/overlays/etc/systemd/network/"* "$STAGE_DIR/etc/systemd/network/"

# Copy DHCP hook script
mkdir -p "$STAGE_DIR/usr/local/bin"
cp "$SRC_DIR/roostos-engine/src/roostos_engine/templates/roost-dhcp-hook.sh" "$STAGE_DIR/usr/local/bin/roost-dhcp-hook"
chmod 755 "$STAGE_DIR/usr/local/bin/roost-dhcp-hook"

# 3. Copy SPA Web UI components
echo "Adding Web UI components..."
mkdir -p "$STAGE_DIR/usr/share/roostos/web"
cp -r "$SRC_DIR/roostos-ui/"* "$STAGE_DIR/usr/share/roostos/web/"

# 4. Compile python wheels for all packages and their requirements offline
echo "Compiling and caching Python wheels..."
if [ -d "$SRC_DIR/.venv" ]; then
    PYTHON="$SRC_DIR/.venv/bin/python"
    if [ ! -f "$SRC_DIR/.venv/bin/pip" ]; then
        echo "Bootstrapping pip in virtual environment..."
        "$PYTHON" -m ensurepip --default-pip || true
    fi
    PIP=("$SRC_DIR/.venv/bin/pip")
    if [ ! -f "$SRC_DIR/.venv/bin/pip" ]; then
        PIP=("$PYTHON" -m pip)
    fi
else
    PYTHON="python3"
    if python3 -m pip --version >/dev/null 2>&1; then
        PIP=(python3 -m pip)
    else
        PIP=(pip3)
    fi
fi

# Ensure pip is up to date and wheel package is available
"${PIP[@]}" install --upgrade pip wheel

# Build wheels for local components and download dependencies
"${PIP[@]}" wheel --wheel-dir="$STAGE_DIR/opt/roostos/wheels" \
    "$SRC_DIR/roostos-sdk" \
    "$SRC_DIR/roostos-engine" \
    "$SRC_DIR/roostos-dns-technitium" \
    "$SRC_DIR/roostos-web"

# 5. Generate package control file
echo "Generating DEBIAN/control file..."
Architecture=$(dpkg --print-architecture 2>/dev/null || echo "amd64")
cat <<EOF > "$STAGE_DIR/DEBIAN/control"
Package: roostos
Version: $PACKAGE_VERSION
Section: admin
Priority: optional
Architecture: $Architecture
Depends: systemd, dbus, python3, python3-venv, kea-dhcp4-server, nftables, docker.io, git, ppp, pppoe, mdns-reflector
Maintainer: RoostOS Core Team <info@roostos.org>
Description: Core services and Web UI for the RoostOS family router
 RoostOS provides a secure, intuitive family-oriented router and firewall,
 with device management, scheduled parental controls, VPNs, and isolated subnets.
EOF

# 6. Build the debian package
echo "Compiling package using dpkg-deb..."
PACKAGE_NAME="roostos_${PACKAGE_VERSION}_${Architecture}.deb"
dpkg-deb --build "$STAGE_DIR" "$SRC_DIR/$PACKAGE_NAME"

echo "============================================="
echo "Build Successful!"
echo "Package generated at: $SRC_DIR/$PACKAGE_NAME"
echo "============================================="
