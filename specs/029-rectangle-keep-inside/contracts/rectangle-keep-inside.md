# Contract: Rectangle keep-inside clip

## Argument

These functions accept `keep_inside: ClipRectangle | None = None`:

- `clip_document_polylines`
- `prepare_positioned_plot_svg`
- `position_and_clip_geometry`
- `prepare_layer_plot_svg`
- `compute_interactive_preview`
- `build_prepared_layer_preview`

`None` means printable-area clipping only, including the current margin inset. Callers that omit the argument are unchanged.

`ClipRectangle.validate()` runs before the clip. Invalid rectangles raise `ClipRectangleError` and are not clipped.

## Clip window

When `keep_inside` is set, the clip window is the positive-area overlap of:

- the printable rectangle already computed from the viewport and margins
- `keep_inside`

Liang–Barsky (`clip_segment`) runs once on that overlap. Path splitting, 0.01 mm snap and dedupe, and 0.05 mm curve flatness stay as they are.

When the overlap has no positive area, or the overlap contains no strokes, preparation produces no polylines:

- Plot path: `PlotViewportError` with `No artwork intersects the plot area.`
- Preview path: `ClippedLayerGeometry.error_message` equal to that same sentence, `path_count == 0`, empty polylines

## Output

Emitted plot SVG keeps the machine viewport size. Every `M`/`L` coordinate lies in the overlap (within the existing 0.01 mm tolerance) and in the machine work area. The source SVG string passed in is not modified. Flattened document polylines on `PreparedLayerGeometry` are not replaced.

Preview preparation (`build_prepared_layer_preview` / `position_and_clip_geometry`) and plot preparation (`prepare_layer_plot_svg`) given the same drawing, placement, viewport, margins, and `keep_inside` produce the same polylines.

## Out of scope for this contract

UI drawing, project JSON, `PlotterService` parameters, circles, ellipses, rotated rectangles, and remove-inside.
