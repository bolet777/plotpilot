#!/usr/bin/env bash
# Rebuild dist/PlotPilot.app.
exec "$(cd "$(dirname "$0")" && pwd)/scripts/build_app.sh" "$@"
