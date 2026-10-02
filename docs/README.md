# PlotPilot documentation

## Core

- [Architecture](ARCHITECTURE.md) — modules, data flows, SpecKit slice map
- [UI V2](UI-V2.md) — V2 layout, theme hooks, V1→V2 feature checklist
- [Project README](../README.md) — setup, run, feature summary
- [Constitution](../.specify/memory/constitution.md) — principles and quality gates
- [Audit 2026-09-30](AUDIT-2026-09-30.md) — technical/product audit, SVG pipeline risks, prioritized roadmap (FR)

## Features (SpecKit)

Each capability is specified under `specs/NNN-slug/` (`spec.md`, `plan.md`, `tasks.md`, …).

- [Feature index](../specs/README.md) — slices 001–023

### macOS app bundle

- [010 quickstart](../specs/010-macos-app-bundle/quickstart.md) — `./lance.sh`, PyInstaller, icons

## Development

- [Tests](../tests/README.md) — pytest layout and conventions
- Icons: `assets/icons/icon.png` → `./scripts/regenerate_icons.sh`
- Build `.app` only: `./scripts/build_macos_app.sh`
