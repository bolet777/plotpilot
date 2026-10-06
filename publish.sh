#!/usr/bin/env bash
# Build, notarize, and publish a GitHub Release.
exec "$(cd "$(dirname "$0")" && pwd)/scripts/publish.sh" "$@"
