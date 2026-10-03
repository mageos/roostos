#!/usr/bin/env bash
# RoostOS Debian Package Build Script
# Delegates to canonical multi-package build script
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$SRC_DIR/scripts/build-all-debs.sh" "$@"

