# PlotPilot documentation

## Core

- [Architecture](ARCHITECTURE.md) — modules, data flows, SpecKit slice map
- [Project README](../README.md) — setup, run, feature summary
- [Constitution](../.specify/memory/constitution.md) — principles and quality gates

## Features (SpecKit)

Each capability is specified under `specs/NNN-slug/` (`spec.md`, `plan.md`, `tasks.md`, …).

- [Feature index](../specs/README.md) — slices 001–010

### macOS app bundle

- [010 quickstart](../specs/010-macos-app-bundle/quickstart.md) — `./lance.sh`, PyInstaller, icons

## Development

- [Tests](../tests/README.md) — pytest layout and conventions
- Icons: `assets/icons/icon.png` → `./scripts/regenerate_icons.sh`
- Build `.app` only: `./scripts/build_macos_app.sh`
