# PlotPilot

Open-source **macOS** application for controlling pen plotters, starting with
[AxiDraw](https://axidraw.com/). PlotPilot focuses on SVG workflows: layers,
preview, and plotting one layer at a time with pen changes between layers.

Repository: [github.com/bolet777/plotpilot](https://github.com/bolet777/plotpilot)

## Current status

**Foundation only.** The repo has:

- Python 3.12 + PySide6 project layout
- SpecKit (spec-driven slices, Cursor integration, git extension)
- Lint/format (Ruff) and tests (pytest)
- A minimal placeholder window to confirm the app boots

**Not implemented yet:** release CI, code signing, or notarization for the macOS
`.app`.

Local macOS bundle: `./lance.sh` (see [010 quickstart](specs/010-macos-app-bundle/quickstart.md)).

## macOS focus

PlotPilot is developed and tested on macOS first. Core logic is kept portable
where practical; platform-specific packaging and polish target macOS.

## License

**MIT** — permissive, widely understood, and compatible with linking to
third-party libraries and tools (including future AxiDraw-related dependencies).
See [LICENSE](LICENSE).

## Development setup

Requirements:

- macOS (primary)
- [Python 3.12](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) (recommended)

```bash
git clone https://github.com/bolet777/plotpilot.git
cd plotpilot
uv sync --group dev
```

## Run the app

**Packaged app (correct Dock name and icon on macOS):**

```bash
./lance.sh
```

Builds `dist/PlotPilot.app` with PyInstaller and opens it. Use `./lance.sh --no-build` to relaunch without rebuilding. Details: [specs/010-macos-app-bundle/quickstart.md](specs/010-macos-app-bundle/quickstart.md).

**From source (fast dev loop; Dock may show Python):**

```bash
uv run plotpilot
```

## Quality commands

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

## Project structure

```text
src/plotpilot/   Application code (app, ui, svg, plotter, services, models)
tests/           pytest suite
specs/           SpecKit feature specifications
docs/            Architecture and docs index
.specify/        SpecKit templates and scripts
.cursor/skills/  SpecKit agent skills for Cursor
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[.specify/memory/constitution.md](.specify/memory/constitution.md).

## SpecKit

Initialize is already done for this repo (`cursor-agent` integration). For new
features, use the skills in Cursor (e.g. `/speckit-specify`) and the git
extension branch workflow. See [specs/README.md](specs/README.md).
