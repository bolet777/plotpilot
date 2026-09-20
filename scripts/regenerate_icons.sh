#!/usr/bin/env bash
# Regenerate PNG sizes and plotpilot.icns from assets/icons/icon.png (macOS: sips + iconutil).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$ROOT/assets/icons"
PKG="$ROOT/src/plotpilot/resources/icons"
SRC="$ASSETS/icon.png"

if [[ ! -f "$SRC" ]]; then
  echo "Missing source icon: $SRC" >&2
  exit 1
fi

mkdir -p "$ASSETS" "$PKG"
ICONSET="$ASSETS/plotpilot.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

for size in 16 32 64 128 256 512 1024; do
  sips -z "$size" "$size" "$SRC" --out "$ASSETS/icon_${size}.png" >/dev/null
  cp "$ASSETS/icon_${size}.png" "$PKG/icon_${size}.png"
done

sips -z 16 16 "$SRC" --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32 "$SRC" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$SRC" --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64 "$SRC" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$SRC" --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256 "$SRC" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$SRC" --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512 "$SRC" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$SRC" --out "$ICONSET/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$SRC" --out "$ICONSET/icon_512x512@2x.png" >/dev/null

iconutil -c icns "$ICONSET" -o "$ASSETS/plotpilot.icns"
cp "$ASSETS/plotpilot.icns" "$PKG/plotpilot.icns"
rm -rf "$ICONSET"

echo "Icons updated in $ASSETS and $PKG"
