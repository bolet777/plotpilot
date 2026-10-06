#!/usr/bin/env bash
# Open dist/PlotPilot.app. Builds it only when the app is missing.
#   ./open.sh
#   ./open.sh --rebuild
exec "$(cd "$(dirname "$0")" && pwd)/scripts/open_app.sh" "$@"
