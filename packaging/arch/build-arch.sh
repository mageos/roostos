#!/usr/bin/env bash
# RoostOS Modular Arch Linux Package Build Script
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_VERSION="$(cat "$SRC_DIR/VERSION" | tr -d '[:space:]')"
BUILD_DIR="$SRC_DIR/build-arch-tmp"
DIST_DIR="$SRC_DIR/dist/arch"
ARCH_DIR="$SRC_DIR/packaging/arch"

echo "============================================="
echo "Building RoostOS Modular Arch Linux Packages"
echo "Version: $PACKAGE_VERSION"
echo "Output Directory: $DIST_DIR"
echo "============================================="

# Ensure PKGBUILD version is synchronized with VERSION file
sed -i "s/^pkgver=.*/pkgver=$PACKAGE_VERSION/" "$ARCH_DIR/PKGBUILD"

mkdir -p "$DIST_DIR"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

if command -v makepkg >/dev/null 2>&1; then
    echo "Using host makepkg..."
    cp "$ARCH_DIR/PKGBUILD" "$BUILD_DIR/"
    cp "$ARCH_DIR/roostos.install" "$BUILD_DIR/" 2>/dev/null || true
    cd "$BUILD_DIR"
    SRC_DIR="$SRC_DIR" makepkg -f --nodeps --cleanbuild
    cp "$BUILD_DIR"/*.pkg.tar* "$DIST_DIR/"
else
    echo "makepkg not found on host. Checking for Docker..."
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        echo "Building Arch packages inside Arch Linux container..."
        docker run --rm \
            -v "$SRC_DIR":/workspace:ro \
            -v "$DIST_DIR":/out \
            archlinux:base-devel \
            bash -c "
                set -e
                useradd -m builder
                chown -R builder:builder /home/builder
                mkdir -p /tmp/pkgbuild
                cp /workspace/packaging/arch/PKGBUILD /tmp/pkgbuild/
                cp /workspace/packaging/arch/roostos.install /tmp/pkgbuild/ 2>/dev/null || true
                chown -R builder:builder /tmp/pkgbuild
                su builder -c '
                    cd /tmp/pkgbuild
                    SRC_DIR=/workspace makepkg -f --nodeps
                    cp *.pkg.tar* /out/
                '
            "
    else
        echo "WARNING: Neither makepkg nor Docker is available to build native .pkg.tar.zst packages."
        echo "PKGBUILD has been updated to version $PACKAGE_VERSION at $ARCH_DIR/PKGBUILD."
        exit 1
    fi
fi

echo "============================================="
echo "Arch Linux Packages Built Successfully!"
echo "Package Artifacts in: $DIST_DIR"
echo "============================================="
