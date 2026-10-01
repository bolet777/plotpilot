# Implementation Plan: Editable Print Margins

**Branch**: `028-print-margins` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-print-margins/spec.md`

## Summary

Add a Qt-free `PrintMargins` pair (horizontal and vertical, default 10 mm) and a `PrintableArea` rectangle whose origin is offset by those margins. Clipping, the final geometry validator, preview, estimate, and plot all use that rectangle in real machine coordinates. The physical work area is unchanged. Flattened geometry stays cached; a margin edit only re-runs transform, clip, and the preview update.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: PySide6 (UI only), existing Liang–Barsky clipper, svgelements flatten path (unchanged)

**Storage**: Qt `QSettings` for plain-session defaults; `.plotpilot` JSON v1 optional `print` object for projects

**Testing**: pytest, no hardware. `./scripts/test_fast.sh`, `uv run pytest -m "not hardware"`, ruff check and format

**Target Platform**: macOS desktop (PlotPilot)

**Project Type**: desktop application (`src/plotpilot`)

**Performance Goals**: Margin edits reuse `LayerGeometryCache` flattened polylines. No extra SVG parse or curve flatten on the UI thread.

**Constraints**: Do not add four independent margins, auto-fit, auto-center, axicli flag changes, work-area dimension changes, or a new flatten path. Leave at least 0.1 mm of printable width and height. Physical coordinates stay machine-absolute.

**Scale/Scope**: Two numeric fields, one derived rectangle, threaded through the existing preview/plot pipeline.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result |
|-----------|--------|
| I. macOS-first, portable core | Pass. Margin math is Qt-free. `QSettings` stays in `SettingsService`. |
| II. Layered boundaries | Pass. Models and geometry do not import Qt. UI only edits values and paints boundaries. |
| III. Testable without hardware | Pass. Clip, validator, project JSON, and widget wiring are pytest-covered. |
| IV. SpecKit slice, minimal scope | Pass. No calibration, no per-side margins, no pipeline rewrite. |
| V. Clarity over abstraction | Pass. One dataclass pair and clip-rectangle parameters on the existing functions. |

Post-design: same gates. No new framework and no extra plotter interface.

## Project Structure

### Documentation (this feature)

```text
specs/028-print-margins/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── print-margins.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/plotpilot/
├── models/print_margins.py
├── models/project_session.py
├── geometry/plot_viewport.py
├── services/layer_geometry.py
├── services/preview_compute_service.py
├── services/preview_prepared_service.py
├── services/positioned_plot_service.py
├── services/plotter_service.py
├── services/multi_layer_plot_service.py
├── services/project_file_service.py
├── services/settings_service.py
├── ui/artwork_transform_controls.py
├── ui/preview_widget.py
└── ui/main_window.py

tests/test_print_margins.py
```

**Structure Decision**: Single Python package. New domain types live in `models/`. Clipping stays in `geometry/plot_viewport.py`. Persistence follows the existing fallback-work-area split between `QSettings` and project session.

## Design

### Physical work area vs printable area

The machine work area remains `PlotViewport` / `PreviewWorkArea`: origin (0, 0), size = travel width × height. Margins do not change those dimensions and do not change axicli model flags.

`PrintableArea` is derived:

```text
x      = horizontal_mm
y      = vertical_mm
width  = work_width  - 2 * horizontal_mm
height = work_height - 2 * vertical_mm
```

Example: 300 × 217.9 mm with 10 / 10 → x=10, y=10, width=280, height=197.9. A4 landscape 297 × 210 with 10 / 10 → x=10..287, y=10..200. Explicit AxiDraw models use the same formula on `PlotterModelInfo` travel.

### Clipping origin offset

`clip_document_polylines` and `emit_validated_plot_svg` accept an arbitrary rectangle `x_min, y_min, x_max, y_max`. When omitted, the rectangle is still the full work area `(0, 0, width, height)` so existing golden calls stay full-bleed.

The product path (`prepare_layer_plot_svg`, preview compute, estimate, plot) passes the printable rectangle. It does not translate artwork to fake a margin and it does not shrink the viewport while keeping the origin at (0, 0). Emitted SVG `width` / `height` / `viewBox` stay the machine work area. Stroke coordinates are machine millimeters inside the printable rectangle.

The validator checks both the mechanical work area and the printable rectangle, using the existing 0.01 mm tolerance. Points in the margin fail even when they are still inside the machine.

### UI

Compact rows on the existing plot-area footer in `ArtworkTransformControls`:

```text
Plot area: <existing label>
Margins:  H [10.0 mm]   V [10.0 mm]
Printable: <width> × <height> mm
```

`QDoubleSpinBox`: 0.1 mm decimals, 1 mm step, minimum 0, keyboard editable. Maximum is `(span - 0.1) / 2`, floored to 0.1 mm, so a positive printable size remains. The printable line refreshes when model, A4/A3, orientation, or margins change.

Preview paints the existing red dashed work-area rectangle and a solid inner rectangle using the widget palette text color (readable in light and dark). Faint source context stays unclipped. Prepared polylines are the clipped geometry.

### Persistence and dirty state

`QSettings` keys `print/margin_horizontal_mm` and `print/margin_vertical_mm`. Missing or invalid stored values fall back to 10 / 10 (same recovery style as invalid plot settings).

Project JSON v1 adds an optional object:

```json
"print": {
  "margin_horizontal_mm": 10.0,
  "margin_vertical_mm": 10.0
}
```

Missing `print` → 10 / 10. Non-numeric, negative, or impossible margins (relative to the project's resolved work area) raise `ProjectFileError`. Format version stays 1.

`SettingsService.begin_project_session` holds project margins in memory and does not write `QSettings`. `end_project_session` restores the global values. Changing either spin marks the open document dirty, matching orientation changes. Save clears the dirty flag as today.

### Performance

Margin edits call the existing debounced preview refresh. They do not invalidate `LayerGeometryCache`. `compute_interactive_preview` receives the cached flattened polylines and only transforms and clips.

### Safety

`PrintMargins.validate` rejects non-finite and negative values. `validate_for_work_area` rejects insets that leave less than 0.1 mm of printable width or height. The plot path turns that into `PlotViewportError` instead of crashing. UI spin ranges prevent the impossible value in normal editing.

## Complexity Tracking

No constitution violations.
