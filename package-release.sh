#!/usr/bin/env bash
# Build PlotPilot.app, bundle the official axicli, and zip it for a GitHub Release.
#
# Usage (from the repository root):
#   ./package-release.sh                 # zip, then GitHub Release
#   ./package-release.sh --no-publish    # zip only (stays in dist/)
#   ./package-release.sh --no-build      # reuse dist/PlotPilot.app
#   ./package-release.sh --no-axicli     # zip the app only
#
# Output: dist/PlotPilot-<version>-macos-<arch>.zip
# Publish uploads that zip to a GitHub Release (tag v<version>). The zip is not
# committed. Commit and push the source yourself first; the script then pushes
# the current commit and attaches the zip to the Release.
#
# axicli is downloaded from Evil Mad Scientist at package time and stored inside
# the .app. It is not a PlotPilot dependency and it is not committed to git.
# PlotPilot (MIT) runs it as a separate program. Parts of AxiDraw software are GPL;
# their license files travel inside the app next to that program.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
APP="$ROOT/dist/PlotPilot.app"
AXICLI_URL="${AXICLI_URL:-https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip}"
BUILD=1
BUNDLE_AXICLI=1
PUBLISH=1

usage() {
  cat <<'EOF'
Build PlotPilot.app, bundle the official axicli, zip it, and publish a GitHub Release.

Usage (from the repository root):
  ./package-release.sh                 # zip, then GitHub Release
  ./package-release.sh --no-publish    # zip only (stays in dist/)
  ./package-release.sh --no-build      # reuse dist/PlotPilot.app
  ./package-release.sh --no-axicli     # zip the app only

The zip is not committed. It is attached to the Release for tag v<version>.
Commit the source first. The script pushes that commit, then uploads the zip.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) BUILD=0 ;;
    --no-axicli) BUNDLE_AXICLI=0 ;;
    --no-publish) PUBLISH=0 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "PlotPilot releases are built on macOS." >&2
  exit 1
fi

VERSION="$(grep -E '^version = ' "$ROOT/pyproject.toml" | head -1 | cut -d'"' -f2)"
ARCH="$(uname -m)"
if [[ -z "$VERSION" ]]; then
  echo "Could not read version from pyproject.toml." >&2
  exit 1
fi

TAG="v${VERSION}"

require_publish_ready() {
  if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is required to publish. Install it, or pass --no-publish." >&2
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "gh is not logged in. Run: gh auth login" >&2
    exit 1
  fi
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Commit or stash these changes before publishing. The Release tag must match the zip." >&2
    git status --short >&2
    exit 1
  fi
  local tag_commit head_commit
  if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    tag_commit="$(git rev-parse "${TAG}^{}")"
    head_commit="$(git rev-parse HEAD)"
    if [[ "$tag_commit" != "$head_commit" ]]; then
      echo "Tag ${TAG} already points at another commit." >&2
      echo "Bump version in pyproject.toml, commit, then run this script again." >&2
      exit 1
    fi
  fi
  echo "Pushing the current commit to origin..."
  git push origin HEAD
}

publish_release() {
  local notes="$1"
  if gh release view "$TAG" >/dev/null 2>&1; then
    echo "Release ${TAG} exists. Replacing the zip."
    gh release upload "$TAG" "$ZIP" --clobber
  else
    gh release create "$TAG" "$ZIP" \
      --title "PlotPilot ${VERSION}" \
      --notes-file "$notes" \
      --latest
  fi
  gh release view "$TAG"
}

if [[ "$PUBLISH" -eq 1 ]]; then
  require_publish_ready
fi

if [[ "$BUILD" -eq 1 ]]; then
  "$ROOT/scripts/build_macos_app.sh"
elif [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run without --no-build first." >&2
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

write_axicli_wrapper() {
  local wrapper="$APP/Contents/MacOS/axicli"
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
}

bundle_axicli() {
  local prefix resources python_dest site
  prefix="$(base_python_prefix)"
  resources="$APP/Contents/Resources"
  python_dest="$resources/python"
  site="$resources/axicli-site"
  echo "Bundling axicli from $AXICLI_URL"
  echo "Python: $prefix"
  rm -rf "$python_dest" "$site"
  ditto "$prefix" "$python_dest"
  "$python_dest/bin/python3.12" -m pip install --disable-pip-version-check --target "$site" "$AXICLI_URL"
  write_axicli_wrapper
  xattr -cr "$python_dest" "$site" "$APP/Contents/MacOS/axicli"
  "$APP/Contents/MacOS/axicli" --version
}

if [[ "$BUNDLE_AXICLI" -eq 1 ]]; then
  bundle_axicli
fi

# Adding axicli invalidates the signature PyInstaller wrote. Ad-hoc sign the
# bundle so macOS does not report it as damaged. This is not a Developer ID
# signature: a downloaded zip still needs right-click → Open the first time.
codesign --force --deep --sign - "$APP"

NAME="PlotPilot-${VERSION}-macos-${ARCH}"
STAGE="$ROOT/dist/release-staging/$NAME"
ZIP="$ROOT/dist/${NAME}.zip"
rm -rf "$ROOT/dist/release-staging"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/PlotPilot.app"
cat > "$STAGE/README.txt" <<EOF
PlotPilot ${VERSION} for macOS (${ARCH})

1. Unzip this folder.
2. Right-click PlotPilot.app and choose Open, then confirm.
   The first launch asks because the app is not signed with an Apple Developer ID.
   After that, open it normally.
3. Connect the AxiDraw by USB.
EOF
if [[ "$BUNDLE_AXICLI" -eq 1 ]]; then
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

rm -f "$ZIP"
ditto -c -k --keepParent "$STAGE" "$ZIP"

if [[ "$PUBLISH" -eq 1 ]]; then
  publish_release "$STAGE/README.txt"
fi
rm -rf "$ROOT/dist/release-staging"

echo
echo "Zip: $ZIP"
if [[ "$PUBLISH" -eq 1 ]]; then
  echo "Release: https://github.com/bolet777/plotpilot/releases/tag/${TAG}"
else
  echo "Not published. Run ./package-release.sh again without --no-publish to upload it."
fi
