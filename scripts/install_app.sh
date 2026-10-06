#!/usr/bin/env bash
# Copy dist/PlotPilot.app into /Applications.
# Root helper: ./install.sh
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos

DEST="/Applications/PlotPilot.app"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run ./build.sh first." >&2
  exit 1
fi

rm -rf "$DEST"
ditto "$APP" "$DEST"
echo "Installed $DEST"
