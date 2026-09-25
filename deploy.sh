#!/usr/bin/env bash
# Copy the built PlotPilot.app into /Applications (macOS).
#
# Usage:
#   ./deploy.sh
#
# Build the bundle first:
#   ./lance.sh
#   ./scripts/build_macos_app.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/dist/PlotPilot.app"
DEST="/Applications/PlotPilot.app"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "PlotPilot.app is macOS-only." >&2
  exit 1
fi

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run ./lance.sh or ./scripts/build_macos_app.sh first." >&2
  exit 1
fi

if [[ -d "$DEST" ]]; then
  rm -rf "$DEST"
fi

ditto "$APP" "$DEST"
echo "Installed $DEST"
