#!/usr/bin/env bash
# Sign dist/PlotPilot.app with a Developer ID certificate and notarize it.
# Called by scripts/publish.sh. Writes dist/.notarized on success.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_macos

ENTITLEMENTS="$ROOT/packaging/macos/entitlements.plist"
NOTARY_PROFILE="${PLOTPILOT_NOTARY_PROFILE:-plotpilot-notary}"
MARKER="$ROOT/dist/.notarized"
rm -f "$MARKER"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP — run ./build.sh first." >&2
  exit 1
fi

IDENTITY="$(
  security find-identity -v -p codesigning \
    | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' \
    | head -1
)"

print_signing_setup() {
  cat >&2 <<EOF
Publishing a build other people can open needs two one-time steps.

1. Create a Developer ID Application certificate (an Apple Development
   certificate cannot notarize a public download):
   Xcode → Settings → Accounts → your team → Manage Certificates →
   + → Developer ID Application.

2. Store notarization credentials. Create an app-specific password at
   https://appleid.apple.com then run:

   xcrun notarytool store-credentials ${NOTARY_PROFILE} \\
     --apple-id YOUR_APPLE_ID_EMAIL \\
     --team-id YOUR_TEAM_ID

   YOUR_TEAM_ID is the 10-character id in parentheses on the certificate.

Then run ./publish.sh again.
EOF
}

if [[ -z "$IDENTITY" ]]; then
  print_signing_setup
  exit 1
fi
if ! xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" >/dev/null 2>&1; then
  print_signing_setup
  exit 1
fi

sign_macho() {
  local file="$1"
  if [[ "${2:-}" == "with-entitlements" ]]; then
    codesign --force --options runtime --timestamp --sign "$IDENTITY" \
      --entitlements "$ENTITLEMENTS" "$file"
  else
    codesign --force --options runtime --timestamp --sign "$IDENTITY" "$file"
  fi
}

echo "Signing with $IDENTITY"
list="$(mktemp)"
find "$APP" -type f -print0 \
  | while IFS= read -r -d '' file; do
      if file -b "$file" | grep -q 'Mach-O'; then
        printf '%s\n' "$file"
      fi
    done \
  | awk '{ print length($0), $0 }' \
  | sort -nr \
  | cut -d' ' -f2- > "$list"
while IFS= read -r file; do
  case "$file" in
    */Contents/MacOS/PlotPilot|*/Contents/Resources/python/bin/python3.12)
      sign_macho "$file" with-entitlements
      ;;
    *)
      sign_macho "$file"
      ;;
  esac
done < "$list"
rm -f "$list"
codesign --force --options runtime --timestamp --sign "$IDENTITY" \
  --entitlements "$ENTITLEMENTS" "$APP"
codesign --verify --deep --strict "$APP"

upload="$ROOT/dist/PlotPilot-notarize.zip"
rm -f "$upload"
ditto -c -k --keepParent "$APP" "$upload"
echo "Submitting to Apple notarization..."
xcrun notarytool submit "$upload" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
rm -f "$upload"
touch "$MARKER"
echo "Notarized $APP"
