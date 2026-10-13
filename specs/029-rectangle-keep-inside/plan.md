# Implementation Plan: Rectangle Keep-Inside Clip

**Branch**: `029-rectangle-keep-inside` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/029-rectangle-keep-inside/spec.md`

## Summary

Add an optional axis-aligned keep-inside rectangle in machine millimetres. Preparation intersects it with the existing printable rectangle and runs the current Liang–Barsky clip once against that overlap. No rectangle leaves today's clip unchanged. Source SVG text and flattened document polylines are not modified. Preview preparation and plot preparation share that clip. This slice has no UI, no project-file field, and no new dependency.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing `ClipRect` / `clip_segment` (Liang–Barsky) and the svgelements flatten path. No new packages.

**Storage**: N/A. The rectangle is a caller argument. Project files and settings are unchanged.

**Testing**: pytest, no hardware. `uv run pytest` and `uv run ruff check` / `uv run ruff format --check` on `src` and `tests`.

**Target Platform**: macOS desktop (PlotPilot). Geometry stays Qt-free.

**Project Type**: desktop application (`src/plotpilot`)

**Performance Goals**: One extra rectangle intersection per prepare. No second flatten and no second clip pass. The flattened-polyline cache stays valid.

**Constraints**: Keep the printable area (work area inset by margins) as a hard limit. Do not plot into the margin. Do not change behavior when the rectangle is absent. Do not add UI, ellipse clipping, remove-inside, or a new dependency. Do not mutate source SVG or cached document polylines.

**Scale/Scope**: One Qt-free model, one optional argument on the existing prepare functions, geometry tests plus a preview/plot parity test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result |
|-----------|--------|
| I. macOS-first, portable core | Pass. The rectangle and the intersection live in Qt-free models and geometry. |
| II. Layered boundaries | Pass. No UI changes. Services pass the rectangle into geometry. Geometry does not import Qt. |
| III. Testable without hardware | Pass. Clip, empty overlap, margin intersection, and preview/plot parity are pytest-only. |
| IV. SpecKit slice, minimal scope | Pass. Slice 1 only. Drawing, persistence, circles, and remove-inside stay out. |
| V. Clarity over abstraction | Pass. One dataclass and one optional argument. No clip-engine interface. |

Post-design: same gates. Intersection-then-single-clip avoids a second algorithm and a new library.

## Project Structure

### Documentation (this feature)

```text
specs/029-rectangle-keep-inside/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── rectangle-keep-inside.md
├── checklists/requirements.md
├── tasks.md
└── implementation-notes.md
```

### Source Code (repository root)

```text
src/plotpilot/
├── models/clip_shape.py
├── geometry/plot_viewport.py
├── services/layer_geometry.py
├── services/preview_compute_service.py
├── services/preview_prepared_service.py
└── services/positioned_plot_service.py

tests/test_rectangle_keep_inside.py
```

**Structure Decision**: PlotPilot's existing layout. The rectangle model sits next to `PrintMargins`. Clipping stays in `plot_viewport.py`. UI, `PlotterService` call sites, and project JSON are untouched because the new argument defaults to absent.

## Complexity Tracking

No constitution violations.
