#!/usr/bin/env bash
# Zip dist/PlotPilot.app for distribution. Does not upload it.
# Called by scripts/publish.sh.
# Writes dist/PlotPilot-<version>-macos-<arch>.zip and a notes file beside it.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run ./build.sh first." >&2
  exit 1
fi

NAME="$(release_name)"
VERSION="$(app_version)"
ARCH="$(uname -m)"
STAGE="$ROOT/dist/release-staging/$NAME"
ZIP="$ROOT/dist/${NAME}.zip"
NOTES="$ROOT/dist/${NAME}-notes.txt"
NOTARIZED=0
if [[ -f "$ROOT/dist/.notarized" ]]; then
  NOTARIZED=1
fi

rm -rf "$ROOT/dist/release-staging"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/PlotPilot.app"

if [[ "$NOTARIZED" -eq 1 ]]; then
  cat > "$STAGE/README.txt" <<EOF
PlotPilot ${VERSION} for macOS (${ARCH})

Unzip this folder and open PlotPilot.app.
Connect the AxiDraw by USB before plotting.
EOF
else
  cat > "$STAGE/Open PlotPilot.command" <<'EOF'
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine "PlotPilot.app" 2>/dev/null || true
open "PlotPilot.app"
EOF
  chmod 755 "$STAGE/Open PlotPilot.command"
  cat > "$STAGE/README.txt" <<EOF
PlotPilot ${VERSION} for macOS (${ARCH})

This build is not notarized. macOS will call a downloaded copy damaged.
Double-click "Open PlotPilot.command", or from this folder in Terminal:

  xattr -dr com.apple.quarantine PlotPilot.app
  open PlotPilot.app

Connect the AxiDraw by USB before plotting.
EOF
fi

if [[ -x "$APP/Contents/MacOS/axicli" ]]; then
  cat >> "$STAGE/README.txt" <<'EOF'

axicli is included inside PlotPilot.app. It is the official AxiDraw software from
https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip
PlotPilot runs it as a separate program. The AxiDraw command-line interface is
MIT. Some libraries shipped with it, including the plotter driver, are GPL.
Their license files are in PlotPilot.app/Contents/Resources/axicli-site.
EOF
fi
cat >> "$STAGE/README.txt" <<'EOF'

PlotPilot itself is MIT. Source: https://github.com/bolet777/plotpilot
EOF

cp "$STAGE/README.txt" "$NOTES"
rm -f "$ZIP"
ditto -c -k --keepParent "$STAGE" "$ZIP"
rm -rf "$ROOT/dist/release-staging"
echo "Zip: $ZIP"
