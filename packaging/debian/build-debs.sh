#!/usr/bin/env bash
# RoostOS Modular Debian Package Build Script
# Delegates to canonical scripts/build-all-debs.sh
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$SRC_DIR/scripts/build-all-debs.sh" "$@"
