#!/usr/bin/env bash
# Upload dist/PlotPilot-<version>-macos-<arch>.dmg to a GitHub Release.
# The disk image is not committed. Called by scripts/publish.sh after the commit is pushed.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

VERSION="$(app_version)"
TAG="v${VERSION}"
NAME="$(release_name)"
DMG="$ROOT/dist/${NAME}.dmg"
NOTES="$ROOT/dist/${NAME}-notes.txt"

if [[ ! -f "$DMG" ]]; then
  echo "Missing $DMG — run ./publish.sh." >&2
  exit 1
fi
if [[ ! -f "$NOTES" ]]; then
  echo "Missing $NOTES — run ./publish.sh." >&2
  exit 1
fi

if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release ${TAG} exists. Replacing the disk image."
  gh release upload "$TAG" "$DMG" --clobber
else
  gh release create "$TAG" "$DMG" \
    --title "PlotPilot ${VERSION}" \
    --notes-file "$NOTES" \
    --latest
fi
gh release view "$TAG"
echo "Release: https://github.com/bolet777/plotpilot/releases/tag/${TAG}"
