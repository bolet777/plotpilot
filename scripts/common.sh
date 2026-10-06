# Shared paths for the macOS app scripts. Source this file; do not execute it.
_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$_COMMON_DIR/.." && pwd)"
APP="$ROOT/dist/PlotPilot.app"

require_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "PlotPilot.app is macOS-only." >&2
    exit 1
  fi
}

app_version() {
  local version
  version="$(grep -E '^version = ' "$ROOT/pyproject.toml" | head -1 | cut -d'"' -f2)"
  if [[ -z "$version" ]]; then
    echo "Could not read version from pyproject.toml." >&2
    exit 1
  fi
  printf '%s\n' "$version"
}

release_name() {
  printf 'PlotPilot-%s-macos-%s\n' "$(app_version)" "$(uname -m)"
}
