#!/usr/bin/env bash
# Upload dist/PlotPilot-<version>-macos-<arch>.zip to a GitHub Release.
# The zip is not committed. Called by scripts/publish.sh after the commit is pushed.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

VERSION="$(app_version)"
TAG="v${VERSION}"
NAME="$(release_name)"
ZIP="$ROOT/dist/${NAME}.zip"
NOTES="$ROOT/dist/${NAME}-notes.txt"

if [[ ! -f "$ZIP" ]]; then
  echo "Missing $ZIP — run ./publish.sh." >&2
  exit 1
fi
if [[ ! -f "$NOTES" ]]; then
  echo "Missing $NOTES — run ./publish.sh." >&2
  exit 1
fi

if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release ${TAG} exists. Replacing the zip."
  gh release upload "$TAG" "$ZIP" --clobber
else
  gh release create "$TAG" "$ZIP" \
    --title "PlotPilot ${VERSION}" \
    --notes-file "$NOTES" \
    --latest
fi
gh release view "$TAG"
echo "Release: https://github.com/bolet777/plotpilot/releases/tag/${TAG}"
