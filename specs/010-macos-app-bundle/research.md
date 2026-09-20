# Research: macOS PlotPilot.app Bundle

## Problem

`uv run plotpilot` executes the CPython interpreter. macOS attributes the Dock tooltip and application identity to that runtime bundle, so users see **Python 3.12** even after Qt/PyObjC branding tweaks.

## Options considered

| Approach | Dock name | Dev UX | Notes |
|----------|-----------|--------|-------|
| Shell `.app` wrapping `uv run` | Unreliable | Easy | `exec python` replaces process; bundle identity reverts to Python |
| PyObjC `NSBundle` mutation on Python bundle | Partial | No extra build | Insufficient for Dock tooltip in practice |
| **PyInstaller `BUNDLE`** | **Reliable** | One build command | Matches constitution; embeds bootloader inside `.app` |
| py2app | Reliable | Extra toolchain | Heavier; PyInstaller already planned |

## Decision

Use **PyInstaller** with a `COLLECT` + `BUNDLE` spec:

- Entry: thin `packaging/macos/entry.py` calling `plotpilot.app.main.run`
- Data: `plotpilot/resources/icons`
- Icon: `assets/icons/plotpilot.icns`
- Output: `dist/PlotPilot.app` (gitignored)
- Dev dependency: `pyinstaller` (macOS only)

## Out of scope (this slice)

- Apple code signing / notarization
- CI release artifacts
- Universal2 / arm64-x86_64 fat binaries beyond PyInstaller defaults
