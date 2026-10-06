#!/usr/bin/env bash
# Build a signed, notarized disk image from the stapled PlotPilot.app.
# The image contains the app and a shortcut to /Applications.
# Called by scripts/publish.sh. This is the file users download.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos

NOTARY_PROFILE="${PLOTPILOT_NOTARY_PROFILE:-plotpilot-notary}"
NAME="$(release_name)"
VERSION="$(app_version)"
DMG="$ROOT/dist/${NAME}.dmg"
NOTES="$ROOT/dist/${NAME}-notes.txt"
WORK="$ROOT/dist/dmg-staging"
RW="$WORK/rw.dmg"
MOUNT="$WORK/mount"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run ./build.sh first." >&2
  exit 1
fi
if [[ ! -f "$ROOT/dist/.notarized" ]]; then
  echo "The app is not notarized yet. ./publish.sh does that before the disk image." >&2
  exit 1
fi

IDENTITY="$(
  security find-identity -v -p codesigning \
    | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' \
    | head -1
)"
if [[ -z "$IDENTITY" ]]; then
  echo "No Developer ID Application certificate in Keychain." >&2
  exit 1
fi

case "$(uname -m)" in
  arm64) MAC_KIND="Apple Silicon" ;;
  *) MAC_KIND="Intel" ;;
esac

detach_mount() {
  local target="$1"
  local attempt
  sync
  for attempt in 1 2 3 4 5 6 7 8; do
    if hdiutil detach "$target" >/dev/null 2>&1; then
      return 0
    fi
    if hdiutil detach "$target" -force >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Could not unmount $target. Close any Finder window named PlotPilot, then run ./publish.sh again." >&2
  hdiutil detach "$target" -force
}

cleanup() {
  if [[ -d "$MOUNT" ]] && mount | grep -F -q " on $MOUNT "; then
    detach_mount "$MOUNT" || true
  fi
}
trap cleanup EXIT

if [[ -d "$MOUNT" ]] && mount | grep -F -q " on $MOUNT "; then
  detach_mount "$MOUNT"
fi
rm -rf "$WORK"
mkdir -p "$MOUNT"
size_mb="$(du -sm "$APP" | awk '{ print $1 }')"
hdiutil create -size "$((size_mb + 100))m" -fs HFS+ -volname "PlotPilot" "$RW" >/dev/null
hdiutil attach "$RW" -mountpoint "$MOUNT" -nobrowse -noautoopen >/dev/null
ditto "$APP" "$MOUNT/PlotPilot.app"
ln -s /Applications "$MOUNT/Applications"
detach_mount "$MOUNT"
rmdir "$MOUNT" 2>/dev/null || true

rm -f "$DMG"
hdiutil convert "$RW" -format UDZO -imagekey zlib-level=9 -o "$DMG" >/dev/null

echo "Signing the disk image with $IDENTITY"
codesign --force --timestamp --sign "$IDENTITY" "$DMG"
echo "Submitting the disk image to Apple notarization..."
xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"

cat > "$NOTES" <<EOF
PlotPilot ${VERSION}

macOS ${MAC_KIND}

1. Download the disk image.
2. Open it.
3. Drag PlotPilot to Applications.
4. Open PlotPilot from Applications.

Signed and notarized. axicli is included inside the app.
Connect the AxiDraw by USB before plotting.

PlotPilot itself is MIT. Source: https://github.com/bolet777/plotpilot
EOF

rm -rf "$WORK"
trap - EXIT
echo "Disk image: $DMG"
