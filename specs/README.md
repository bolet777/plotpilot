# SpecKit feature specs

PlotPilot uses [GitHub Spec Kit](https://github.com/github/spec-kit) for
spec-driven development. Each numbered slice has a directory under `specs/` and
a matching git branch `NNN-short-name`.

## Layout

```text
specs/NNN-short-name/
  spec.md       User requirements and success criteria
  plan.md       Implementation plan
  tasks.md      Checklist (all items below are complete in main development line)
  research.md   Decisions and external tool notes (where present)
  quickstart.md Manual verification (where present)
```

## Delivered features

| # | Slug | Summary |
|---|------|---------|
| 001 | [svg-open](001-svg-open/) | Open SVG via File menu / **⌘O**; load errors |
| 002 | [svg-layers](002-svg-layers/) | Inkscape-style layer list in the main window |
| 003 | [layer-preview](003-layer-preview/) | Preview selected layer |
| 004 | [axidraw-connect](004-axidraw-connect/) | Detect AxiDraw, pen up/down, status strip |
| 005 | [plot-selected-layer](005-plot-selected-layer/) | Plot one layer via `axicli` |
| 006 | [plot-settings](006-plot-settings/) | Speed/accel and related settings + persistence |
| 007 | [multi-layer-workflow](007-multi-layer-workflow/) | Plot checked layers; pen-change pauses |
| 008 | [safe-stop-home](008-safe-stop-home/) | Stop → raise pen → home → disable XY |
| 009 | [root-groups-as-layers](009-root-groups-as-layers/) | Fallback layers from root `<g>` groups |
| 010 | [macos-app-bundle](010-macos-app-bundle/) | PyInstaller `PlotPilot.app`, `./build.sh`, `./open.sh`, icons |
| 011 | [test-suite-fast-and-headless](011-test-suite-fast-and-headless/) | Fast pytest; hardware tests opt-in |
| 012 | [plot-optimization](012-plot-optimization/) | Path reordering option sent to axicli |
| 013 | [plotter-model-and-bounds](013-plotter-model-and-bounds/) | Model travel limits and page preflight |
| 014 | [plot-progress](014-plot-progress/) | Plot progress and preview estimate |
| 015 | [viewport-positioning-and-clipping](015-viewport-positioning-and-clipping/) | Position/scale artwork; geometric clip before axicli |
| 016 | [project-session](016-project-session/) | Versioned `.plotpilot` save and reopen |
| 017 | [svg-golden-baseline](017-svg-golden-baseline/) | SVG golden oracles; known geometry bugs as xfail |
| 018 | [fix-core-geometry](018-fix-core-geometry/) | Clip, arc flattening, degenerate cleanup |
| 019 | [canonical-svg-geometry](019-canonical-svg-geometry/) | One user-space → mm page mapping |
| 020 | [robust-layer-isolation](020-robust-layer-isolation/) | Layer isolation keeps root CSS, filters, and clips |
| 021 | [preview-equals-output](021-preview-equals-output/) | Preview renders the same prepared geometry as the plot |
| 022 | [vpype-evaluation](022-vpype-evaluation/) | Evaluate vpype as geometry engine (spike only; keep current engine) |
| 023 | [axicli-controls](023-axicli-controls/) | Explicit axicli path order, pen heights, `-N`, `-C`, home, estimate |
| 025 | [preview-performance](025-preview-performance/) | Cached flatten; async clip so position and scale stay responsive |
| 026 | [modern-transform-controls](026-modern-transform-controls/) | Slider-based X/Y/scale panel synced with preview drag |
| 027 | [window-resize-and-scroll](027-window-resize-and-scroll/) | Resizable window; page scrolls when the layout does not fit |
| 028 | [print-margins](028-print-margins/) | Editable safe print margins inside the physical work area |

Branch naming: `NNN-slug` (e.g. `010-macos-app-bundle`).

## Workflow (new work)

1. `/speckit-specify` — create or update `spec.md`
2. `/speckit-plan` — technical plan
3. `/speckit-tasks` — actionable tasks
4. `/speckit-implement` — code changes
5. `/speckit-converge` — gap check until converged

Principles: [.specify/memory/constitution.md](../.specify/memory/constitution.md).

## Upcoming (not specced as next slice)

- Release CI, signed/notarized macOS builds
- Additional plotter backends beyond AxiDraw CLI
