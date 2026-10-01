# Plan — 025 preview performance

## Technical context

- Python 3.12, PySide6, existing `QThreadPool` pattern from `PlotterService`.
- Geometry stays in `geometry/plot_viewport.py`. Same Liang–Barsky clip, same 0.05 mm flatness (`CURVE_FLATNESS_MM`).
- No new dependencies.

## Design

### Stable vs dynamic

Stable for one document and one layer:

- isolated layer SVG
- page size
- content diagnostics
- flattened polylines in document millimeters

Dynamic:

- `ArtworkTransform` (X, Y, scale)
- viewport width and height (model travel or A4/A3 portrait/landscape)

`PreparedLayerGeometry` holds only the stable data. It does not hold Qt objects.

### Two stages

1. `prepare_layer_geometry` — isolate, diagnose, flatten once.
2. `position_and_clip_geometry` — transform and clip the cached polylines.

`prepare_positioned_plot_svg` / `prepare_layer_plot_svg` call the same stages, then `emit_validated_plot_svg`, which still runs `_validate_output_geometry`. The plot path does not trust the preview: it emits and validates again.

### Cache

`LayerGeometryCache` stores one `PreparedLayerGeometry`, keyed by `id(document)` and `layer_id`.

Invalidate when the document or the selected layer changes (`invalidate()` from the layer preview update).

Do not invalidate for X, Y, scale, fallback size, orientation, or window resize.

### Threading

`PreviewComputeService` submits a `QRunnable`. The worker calls `compute_interactive_preview` and returns an `InteractivePreview`. It does not touch widgets.

`PreviewResultGate` issues a generation on each submit. The UI slot applies a result only when `accept(generation)` is true (newest id, and the service has not shut down). `closeEvent` stops the debounce timer and calls `shutdown()`, which rejects in-flight results and blocks further signals.

The 50 ms debounce timer is unchanged. It only drops redundant jobs. It is not what makes the spinboxes move.

### Rendering

Interactive plotted strokes are `QPainter.drawPolyline` on polylines already clipped in the worker. `paintEvent` does not clip. A widget-local pixmap is rebuilt when those polylines or the widget size change, so a drag does not walk every point on each mouse move.

The faint source stays on `QSvgRenderer`. Measurements showed that renderer is not the freeze (about 1 ms to draw on an 80-path drawing, created once per layer). It is not pixmap-cached.

`set_prepared_plot` remains for callers that still pass an SVG string. The main window uses `set_clipped_plot`.

## Constitution

- Preview at rest matches plot geometry (parity tests).
- Plot validator remains on the axicli path.
- Headless tests, no hardware.
