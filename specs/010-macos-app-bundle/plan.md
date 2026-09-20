# Implementation Plan: macOS PlotPilot.app Bundle

**Branch**: `010-macos-app-bundle` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)

## Summary

Add a PyInstaller spec and `scripts/build_macos_app.sh` to produce `dist/PlotPilot.app` with correct `Info.plist` branding and ICNS. Document usage in `quickstart.md`. Keep `uv run plotpilot` for dev; recommend the built `.app` for Dock-correct launches.

## Technical Context

- **Language**: Python 3.12, PySide6
- **Packaging**: PyInstaller 6.x (`BUNDLE` + windowed `EXE`)
- **Assets**: `assets/icons/plotpilot.icns`, `src/plotpilot/resources/icons/`
- **Testing**: pytest smoke for packaging files; full build manual on macOS
- **Platform**: macOS only for build script

## Constitution Check

- Platform-specific packaging lives under `packaging/macos/` and scripts — not in SVG/plotter core. **Pass**
- No UI/hardware boundary changes. **Pass**
- Minimal new dependency (`pyinstaller` in dev group, darwin marker). **Pass**

## Project Structure

```text
packaging/macos/
├── entry.py           # PyInstaller entry
└── plotpilot.spec     # PyInstaller spec

scripts/
└── build_macos_app.sh # uv sync + pyinstaller

dist/PlotPilot.app     # build output (gitignored)
```

## Phase 0

See [research.md](./research.md) — PyInstaller selected.

## Phase 1

- [quickstart.md](./quickstart.md) — build and launch
- No new runtime data models or API contracts
