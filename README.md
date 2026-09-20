# PlotPilot

Open-source **macOS** application for controlling pen plotters, starting with
[AxiDraw](https://axidraw.com/). PlotPilot focuses on SVG workflows: open a file,
inspect layers, preview one layer at a time, and plot with pen changes between
layers.

Repository: [github.com/bolet777/plotpilot](https://github.com/bolet777/plotpilot)

## Current status

PlotPilot is a **working desktop app** for SVG layer workflows and AxiDraw control
via the external `axicli` CLI (must be installed and on `PATH`).

| Area | Status |
|------|--------|
| Open SVG (File menu, **⌘O**) | Done |
| Layer list (Inkscape layers, root groups fallback) | Done |
| Layer preview | Done |
| AxiDraw detect, pen up/down, auto monitoring | Done |
| Plot selected layer | Done |
| Plot settings (speed, acceleration, …) persisted | Done |
| Multi-layer plot with pen-change pauses | Done |
| Safe stop (cancel plot → raise pen → home → disable XY) | Done |
| App icon, window icon, macOS Dock branding via `.app` | Done |
| Release CI, code signing, notarization | Not yet |

SpecKit slices **001–010** are implemented in code; see [specs/README.md](specs/README.md).

## Features (user-facing)

- **Open SVG** — valid SVG files; clear errors for missing, non-SVG, or malformed files.
- **Layers** — list with color swatches; select a layer to preview; checkboxes for multi-layer jobs.
- **Preview** — vector preview of the selected layer in the main window.
- **Plotter** — connection status, **Pen ↑** / **Pen ↓**, **Refresh**; automatic presence polling when idle.
- **Plot selected layer** — plots the current layer through `axicli` using current plot settings.
- **Plot checked layers** — queues checked layers; pauses between layers for pen changes (**Continue**).
- **Stop** — cancels plotting and runs the safe-stop sequence on the device.
- **Plot settings** — editable motion/pen parameters; stored with Qt `QSettings`.

Hardware is optional for development: logic and UI are covered by pytest with fake backends.

## Requirements

- **macOS** (primary platform)
- [Python 3.12](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/)
- **AxiDraw**: [AxiDraw software](https://axidraw.com/doc/) providing the `axicli` command (for real plotting)

## Development setup

```bash
git clone https://github.com/bolet777/plotpilot.git
cd plotpilot
uv sync --group dev
```

## Run the app

**Packaged app (recommended on macOS — correct Dock name and icon):**

```bash
./lance.sh
```

Builds `dist/PlotPilot.app` with PyInstaller and opens it. Use `./lance.sh --no-build` to relaunch without rebuilding. See [specs/010-macos-app-bundle/quickstart.md](specs/010-macos-app-bundle/quickstart.md).

**From source (fast iteration; Dock may show “Python”):**

```bash
uv run plotpilot
```

## Icons and macOS bundle

- Master icon: `assets/icons/icon.png`
- Regenerate sizes and `.icns`: `./scripts/regenerate_icons.sh`
- Build only the `.app`: `./scripts/build_macos_app.sh`

## Quality commands

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

## Project structure

```text
src/plotpilot/
  app/         Entry point, macOS branding helpers
  resources/   Bundled icons (PNG + ICNS)
  ui/          Main window, preview, plot settings widgets
  svg/         Parse SVG, layers, preview SVG generation
  plotter/     PlotterBackend, AxiDraw CLI adapter, fake backend for tests
  services/    SVG load, layers, preview, plotter, multi-layer, settings
  models/      Document, layers, jobs, plotter status, settings
packaging/macos/   PyInstaller entry + spec
scripts/           Icon regeneration, macOS app build
assets/icons/      Source artwork and generated icon set
tests/             pytest (logic + MainWindow integration with fakes)
specs/             SpecKit feature specs (001–010)
docs/              Architecture and doc index
.specify/          SpecKit templates and scripts
.cursor/skills/    SpecKit agent skills for Cursor
lance.sh           Build + launch PlotPilot.app from repo root
```

## Documentation

- [docs/README.md](docs/README.md) — doc index
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — modules and boundaries
- [.specify/memory/constitution.md](.specify/memory/constitution.md) — engineering principles
- [specs/README.md](specs/README.md) — feature slices
- [tests/README.md](tests/README.md) — testing conventions

## SpecKit

Use Cursor skills (e.g. `/speckit-specify`) and git feature branches `NNN-slug` aligned with `specs/NNN-slug/`.

## License

**MIT** — see [LICENSE](LICENSE).
