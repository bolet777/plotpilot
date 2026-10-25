#!/usr/bin/env bash
# Regenerate PNG sizes and plotpilot.icns from assets/icons/icon.png (macOS: sips + iconutil).
# PNGs stay transparent for the in-app logo. The ICNS is opaque for the Dock.
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

# macOS 26 plates any Dock/Finder icon that still has transparent corners.
# Fill those pixels with the icon face color and drop the alpha channel.
# The UI PNGs above stay transparent; only the bundle ICNS is flattened.
# The artwork is not scaled. Pixels outside the system squircle are the only
# ones that were transparent, so this does not crop the visible icon.
cd "$ROOT"
uv run python - "$ICONSET" << 'PY'
import struct
import sys
import zlib
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter


def background_color(image: QImage) -> QColor:
    """Median dark, low-saturation face color. Skips the neon P and metal rails."""
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = image.width(), image.height()
    step = max(1, width // 256)
    reds: list[int] = []
    greens: list[int] = []
    blues: list[int] = []
    for y in range(0, height, step):
        for x in range(0, width, step):
            color = image.pixelColor(x, y)
            if color.alpha() < 250:
                continue
            red, green, blue = color.red(), color.green(), color.blue()
            if max(red, green, blue) - min(red, green, blue) > 28:
                continue
            luma = (red + green + blue) // 3
            if 20 <= luma <= 90:
                reds.append(red)
                greens.append(green)
                blues.append(blue)
    if not reds:
        return QColor(42, 50, 58)
    reds.sort()
    greens.sort()
    blues.sort()
    mid = len(reds) // 2
    return QColor(reds[mid], greens[mid], blues[mid])


def write_rgb_png(path: Path, image: QImage) -> None:
    """Write a color-type-2 PNG so iconutil cannot keep an alpha channel."""
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    width, height = image.width(), image.height()
    row_bytes = image.bytesPerLine()
    pixels = memoryview(image.constBits()).cast("B")
    raw = bytearray()
    for y in range(height):
        start = y * row_bytes
        raw.append(0)
        raw.extend(pixels[start : start + width * 3])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def flatten(path: Path, fill: QColor) -> None:
    image = QImage(str(path)).convertToFormat(QImage.Format.Format_ARGB32)
    if image.isNull():
        raise SystemExit(f"Cannot read {path}")
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOver)
    painter.fillRect(image.rect(), fill)
    painter.end()
    write_rgb_png(path, image)


iconset = Path(sys.argv[1])
paths = sorted(iconset.glob("*.png"))
master = iconset / "icon_512x512@2x.png"
if master not in paths:
    raise SystemExit(f"Missing {master}")
fill = background_color(QImage(str(master)))
for path in paths:
    flatten(path, fill)
print(f"ICNS fill color rgb({fill.red()}, {fill.green()}, {fill.blue()})")
PY

iconutil -c icns "$ICONSET" -o "$ASSETS/plotpilot.icns"
cp "$ASSETS/plotpilot.icns" "$PKG/plotpilot.icns"
rm -rf "$ICONSET"

alpha="$(sips -g hasAlpha "$ASSETS/plotpilot.icns" | awk '/hasAlpha/ { print $2 }')"
if [[ "$alpha" != "no" ]]; then
  echo "plotpilot.icns still has an alpha channel (hasAlpha=$alpha)" >&2
  exit 1
fi

echo "Icons updated in $ASSETS and $PKG"
