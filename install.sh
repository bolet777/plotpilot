#!/usr/bin/env bash
# Copy dist/PlotPilot.app into /Applications.
exec "$(cd "$(dirname "$0")" && pwd)/scripts/install_app.sh" "$@"
