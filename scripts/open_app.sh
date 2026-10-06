#!/usr/bin/env bash
# Open dist/PlotPilot.app. Build it first only when it is missing.
# Root helper: ./open.sh
#
#   ./open.sh
#   ./open.sh --rebuild
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos

if [[ "${1:-}" == "--rebuild" || ! -d "$APP" ]]; then
  "$ROOT/scripts/build_app.sh"
elif [[ -n "${1:-}" ]]; then
  echo "Unknown option: $1" >&2
  echo "Usage: ./open.sh [--rebuild]" >&2
  exit 1
fi

echo "Opening $APP"
open "$APP"
