#!/usr/bin/env bash
# Build PlotPilot.app (PyInstaller) and launch it — macOS dev shortcut from repo root.
#
# Usage:
#   ./lance.sh          # build + open dist/PlotPilot.app
#   ./lance.sh --no-build   # open existing bundle only
#
# For quick iteration without packaging (Dock may show "Python 3.12"):
#   uv run plotpilot
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/dist/PlotPilot.app"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "PlotPilot.app is macOS-only." >&2
  exit 1
fi

if [[ "${1:-}" == "--no-build" ]]; then
  if [[ ! -d "$APP" ]]; then
    echo "Missing $APP — run ./lance.sh without --no-build first." >&2
    exit 1
  fi
else
  "$ROOT/scripts/build_macos_app.sh"
fi

echo "Launching $APP"
open "$APP"
