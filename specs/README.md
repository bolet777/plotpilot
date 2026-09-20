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
| 010 | [macos-app-bundle](010-macos-app-bundle/) | PyInstaller `PlotPilot.app`, `lance.sh`, icons |

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
