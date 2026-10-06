#!/usr/bin/env bash
# Download the official AxiDraw CLI into dist/PlotPilot.app.
# Called by scripts/publish.sh. axicli is not a PlotPilot dependency and is not committed.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos

AXICLI_URL="${AXICLI_URL:-https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip}"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run ./build.sh first." >&2
  exit 1
fi

base_python_prefix() {
  local found real prefix
  found="$(uv python find 3.12)"
  real="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$found")"
  prefix="$(cd "$(dirname "$real")/.." && pwd)"
  if [[ ! -x "$prefix/bin/python3.12" ]]; then
    echo "Expected a standalone Python 3.12 under $prefix (from: $found)." >&2
    exit 1
  fi
  if [[ -f "$prefix/pyvenv.cfg" ]]; then
    echo "Refusing to bundle a virtualenv at $prefix." >&2
    exit 1
  fi
  printf '%s\n' "$prefix"
}

prefix="$(base_python_prefix)"
resources="$APP/Contents/Resources"
python_dest="$resources/python"
site="$resources/axicli-site"
wrapper="$APP/Contents/MacOS/axicli"

echo "Bundling axicli from $AXICLI_URL"
echo "Python: $prefix"
rm -rf "$python_dest" "$site"
ditto "$prefix" "$python_dest"
"$python_dest/bin/python3.12" -m pip install --disable-pip-version-check --target "$site" "$AXICLI_URL"

cat > "$wrapper" <<'EOF'
#!/bin/bash
# Private axicli for this PlotPilot.app. Python and the AxiDraw packages live
# under Contents/Resources and move with the app.
set -euo pipefail
MACOS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$MACOS/.." && pwd)"
export PYTHONNOUSERSITE=1
export PYTHONPATH="${ROOT}/Resources/axicli-site${PYTHONPATH:+:${PYTHONPATH}}"
exec "${ROOT}/Resources/python/bin/python3.12" -m axicli "$@"
EOF
chmod 755 "$wrapper"
xattr -cr "$python_dest" "$site" "$wrapper"
"$wrapper" --version
