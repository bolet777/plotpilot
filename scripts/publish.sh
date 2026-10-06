#!/usr/bin/env bash
# Build, bundle axicli, notarize, zip, and publish a GitHub Release.
# Root helper: ./publish.sh
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos
cd "$ROOT"

VERSION="$(app_version)"
TAG="v${VERSION}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required. Install it, then run: gh auth login" >&2
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
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
  tag_commit="$(git rev-parse "${TAG}^{}")"
  head_commit="$(git rev-parse HEAD)"
  if [[ "$tag_commit" != "$head_commit" ]]; then
    echo "Tag ${TAG} already points at another commit." >&2
    echo "Bump version in pyproject.toml, commit, then run ./publish.sh again." >&2
    exit 1
  fi
fi

echo "Pushing the current commit to origin..."
git push origin HEAD

"$ROOT/scripts/build_app.sh"
"$ROOT/scripts/bundle_axicli.sh"
"$ROOT/scripts/notarize_app.sh"
"$ROOT/scripts/package_app.sh"
"$ROOT/scripts/publish_release.sh"
