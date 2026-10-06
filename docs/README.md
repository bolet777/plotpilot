# PlotPilot documentation

## Using the app

- [User guide](guide.md) — window tour, placement, margins, plotting, projects, shortcuts
- [README](../README.md) — what PlotPilot does, requirements, and how to launch it
- [Screenshot](PlotPilot.png) — the main window during a layer plot

## Contributors

- [Architecture](ARCHITECTURE.md) — modules, data flows, and how the UI is composed
- [UI V2](UI-V2.md) — layout, theme hooks, and where each control lives
- [Tests](testing.md) — fast, full, and hardware pytest loops
- [Test layout](../tests/README.md) — conventions and coverage map
- [Feature index](../specs/README.md) — SpecKit slices
- [Constitution](../.specify/memory/constitution.md) — engineering principles
- [Audit 2026-09-30](AUDIT-2026-09-30.md) — SVG pipeline risks and the roadmap that followed (French)

### macOS app bundle

- [010 quickstart](../specs/010-macos-app-bundle/quickstart.md) — `./lance.sh`, PyInstaller, icons
- Icons: `assets/icons/icon.png` → `./scripts/regenerate_icons.sh`
- Build `.app` only: `./scripts/build_macos_app.sh`
