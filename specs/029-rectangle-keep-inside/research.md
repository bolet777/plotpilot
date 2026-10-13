# Research: Rectangle keep-inside clip

## 1. How should a rectangle cut the existing printable clip?

**Decision**: Intersect the keep-inside rectangle with the printable `ClipRect`, then call `clip_segment` once on that overlap.

**Rationale**: Liang–Barsky already keeps the inside of one axis-aligned rectangle and splits a path that exits and re-enters. The overlap of two axis-aligned rectangles is another axis-aligned rectangle. A second clip pass would duplicate that result and add a chance for the two windows to disagree. `docs/investigations/shape-clipping-feasibility.md` recommends this fold-in for the rectangle Keep inside slice.

**Alternatives considered**:

- Clip to the printable area, then clip again to the user rectangle. Same geometry for a convex rectangle, extra pass, rejected for this slice.
- Replace the printable rectangle with the user rectangle. Rejected: a rectangle that crosses the margin would plot into the margin.
- SVG clip paths or a painter mask. Rejected: the plotter would still receive uncut strokes.

## 2. What model should this slice introduce?

**Decision**: `ClipRectangle` in `src/plotpilot/models/clip_shape.py`: `x_mm`, `y_mm`, `width_mm`, `height_mm` in machine millimetres, y down. `validate()` rejects non-finite values and non-positive size. No `kind` and no `mode` field.

**Rationale**: This slice is only axis-aligned Keep inside. An ellipse enum or a remove-inside mode would be unused API. Later slices can extend the module. A square is equal width and height, not a second type.

**Alternatives considered**:

- A `ClipShape` union with rectangle and ellipse from day one. Rejected as unused surface area (constitution: minimal scope).
- Reuse `ClipRect` (`x_min`, `y_min`, `x_max`, `y_max`) as the public model. Rejected: callers think in origin and size, matching `PrintableArea`. `ClipRect` stays the internal clip window.

## 3. How does an empty overlap or a miss report failure?

**Decision**: A valid rectangle that does not overlap the printable area, or that overlaps it but contains no artwork, produces no polylines. Callers keep today's outcome: `PlotViewportError("No artwork intersects the plot area.")` on the plot path, and `ClippedLayerGeometry.error_message` with that same string on the preview path.

**Rationale**: The spec requires the same empty-plot outcome already used when artwork misses the printable area. That string is `_NO_INTERSECTION` in `layer_geometry.py` and the `emit_validated_plot_svg` error in `plot_viewport.py`.

**Alternatives considered**:

- A new "rectangle misses the printable area" message. Clearer, but it would break the spec's "same outcome" rule. A distinct message can wait until the UI can explain it.

## 4. What does the output validator check?

**Decision**: Pass the overlap rectangle into `emit_validated_plot_svg` as the clip window. The SVG page stays the full machine viewport. The existing validator still requires every point to lie in that clip window and in the machine work area.

**Rationale**: The overlap is inside the printable area, so margin safety is unchanged. Using the overlap as the clip window also rejects a point that sits in the printable area but outside the keep-inside rectangle. When no rectangle is supplied, the clip window stays the printable area, as it does today.

**Alternatives considered**:

- Validate only against the printable area. Sufficient for margin safety, weaker against a clip bug. Rejected because the overlap is still an axis-aligned rectangle the validator already understands.

## 5. Where is the argument threaded, and what stays untouched?

**Decision**: Optional `keep_inside: ClipRectangle | None = None` on `clip_document_polylines`, `prepare_positioned_plot_svg`, `position_and_clip_geometry`, `prepare_layer_plot_svg`, `compute_interactive_preview`, and `build_prepared_layer_preview`. `None` is the default.

**Rationale**: Preview polylines come from `position_and_clip_geometry`. Plot SVG comes from `prepare_positioned_plot_svg` via `prepare_layer_plot_svg`. Both must share the overlap or FR-007 fails. Default `None` means `PlotterService`, the main window, and existing tests keep current behavior without edits.

**Alternatives considered**:

- Thread the rectangle through `PlotterService` and `MainWindow` now. That is slice 2 (there is nothing to pass until the user can draw a rectangle).
- Store the rectangle on `ProjectSession`. Out of scope for this slice.

## 6. How is the source artwork kept unchanged?

**Decision**: Do not write the source SVG and do not replace `PreparedLayerGeometry.polylines`. The clip reads those polylines and returns a new list. Flattened geometry stays a tuple of tuples.

**Rationale**: `prepare_layer_geometry` already caches document-space polylines independent of placement. A keep-inside rectangle is applied after orient, scale, and translate, in machine space, same as the printable clip.
