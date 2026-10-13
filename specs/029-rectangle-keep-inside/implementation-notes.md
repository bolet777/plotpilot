# Implementation notes: Rectangle keep-inside clip

Slice 2 (`030-clip-rectangle-tool`) now draws this rectangle in the app and passes it through preview, plot, estimate, and the project file. The notes below still describe the geometry slice only.

**Status: geometry slice, frozen as written.** Slice 1 did not include a drawing tool. Automated pytest and ruff were run once while the slice was written; that is not a substitute for using the feature.

Slice 1 only. No preview drawing, no project-file field, and no new dependency.

## Decisions

**One Liang–Barsky pass on the overlap.** `overlap_clip_rect` intersects `ClipRectangle` with the printable `ClipRect` (work area inset by margins). `clip_segment` then runs once on that overlap. A second clip pass is not used. When the overlap has no positive area, including a shared edge, preparation returns no polylines.

**`ClipRectangle` has no mode and no shape kind.** Fields are `x_mm`, `y_mm`, `width_mm`, `height_mm` in machine millimetres, y down. `validate()` raises `ClipRectangleError` for non-finite values or a non-positive size. A square is equal width and height. Ellipse and remove-inside stay out of this type until their slices.

**`keep_inside=None` is the default** on `clip_document_polylines`, `prepare_positioned_plot_svg`, `position_and_clip_geometry`, `LayerGeometryCache.clipped_for`, `prepare_layer_plot_svg`, `compute_interactive_preview`, and `build_prepared_layer_preview`. `PlotterService` and `MainWindow` are not edited. They keep the printable-area clip.

**Empty results reuse the existing sentence** `No artwork intersects the plot area.` Plot preparation raises `PlotViewportError`. Preview preparation sets that string on `ClippedLayerGeometry.error_message` and `PreparedLayerPreview.preparation_error`.

**The output validator uses the overlap.** `prepare_positioned_plot_svg` passes the overlap into `emit_validated_plot_svg`. `build_prepared_layer_preview` does the same via `overlap_clip_rect`, so a point outside the rectangle fails both paths. The SVG page stays the full machine viewport. With no rectangle, the validator window is still the printable area.

**Source artwork is not rewritten.** The clip reads `PreparedLayerGeometry.polylines` and returns a new list. The cached tuple is left in place. The source SVG file is not opened for writing.

## Tests

`tests/test_rectangle_keep_inside.py` covers validation, edge trimming, a diagonal, a fully inside stroke, a miss, exit/re-enter without a bridge, an endpoint touch, margin overlap, a rectangle larger than the printable area, a zero-area shared edge, omitted-rectangle regression, source and flatten immutability, and preview/plot/interactive parity.

Existing clip, margin, positioned-plot, and preview/plot parity tests were run unchanged.

## Left for Slice 2

Pass a `ClipRectangle` from the main window into preview refresh, `prepare_layer_plot_svg`, estimate, and multi-layer plot. Draw, move, and delete the rectangle on the preview. Store it on `ProjectSession` as an optional version-1 key. Until that wiring exists, the running application never supplies a rectangle.
