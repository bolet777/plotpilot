# Implementation Plan: Interactive Keep-Inside Rectangle

**Branch**: `030-clip-rectangle-tool` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/030-clip-rectangle-tool/spec.md`

## Summary

Add one Clip tool on the existing preview strip. Dragging stores a `ClipRectangle` in machine millimetres, clamped to the printable area. The overlay is painted by the preview widget. Preview refresh, plot, estimate, and multi-layer jobs pass that rectangle into the Slice 1 `keep_inside` argument. Projects gain an optional `clipping` object on format version 1. No new dependency, no SVG clip path, and no painter mask of the plotted strokes.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: PySide6 for the tool and overlay. Slice 1 `ClipRectangle`, `overlap_clip_rect`, and Liang–Barsky. No new packages.

**Storage**: Optional `clipping.rectangle` in `.plotpilot` JSON version 1. Absent means no rectangle.

**Testing**: pytest (widget drags, project JSON, plot and multi-layer parity) plus ruff. A real `plotpilot` window is launched for visual checks.

**Target Platform**: macOS desktop

**Project Type**: desktop application (`src/plotpilot`)

**Performance Goals**: Rectangle edits reuse `LayerGeometryCache` and the 50 ms preview worker. The UI thread only updates the rectangle and repaints the overlay.

**Constraints**: Clip and move tools are exclusive. Zoom and pan stay view-only. Artwork transform does not move the rectangle. Margins still win. Do not bump `SUPPORTED_VERSION`. Do not merge to main in this slice.

**Scale/Scope**: One rectangle, four corner handles, Delete/Backspace, project round-trip, and the existing prepare entry points.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result |
|-----------|--------|
| I. macOS-first, portable core | Pass. Drag math is Qt-free. The widget only maps pixels. |
| II. Layered boundaries | Pass. The widget edits a model. Services pass it into geometry. Geometry does not import Qt. |
| III. Testable without hardware | Pass. Fake plotter and headless Qt cover plot and drag tests. |
| IV. SpecKit slice, minimal scope | Pass. No ellipse, no remove-inside, no second panel. |
| V. Clarity over abstraction | Pass. One optional field and the existing `keep_inside` argument. |

Post-design: same gates.

## Project Structure

### Documentation (this feature)

```text
specs/030-clip-rectangle-tool/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/clip-rectangle-tool.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/plotpilot/models/clip_shape.py
src/plotpilot/models/project_session.py
src/plotpilot/models/multi_layer_job.py
src/plotpilot/services/project_file_service.py
src/plotpilot/services/plotter_service.py
src/plotpilot/services/multi_layer_plot_service.py
src/plotpilot/ui/preview_widget.py
src/plotpilot/ui/preview_workspace.py
src/plotpilot/ui/main_window.py
src/plotpilot/ui/theme.py
tests/test_clip_rectangle_tool.py
```

**Structure Decision**: The rectangle lives on `LayerPreviewWidget` the same way `ArtworkTransform` does. `MainWindow` forwards it. Geometry from Slice 1 is unchanged except that callers now pass a value.

## Complexity Tracking

No constitution violations.
