#!/usr/bin/env bash
# RoostOS Modular Debian Package Build Script
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_VERSION="$(cat "$SRC_DIR/VERSION" | tr -d '[:space:]')"
BUILD_DIR="$SRC_DIR/build-deb-tmp"
DIST_DIR="$SRC_DIR/dist/debs"
COMMON_DIR="$SRC_DIR/packaging/common"
DEBIAN_DIR="$SRC_DIR/packaging/debian"

echo "============================================="
echo "Building RoostOS Modular Debian Packages"
echo "Version: $PACKAGE_VERSION"
echo "Output Directory: $DIST_DIR"
echo "============================================="

rm -rf "$BUILD_DIR"
mkdir -p "$DIST_DIR"

Architecture=$(dpkg --print-architecture 2>/dev/null || echo "amd64")

# Helper function to create a Debian package
build_pkg() {
    local pkg_name="$1"
    local pkg_arch="$2"
    local pkg_desc="$3"
    local pkg_deps="$4"
    local stage_path="$BUILD_DIR/$pkg_name"

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

    deb_filename="${pkg_name}_${PACKAGE_VERSION}_${pkg_arch}.deb"
    dpkg-deb --build "$stage_path" "$DIST_DIR/$deb_filename"
    echo "✓ Built: $DIST_DIR/$deb_filename"
}

# 1. roostos-sdk
STAGE_SDK="$BUILD_DIR/roostos-sdk"
mkdir -p "$STAGE_SDK/usr/lib/python3/dist-packages"
cp -r "$SRC_DIR/roostos-sdk/src/roostos_sdk" "$STAGE_SDK/usr/lib/python3/dist-packages/"
build_pkg "roostos-sdk" "all" "Python SDK for RoostOS services and plugins" "python3, python3-dbus-next"

# 2. roostos-engine
STAGE_ENGINE="$BUILD_DIR/roostos-engine"
mkdir -p "$STAGE_ENGINE/usr/lib/python3/dist-packages"
mkdir -p "$STAGE_ENGINE/usr/local/bin"
mkdir -p "$STAGE_ENGINE/etc/roostos"
mkdir -p "$STAGE_ENGINE/lib/systemd/system"
echo "$PACKAGE_VERSION" > "$STAGE_ENGINE/etc/roostos/version"
cp -r "$SRC_DIR/roostos-engine/src/roostos_engine" "$STAGE_ENGINE/usr/lib/python3/dist-packages/"
cp "$COMMON_DIR/systemd/roostos-engine.service" "$STAGE_ENGINE/lib/systemd/system/"
build_pkg "roostos-engine" "all" "Central domain object REST API and configuration storage service for RoostOS" "python3, roostos-sdk, python3-pydantic, python3-fastapi, python3-jwt, python3-pyyaml"

# 3. roostos-core
STAGE_CORE="$BUILD_DIR/roostos-core"
mkdir -p "$STAGE_CORE/usr/local/bin"
mkdir -p "$STAGE_CORE/etc/dbus-1/system.d"
mkdir -p "$STAGE_CORE/DEBIAN"
cp "$COMMON_DIR/dbus/org.roostos.conf" "$STAGE_CORE/etc/dbus-1/system.d/"
cp "$SRC_DIR/roostos-engine/src/roostos_engine/templates/roost-dhcp-hook.sh" "$STAGE_CORE/usr/local/bin/roost-dhcp-hook" 2>/dev/null || true
chmod 755 "$STAGE_CORE/usr/local/bin/roost-dhcp-hook" 2>/dev/null || true
cp "$DEBIAN_DIR/postinst" "$STAGE_CORE/DEBIAN/postinst"
cp "$DEBIAN_DIR/prerm" "$STAGE_CORE/DEBIAN/prerm"
cp "$DEBIAN_DIR/postrm" "$STAGE_CORE/DEBIAN/postrm"
chmod 755 "$STAGE_CORE/DEBIAN/postinst" "$STAGE_CORE/DEBIAN/prerm" "$STAGE_CORE/DEBIAN/postrm"
build_pkg "roostos-core" "$Architecture" "Local router management daemon applying firewall, DHCP, and network configs" "python3, roostos-sdk, roostos-engine, systemd, dbus, kea-dhcp4-server, nftables, iwd, python3-paho-mqtt"

# 4. roostos-web
STAGE_WEB="$BUILD_DIR/roostos-web"
mkdir -p "$STAGE_WEB/usr/lib/python3/dist-packages"
mkdir -p "$STAGE_WEB/usr/share/roostos/web"
mkdir -p "$STAGE_WEB/lib/systemd/system"
cp -r "$SRC_DIR/roostos-web/src/roostos_web" "$STAGE_WEB/usr/lib/python3/dist-packages/"
cp -r "$SRC_DIR/roostos-ui/"* "$STAGE_WEB/usr/share/roostos/web/" 2>/dev/null || true
cp "$COMMON_DIR/systemd/roostos-web.service" "$STAGE_WEB/lib/systemd/system/"
build_pkg "roostos-web" "all" "Web administration panel and single-page management application for RoostOS" "python3, roostos-engine, python3-fastapi, python3-pam, python3-jwt"

# 5. roostos-timeguardd
STAGE_TG="$BUILD_DIR/roostos-timeguardd"
mkdir -p "$STAGE_TG/usr/local/bin"
mkdir -p "$STAGE_TG/lib/systemd/system"
cp "$SRC_DIR/roostos-timeguardd/src/roostos_timeguardd/main.py" "$STAGE_TG/usr/local/bin/roostos-timeguardd" 2>/dev/null || true
chmod 755 "$STAGE_TG/usr/local/bin/roostos-timeguardd" 2>/dev/null || true
cp "$COMMON_DIR/systemd/roostos-timeguardd.service" "$STAGE_TG/lib/systemd/system/"
build_pkg "roostos-timeguardd" "all" "Screen time monitoring daemon for RoostOS client workstations" "python3, python3-paho-mqtt, systemd, dbus"

# 6. roostos-router (Meta-Package)
STAGE_META="$BUILD_DIR/roostos-router"
build_pkg "roostos-router" "all" "Standalone all-in-one RoostOS router distribution meta-package" "roostos-sdk, roostos-engine, roostos-core, roostos-web"

echo "============================================="
echo "All 6 Debian Packages Built Successfully!"
echo "Package Artifacts in: $DIST_DIR"
echo "============================================="
