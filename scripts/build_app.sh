#!/usr/bin/env bash
# Build dist/PlotPilot.app with PyInstaller (macOS only).
# Root helper: ./build.sh
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos
cd "$ROOT"

ICNS="$ROOT/assets/icons/plotpilot.icns"
if [[ ! -f "$ICNS" ]]; then
  echo "Missing $ICNS — run ./scripts/regenerate_icons.sh first." >&2
  exit 1
fi

uv sync --group dev
uv run pyinstaller "$ROOT/packaging/macos/plotpilot.spec" --noconfirm --clean

echo "Built $APP"
