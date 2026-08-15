#!/usr/bin/env bash
# RoostOS TimeGuard Daemon Debian Package Build Script
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$SRC_DIR/build-deb-tmp/timeguardd"
STAGE_DIR="$BUILD_DIR/stage"
PACKAGE_VERSION=0.1.0

echo "============================================="
echo "Building roostos-timeguardd Debian Package"
echo "Source: $SRC_DIR"
echo "============================================="

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$STAGE_DIR/DEBIAN"
mkdir -p "$STAGE_DIR/etc/systemd/system"
mkdir -p "$STAGE_DIR/usr/local/bin"
mkdir -p "$STAGE_DIR/opt/roostos-timeguardd/wheels"

# 1. Copy source files and daemon script
echo "Adding TimeGuard daemon files..."
cp "$SRC_DIR/roostos-timeguardd/src/roostos_timeguardd/main.py" "$STAGE_DIR/usr/local/bin/roostos-timeguardd"
cp "$SRC_DIR/roostos-timeguardd/src/roostos_timeguardd/setup.py" "$STAGE_DIR/usr/local/bin/roostos-timeguard-setup"
chmod 755 "$STAGE_DIR/usr/local/bin/roostos-timeguardd"
chmod 755 "$STAGE_DIR/usr/local/bin/roostos-timeguard-setup"

# 2. Add systemd service config
cat <<EOF > "$STAGE_DIR/etc/systemd/system/roostos-timeguardd.service"
[Unit]
Description=RoostOS TimeGuard Screen Time Daemon
After=network.target dbus.service

[Service]
Type=simple
ExecStart=/usr/local/bin/roostos-timeguardd start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 3. Create installer maintainer scripts (postinst, prerm, postrm)
cat <<EOF > "$STAGE_DIR/DEBIAN/postinst"
#!/bin/sh
set -e
if [ "\$1" = "configure" ]; then
    # Run auto-discovery and config setup
    /usr/local/bin/roostos-timeguard-setup || true
    systemctl daemon-reload || true
    systemctl enable roostos-timeguardd.service || true
    systemctl start roostos-timeguardd.service || true
fi
EOF
chmod 755 "$STAGE_DIR/DEBIAN/postinst"

cat <<EOF > "$STAGE_DIR/DEBIAN/prerm"
#!/bin/sh
set -e
if [ "\$1" = "remove" ]; then
    systemctl stop roostos-timeguardd.service || true
    systemctl disable roostos-timeguardd.service || true
fi
EOF
chmod 755 "$STAGE_DIR/DEBIAN/prerm"

# 4. Generate package control file
Architecture=$(dpkg --print-architecture 2>/dev/null || echo "all")
cat <<EOF > "$STAGE_DIR/DEBIAN/control"
Package: roostos-timeguardd
Version: $PACKAGE_VERSION
Section: admin
Priority: optional
Architecture: $Architecture
Depends: python3, python3-dbus, python3-paho-mqtt, libpam-ldapd, nslcd, avahi-utils
Maintainer: RoostOS Core Team <info@roostos.org>
Description: Screen time monitoring daemon for RoostOS clients
 roostos-timeguardd monitors user logins and lock state using systemd-logind,
 enforcing screen time limits via D-Bus lock commands and PAM integration.
EOF

# 5. Build the debian package
echo "Building the deb package..."
dpkg-deb --build "$STAGE_DIR" "$SRC_DIR/roostos-timeguardd_${PACKAGE_VERSION}_${Architecture}.deb"

echo "============================================="
echo "Successfully built roostos-timeguardd_${PACKAGE_VERSION}_${Architecture}.deb"
echo "============================================="
