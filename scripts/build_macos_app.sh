#!/usr/bin/env bash
# Build dist/PlotPilot.app with PyInstaller (macOS only).
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "PlotPilot.app can only be built on macOS." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ICNS="$ROOT/assets/icons/plotpilot.icns"
if [[ ! -f "$ICNS" ]]; then
  echo "Missing $ICNS — run ./scripts/regenerate_icons.sh first." >&2
  exit 1
fi

uv sync --group dev
uv run pyinstaller "$ROOT/packaging/macos/plotpilot.spec" --noconfirm --clean

echo "Built $ROOT/dist/PlotPilot.app"
