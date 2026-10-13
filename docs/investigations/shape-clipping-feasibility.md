# Shape-based path clipping — feasibility

Investigation only. Conclusions below are from the repository as inspected for
this study. Items marked **Assumption** were not executed or measured in this
pass.

**Follow-up status:** Slice 1 (geometry) is frozen in
`specs/029-rectangle-keep-inside/`. Slice 2 (the clip tool) is frozen in
`specs/030-clip-rectangle-tool/`. Slice 3 (circle and ellipse keep-inside) is
frozen in `specs/031-ellipse-keep-inside/`. Slice 4 adds remove-inside
for both shapes (`specs/032-remove-inside/`). A plot uses the drawn shape and mode.

## 1. Executive summary

Shape clipping is feasible on the pipeline PlotPilot already uses for the
work area: flatten stroked curves to polylines, place them in machine
millimetres, cut the polylines, then preview and plot those polylines.

An axis-aligned rectangle or square in **Keep inside** mode is a tighter
`ClipRect` passed to the existing Liang–Barsky clipper, intersected with the
printable area. Circle, ellipse, and **Remove inside** need a new intersection
step. They still belong in the same walker. They do not need a second clipping
engine, SVG masks, or a new dependency.

Liang–Barsky itself only keeps the inside of one axis-aligned rectangle. A
line against a convex shape still has at most one inside span, so Keep inside
for a circle or ellipse fits the current “one span per segment” walker.
Remove inside can leave two outside spans on one segment, so that mode needs
the walker to emit a list of spans. Concave polygons, freeform paths, and
several shapes at once can leave more than two spans; leave those for later.

Simplest product shape: one clipping shape, stored in machine millimetres on
the project (same scope as margins), drawn from the existing preview tool
strip, applied live with the current worker. No Apply button, no undo stack,
no per-layer shapes.

**Implement first:** axis-aligned rectangle, Keep inside, wired through preview
and plot so the two stay identical. Then ellipse Keep inside. Then Remove
inside for both.

Overall complexity for that phase: **Medium**. The rectangle-only first slice
is **Low**.

## 2. Existing clipping architecture

Verified from the code, not from the older slice notes alone. Slice 015
research describes the original design; the implementation has since grown
margins, orientation, a flatten cache, and a polyline preview.

### Pipeline

```text
isolate layer SVG
  → parse page mm (svg/page_geometry.py, svg/plot_dimensions.py)
  → svgelements segments, stroke only
  → flatten curves to polylines in document mm
  → orient page (0/90/180/270), then scale and translate
  → snap near the clip edges
  → Liang–Barsky segment clip
  → drop degenerate polylines
  → preview draws those polylines
  → plot emits M/L SVG and validates every vertex
  → axicli clips again to the machine rectangle
```

### Where it lives

| Step | Location |
| --- | --- |
| Rectangle type and segment clip | `ClipRect`, `clip_segment` in `src/plotpilot/geometry/liang_barsky.py` |
| Flatten, place, clip, emit, validate | `src/plotpilot/geometry/plot_viewport.py` |
| Flatten once, clip many times | `prepare_layer_geometry`, `position_and_clip_geometry`, `LayerGeometryCache` in `src/plotpilot/services/layer_geometry.py` |
| Preview job off the UI thread | `compute_interactive_preview`, `PreviewComputeService` in `src/plotpilot/services/preview_compute_service.py` |
| Plot and estimate SVG | `prepare_layer_plot_svg` in `src/plotpilot/services/positioned_plot_service.py`, called from `PlotterService.start_plot_layer` and `request_pre_plot_estimate` |
| Multi-layer | `MultiLayerPlotService` forwards the same transform and margins into `PlotterService` |
| Printable rectangle | `PrintMargins`, `printable_area_for` in `src/plotpilot/models/print_margins.py` |
| Placement | `ArtworkTransform`, `orient_point` in `src/plotpilot/models/artwork_transform.py` |
| Preview painting | `LayerPreviewWidget.set_clipped_plot` and `_paint_physical_preview` in `src/plotpilot/ui/preview_widget.py` |
| Debounce | `MainWindow._preview_prep_timer` at 50 ms, then `_schedule_prepared_preview_refresh` |

There are two public entries into the same private walker, `_clip_document_subpaths`:

- Preview: `clip_document_polylines` via `position_and_clip_geometry`.
- Plot: `prepare_positioned_plot_svg`, which flattens again and then calls the same walker.

`build_prepared_layer_preview` uses the preview entry and then
`emit_validated_plot_svg`. Interactive preview does **not** emit SVG on each
drag. It draws the clipped point lists. Plot still emits SVG and runs
`_validate_output_geometry`.

### Algorithms and libraries

- **Parse and flatten:** `svgelements` (`SVG.parse`, `Shape.segments(transformed=True)`). Runtime dependency in `pyproject.toml`. Curves are sampled at `CURVE_FLATNESS_MM = 0.05`. Steps per segment are capped at `MAX_FLATTEN_STEPS_PER_SEGMENT = 512`.
- **Clip:** PlotPilot-owned Liang–Barsky. One accepted parameter interval `[u1, u2]` per segment. The four edges are the clip rectangle.
- **Cleanup:** points within `COORD_TOLERANCE_MM = 0.01` of a clip edge are snapped onto that edge (`_snap_point_to_clip`). Consecutive points within 0.01 mm are merged. Polylines with fewer than two distinct points are dropped (`_sanitize_polyline`).
- **Not used for this clip:** `vpype` is a **dev** dependency only. Slice 022 decided to keep the current engine. `shapely`, `pyclipper`, and `numpy` are not PlotPilot runtime dependencies. axicli’s own rectangular clip (Cohen–Sutherland) and its pyclipper hidden-line mode run later, inside axicli, on the SVG PlotPilot already wrote.

### What is clipped

`_flatten_document_subpaths` keeps shapes whose stroke is present and is not `none` or `transparent`. Fill-only shapes, text, and images are counted for warnings in `preview_prepared_service.py` and are not flattened into plot motion.

Each `Move` starts a subpath. `Close` appends the subpath start and flushes, so a closed contour becomes a polyline whose first and last points meet. Output SVG (`_emit_svg`) is only `M`/`L` with `fill="none"`. A source `Z` is not preserved as a close command.

`plot_segment` treats a rejected segment as a pen-up: it flushes the current polyline. A segment that leaves and later re-enters becomes two polylines. `tests/test_geometry_clipping.py` (`test_clip_exit_travel_outside_reenter_splits_polylines`) locks that split. The same walker does not draw a bridge across the outside region.

### Scaling, offsets, margins

Order inside `plot_segment`, verified in `plot_viewport.py`:

1. Rotate the document point about the page (`orient_point`) when orientation is not `PRESERVED`.
2. `machine = (x_mm, y_mm) + scale * oriented_document_point`.
3. Snap, then clip to one rectangle.

That rectangle is the printable area, not the raw machine travel. `position_and_clip_geometry` and `prepare_layer_plot_svg` both call `printable_area_for` and pass `clip_x_min_mm` / `clip_y_min_mm` / `clip_x_max_mm` / `clip_y_max_mm`. Default margins are 10 mm on each side (`PrintMargins`). The SVG page written for axicli stays the full viewport (`width`/`height` = machine width and height, `viewBox="0 0 W H"`, 1 user unit = 1 mm). Vertices must lie in the printable rectangle **and** in the machine rectangle (`_validate_output_geometry`).

Margins do not shift the machine origin. They inset the clip window. A point in the margin band is outside the clip and is removed.

### Preview versus plot

The black preview strokes are the clipped polylines in machine millimetres (`set_clipped_plot` → `_plot_pixmap_for`). They are not an SVG `<clipPath>`.

The faint ghost is the **unclipped** layer. It is either cached context polylines or a `QSvgRenderer`, drawn with the live `ArtworkTransform`. `QPainter.setClipRect` on that ghost only limits painting to the work-area widget rect. It does not change the plotted geometry. While a clip is in flight, `set_clip_pending` hides the previous black ink so a stale cut is not shown on top of a moved ghost.

Zoom and pan change `PhysicalPreviewLayout.mm_to_px` and `workspace_x_px` / `workspace_y_px` (`_current_physical_layout`). `widget_to_mm` divides by that scale. Comments and the UI guide state that view zoom and pan do not affect plotting. The preview scale is one value for both axes (`compute_physical_preview_layout`), so a circle in millimetres stays a circle on screen.

### Source SVG clip paths

PlotPilot has no `clipPath` / `clip-path` handling under `src/plotpilot`. Isolation copies the layer subtree; flattening uses transformed stroke segments. **Assumption:** svgelements does not apply SVG clip paths inside `segments(transformed=True)`. That was not verified against the library. Even if it did, that would be a source-file mask, separate from a user shape drawn in PlotPilot.

## 3. Reusable components

Use these as they are:

- **Flatten cache.** `PreparedLayerGeometry.polylines` is document-space and independent of placement. A clipping shape must not invalidate that cache. Reclip the way `ArtworkTransform` already does.
- **Worker, generation gate, 50 ms timer.** Shape drags should call `_schedule_prepared_preview_refresh`, not clip on the UI thread.
- **Subpath split semantics.** Flush on a gap, start a new polyline on re-entry, drop spans shorter than 0.01 mm. Tests in `tests/test_geometry_clipping.py` are the contract to keep for the rectangle case.
- **Safety validator.** Keep `_validate_output_geometry` on the printable rectangle. A shape cut that can only emit points on segments already inside that rectangle still passes it. The validator does not need to know the circle.
- **Preview polyline renderer.** `set_clipped_plot` already shows the physical result. The shape outline is an extra paint on top, in the same machine-mm space as the printable boundary (`_paint_printable_boundary`).
- **Pointer mapping.** `widget_to_mm` and the move-tool delta (`delta_px / mm_to_px`) already convert a zoomed, panned view into machine millimetres.
- **Session persistence pattern.** `ProjectSession` plus an optional JSON block, same as `artwork_transform` and `print`. Missing block means “no shape”, so existing projects stay valid without a version bump. `read_project_file` rejects `version < SUPPORTED_VERSION` (currently 1), so a bump would refuse old files. An optional key on version 1 avoids that.
- **Parameter plumbing.** `print_margins` is already threaded through `compute_interactive_preview`, `prepare_layer_plot_svg`, `PlotterService.start_plot_layer`, `request_pre_plot_estimate`, and `MultiLayerPlotService`. A clipping shape should follow that same argument, not a preview-only field.

Do not reuse Liang–Barsky as the circle algorithm. Do reuse the walker that calls it.

`clip_segment` returns a single span. `_clip_document_subpaths` assumes that one span (`accept, nx0, ny0, nx1, ny1`). That assumption holds for Keep inside against any convex shape. It does not hold for Remove inside, or for a non-convex boundary.

## 4. Geometric feasibility

Phase 1 shapes are convex. A straight segment meets a convex boundary in at most two points, so the inside of the shape is one interval of the segment (or none, or the whole segment).

| Shape | Keep inside | Remove inside |
| --- | --- | --- |
| Axis-aligned rectangle / square | Already implemented, if the clip rectangle is the intersection of the user rectangle and the printable area | Not implemented. The kept region is the printable rectangle with a rectangular hole. One segment can contribute two pieces. |
| Circle | New line–circle test, then the existing one-span walker | Same intersection test; walker must emit both outside pieces |
| Ellipse | Map the segment into the unit circle (divide by the radii), run the circle test, map the hit points back. An ellipse is convex, so the one-span property remains. | Same as the circle, after that map |

Square is not a separate curve type. It is a rectangle with equal width and height. The isotropic preview scale keeps that square on screen.

### What the current walker already covers

Verified by `clip_segment` and the clipping tests:

- Segment fully inside, fully outside, entering, leaving, or crossing a rectangle.
- A path that exits and re-enters, split into two polylines, with no diagonal bridge.
- Several subpaths stay separate (`test_disconnected_paths_not_merged`).
- A closed path that stays inside stays one polyline.
- Open paths are the normal case after a split.
- Boundary and corner contact.
- Scale then clip (`test_clip_scaled_rectangle_partially_outside`).
- Degenerate output dropped (slice 018, B13).

A path that crosses a convex boundary many times is a sequence of segments. Each segment is still one inside span. The walker already chains those spans and flushes on gaps. Compound SVG paths are already separate subpaths before clipping.

### What it does not cover

- **Remove inside**, even for a rectangle. After the printable clip, subtracting an inner rectangle leaves up to two kept pieces per segment.
- **Circle and ellipse.** No line–curve intersection exists in `src/plotpilot/geometry`.
- **Rotated rectangles.** Liang–Barsky is axis-aligned. A rotated rectangle is a convex polygon and needs a different edge test (Cyrus–Beck or an equivalent). Phase 1 does not require rotation. **Recommendation:** omit rotation. If a later slice adds it, treat the rectangle as a 4-gon, not as `ClipRect`.
- **Concave polygon, freeform, or several shapes.** One segment can have many inside spans. Union of two circles is not convex. That needs a span list of unbounded length, or a polygon clipper. Out of phase 1.
- **True Bézier clipping.** Unnecessary. Artwork curves are chords at 0.05 mm before any clip. The shape boundary is applied to those chords. The boundary itself stays exact (circle or ellipse equation on the chord). The 0.05 mm error is the existing curve error, not a new mask error. Clipping control points of cubics would diverge from axicli’s flatten-then-clip behaviour and from preview/plot parity (slice 021, slice 025).

### Numerical and degenerate cases

Existing tolerances, verified:

- Flattening: 0.05 mm.
- Snap and dedupe: 0.01 mm.
- Empty result: `PlotViewportError` / `ClippedLayerGeometry.error_message` = `"No artwork intersects the plot area."`
- Invalid rectangle: `ClipRect` rejects `x_max < x_min` or `y_max < y_min`. Zero-area margins raise `PrintMarginsError`.

For a circle or ellipse, plan on these cases (not implemented, standard for this test):

- Zero or negative radius: reject in the model, same as a non-positive clip rectangle.
- Discriminant near zero (tangent): treat as a miss or as a single point, then let `_sanitize_polyline` drop a zero-length span. Use a tolerance on the order of 0.01 mm so a tangent does not flicker.
- Very thin ellipse: the unit-circle map divides by the smaller radius. Guard a minimum radius (for example the existing `MIN_PRINTABLE_MM = 0.1`, or the 0.01 mm coordinate tolerance) before dividing.
- Intersection parameters just outside `[0, 1]` because of rounding: clamp into the segment, then snap with the same 0.01 mm test used by `_points_near`.
- Shape that misses the printable area entirely: intersection is empty; keep today’s empty-artwork error.
- Shape that only grazes a polyline at one point: drop it, as zero-length segments are dropped today.

**Assumption:** double-precision quadratics are stable at plotter scale (tens to hundreds of millimetres, 0.01 mm tolerance). No measurement was run.

### Existing dependencies

`svgelements` and the stdlib (`math`) are enough for phase 1. A line–circle quadratic is a few operations per segment. Ellipse clipping is that test in scaled coordinates.

`vpype` / Shapely / pyclipper would add a packaging surface the project already declined (slice 022: numpy, scipy, shapely, multiprocess, on the order of 100 MB). They become relevant only for concave or freeform boundaries. They are not required to judge phase 1 feasible.

## 5. Technical alternatives

| Approach | Fit | Why it is or is not the path |
| --- | --- | --- |
| **A. Second pass on the current polylines** | Phase 1 | Keep Liang–Barsky as the printable-area cut. Then Keep inside (one span) or Remove inside (list of spans) against the user shape. Preview, plot, estimate, and the validator stay on one function: `_clip_document_subpaths` or a helper it calls. |
| **B. User rectangle replaces `ClipRect` directly** | Keep inside, axis-aligned only | Correct when the user rectangle is intersected with the printable area first. Intersection of two axis-aligned rectangles is still a `ClipRect`. This is the whole geometry change for the first slice. It cannot represent a hole or a circle. |
| **C. SVG `<clipPath>` or `QPainter.setClipPath`** | Reject | Would hide pixels. axicli would still receive the uncut strokes. The ghost already uses a painter clip for display only; the black ink and the plot file are real cuts. |
| **D. Qt `QPainterPath` boolean ops** | Reject | Geometry must not import Qt (`docs/ARCHITECTURE.md`). Plot preparation would not share the UI clip. |
| **E. vpype `crop` or Shapely / pyclipper** | Later, only if freeform is required | Slice 022 kept the current engine. A general polygon clipper is the right tool for concave freeform, and the wrong dependency for a circle. |
| **F. Exact cubic clipping** | Reject for this feature | Breaks the flatten-once contract and the 0.05 mm parity between preview and plot. |

Recommended architecture is **A**, with **B** as the first slice inside A.

Safety order, for every mode:

1. Place polylines in machine millimetres (existing).
2. Clip to the printable rectangle (existing Liang–Barsky). This is what keeps pen motion out of the margins and off the machine limits.
3. Apply the user shape to those already-safe segments.
4. Sanitize and validate against the printable rectangle (existing).

Step 3 never sees a segment outside the printable area, so a circle drawn across the margin cannot emit points in the margin. axicli’s later rectangular bounds clip remains a backstop for the machine rectangle only. It will not restore a circle cut, and it will not re-apply one. The circle cut has to be in the SVG PlotPilot writes.

## 6. UX proposals

The interface already has a dense Transform tab (position, scale, orientation, margins) and a small vertical tool strip on the preview (`PreviewWorkspace`: move, zoom in, zoom out, fit). The move tool is the pattern to copy: a checkable overlay button, drag in machine millimetres, live update through the same timer and worker. There is no undo stack anywhere in `src/plotpilot`.

Clipping should feel like that move tool. One shape. Two modes. Draw, move, resize, delete.

### A. Minimal contextual toolbar

Add controls only on the preview overlay, and only when they apply.

- One **Clip** tool beside the move tool. Choosing it turns the move tool off, and the reverse, so one left-drag has one meaning. Middle-button pan and wheel zoom stay as they are.
- Inside the tool, two shape buttons: **Rectangle** and **Ellipse**. Shift while dragging constrains a square or a circle. No third and fourth tools.
- Drag on the paper to create the shape. The drag is converted with `widget_to_mm`. The shape is stored in machine millimetres.
- After it exists: drag inside to move, drag a handle to resize. Delete (and a small clear control on the overlay) removes it.
- Two mode buttons appear only while a shape exists: **Keep inside** and **Remove inside**.
- The outline is painted in machine space, cosmetic pen, translucent fill, in a colour that is not `COLORS.printable_outline` (`#2f7df6`, already used for the dashed printable rectangle and the accent). The black polylines remain the cut result. The ghost remains the unclipped layer, which is what shows the user what was removed.
- The shape outline moves on the UI thread during the drag. The black ink updates when the worker returns, using the existing pending state.

No numeric fields in this approach. The cursor readout already shows machine X/Y.

### B. Dedicated compact clipping panel

A card on the Transform tab (or a fourth properties tab):

- Shape type, mode, and millimetre fields (origin and size, or centre and radii).
- Buttons: draw on preview, delete.
- The preview still needs the drag handles from approach A, or the panel is typing-only and fails the “draw it on the work area” goal.

The panel matches how margins work today (sliders plus a diagram) and is better when the user wants an exact 40 mm circle. It adds a second place that can disagree with the canvas, and the Transform tab is already the longest panel.

### Comparison

| | Contextual toolbar | Clipping panel |
| --- | --- | --- |
| Controls on screen by default | One extra tool button | A card of fields even when clipping is unused |
| Drawing | The tool is the drawing | The panel must still switch the preview into a draw mode |
| Precise millimetres | Cursor readout only; exact values wait for a later slice | Spin boxes from the start |
| Risk of preview ≠ plot | Low, if the shape object is the only state | Higher if panel fields and the canvas shape can diverge |
| Fit with current UI | Same pattern as the move tool | Same pattern as margins, in a panel that is already full |
| Implementation surface | `preview_workspace.py`, `preview_widget.py`, `main_window.py` wiring | Those files plus `artwork_transform_controls.py` or a new card |

Shared behaviour, either approach:

- **Live, no Apply button.** Transform updates are live. An Apply state would make the preview differ from the next plot. Slice 021’s rule is that the preview is the prepared geometry.
- **Delete restores today’s margin clip.** A separate disable toggle is a third state. Deleting the shape is the off switch. Drawing again is the on switch.
- **No new undo stack.** Position and scale have no undo either; they have Reset. Delete is the reset for this feature.
- **Lock while plotting.** The move tool already disables when transform controls lock. The clip tool should follow `set_transform_controls_enabled`.

## 7. Recommended UX

Use **approach A**, the contextual toolbar.

It is the smallest set of controls that still lets someone draw the shape on the work area, move it, and choose Keep inside or Remove inside. Put millimetre spin boxes in a later slice if exact entry is needed; do not block the first slice on them.

Default mode: **Keep inside**. Default shape: none, which is today’s behaviour.

Visual rules:

- Printable area: existing blue dashed rectangle.
- Clipping shape: a different hue, dashed, with a light fill, drawn after the ink so handles stay visible.
- Do not stroke the clipping shape into the plot SVG. It is a parameter, not artwork.

## 8. Coordinate system considerations

Store the shape in **machine millimetres**, origin at the machine home, y down. That is the space of `ClipRect`, `widget_to_mm`, the printable area, and the emitted SVG.

| Transform | Effect on a machine-space shape |
| --- | --- |
| View zoom / pan | None, if positions are stored in mm via `widget_to_mm` / `mm_to_px`. Storing pixels would be wrong. |
| Artwork X/Y, scale, orientation | None. The artwork moves through the shape. The shape stays on the bed. This matches a physical mask. A document-space shape would scale and rotate with the art and would surprise anyone who then nudges placement. |
| Margins | The effective cut is `shape ∩ printable area` (Keep inside) or `printable area \ shape` (Remove inside). The stored shape is not rewritten when margins change. |
| Work-area / model change | The shape stays in millimetres. If the new printable area misses it, the clip is empty and the existing error is shown. The overlay can still draw the shape so the mismatch is visible. |
| Layer change | The shape stays. The new layer’s cached polylines are clipped to it. |

Drawing must use `_current_physical_layout` (zoom and pan included). The move tool already does this for deltas. A handler that used `_base_layout` while zoomed would place the shape in the wrong millimetres.

Constrain interactive drawing and resizing to the printable rectangle so the outline the user sees is the outline that cuts. If a stored shape later sticks out because margins grew, draw the overhang muted and cut only the intersection. Do not silently plot the overhang.

The shape is not a child of the page orientation. Orientation is applied to document points before the clip (`resolve_transform_rotation` uses the printable size). The shape is applied after placement. Rotating the page must not rotate the mask.

Preview `QPainter` clips and the widget’s device pixel ratio affect rasters only. The pixmap of clipped strokes is rebuilt when the polyline identity or the widget size changes (`_plot_pixmap_for`). A new clip result is a new tuple, so the raster updates. That is existing behaviour.

## 9. Performance considerations

Verified from slice 025 benchmarks (`docs` counterpart: `specs/025-preview-performance/benchmarks.md`), cached `position_and_clip_geometry` only:

| Fixture | Cached clip (one run, ms) |
| --- | ---: |
| simple | ~0 |
| 80 cubics | ~55–67 |
| 1k paths | ~520–580 |
| 10k paths | ~1.7–1.9 s |

Flattening dominates the cold load (about 3 s at 1k paths, about 10 s at 10k) and is already cached per layer. A shape edit must not flatten again.

**Assumption, not measured:** a circle test per segment is a small constant factor on top of Liang–Barsky’s four edge tests. A second pass over the same polylines can approach a doubling of clip time on dense files. It does not change the flatten cost, which remains the large term.

What keeps the UI responsive today, and should be kept:

- Clip runs on `QThreadPool` via `PreviewComputeService`.
- A generation counter drops stale results (`PreviewResultGate`).
- The 50 ms timer coalesces slider and drag updates.
- During the wait, the ghost follows the pointer and the previous ink is hidden (`set_clip_pending`).
- The shape outline is a handful of painter calls and can track the drag immediately, the same way the ghost tracks an artwork drag while the ink waits.

Do not clip on every mouse-move on the UI thread. Do not build a plot SVG or run `_validate_output_geometry` during the drag. Reserve emission and validation for plot, estimate, and tests, as the interactive path already does.

Plot preparation (`prepare_layer_plot_svg`) still flattens from scratch and does not read `LayerGeometryCache`. A shape parameter on `_clip_document_subpaths` covers both entries. Preview latency and plot latency stay independent, which is the current design.

No extra cache is needed beyond the flatten cache. Clipped polylines are cheap to drop. Caching them keyed by `(layer, transform, margins, shape)` would only help if the same parameters repeat; the worker already makes a repeat cheap relative to flatten.

## 10. Risks and limitations

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Preview path updated, plot path not | Two entry points call `_clip_document_subpaths`. A preview-only shape would plot the uncut file. | Thread the shape through `prepare_layer_plot_svg`, estimate, and multi-layer the way margins are threaded. One geometry function. |
| Remove inside forced through `clip_segment` | That function returns one span. The hole would be wrong. | Change the walker to a list of spans before shipping Remove inside. |
| Painter clip used as the feature | Pen would still cross the shape. | Overlay is decorative. The polylines are the feature. |
| Shape stored in pixels or document space | Zoom, scale, or rotate would move the cut relative to the bed. | Machine millimetres only. |
| Shape allowed to extend into the margin and then clipped differently than drawn | The outline and the cut disagree. | Constrain editing to the printable area; after margin changes, show overhang as inactive. |
| Axis-aligned assumption forgotten | A rotated rectangle cannot use `ClipRect`. | Phase 1 rectangles stay axis-aligned. |
| Tangent and tiny-radius noise | Extra tiny segments or a division by zero. | Model validation plus the existing 0.01 mm sanitize. |
| Dense files while dragging the shape | Clip can take seconds at 10k paths. | Existing worker. The outline stays live; ink catches up. |
| Project version bump | `read_project_file` rejects versions below `SUPPORTED_VERSION`. | Optional JSON key on version 1. Absent key means no shape. |
| Source SVG `clipPath` | Not handled by PlotPilot. Users may expect the file’s own mask to cut. | Out of scope. Document it if the feature ships. **Assumption** on svgelements behaviour, see section 2. |
| Several shapes, freeform, holes that are not convex | Segment span count is no longer 0, 1, or 2. | Defer. Revisit pyclipper only then. |
| No undo | A bad drag is gone unless the shape can be edited or deleted. | Handles plus Delete. Do not add `QUndoStack` only for this. |

Fill, text, images, and dash patterns stay out of scope. They are already outside the stroke flattener.

## 11. Recommended implementation architecture

Keep the current engine. Generalize the clip step, not the parser.

```text
ClipShape | None          machine mm, session scope, Qt-free
        │
        ▼
position_and_clip_geometry / prepare_positioned_plot_svg
        │
        ▼
_clip_document_subpaths
        1. orient, scale, translate          (unchanged)
        2. Liang–Barsky to printable rect    (unchanged, always on)
        3. shape pass, only if a shape is set
             Keep inside  → one span (rect: tighter ClipRect, or the same
                            intersection computed up front)
             Remove inside → list of spans
        4. _sanitize_polyline                (unchanged)
        ▼
ClippedLayerGeometry → preview polylines
emit_validated_plot_svg → plot, estimate, parity tests
```

Model (Qt-free), sketched only:

- `kind`: `rectangle` or `ellipse`
- `mode`: `keep_inside` or `remove_inside`
- Rectangle: `x_mm`, `y_mm`, `width_mm`, `height_mm` in machine space. A square is equal width and height, not a second kind.
- Ellipse: `cx_mm`, `cy_mm`, `rx_mm`, `ry_mm`. A circle is equal radii.
- `validate()` rejects non-finite or non-positive size.
- `None` means the pipeline is exactly today’s pipeline.

For Keep inside of an axis-aligned rectangle, step 3 can be folded into step 2 by intersecting the two rectangles and calling `clip_segment` once. That is the preferred first slice. Circle and Remove inside are a real step 3.

Layer scope: **one shape for the whole project, applied to every plotted layer**, including estimate and multi-layer jobs. The preview shows the current layer only, which is already how the window works. The shape is a region of the bed, like margins, so pen changes should not silently change the cut. Per-layer shapes would need a shape list, a layer id, and a way to see a shape that belongs to a layer you are not looking at. That is the complexity to avoid.

Non-destructive: source SVG bytes and `PreparedLayerGeometry.polylines` stay unchanged. The shape is data on `ProjectSession`. The preview’s black ink and the temp SVG for axicli are derived. Deleting the shape recomputes the margin-only clip.

The clipping shape is not emitted as a path. axicli receives the cut strokes only.

## 12. Proposed implementation slices

Each slice is independently shippable and leaves current files behaving as they do when no shape is set.

### Slice 1 — Rectangle, Keep inside, no UI

**Objective.** An optional axis-aligned rectangle in machine millimetres further clips placed polylines. With no rectangle, output is unchanged.

**Files / components.**

- New Qt-free model, for example `src/plotpilot/models/clip_shape.py`.
- `clip_document_polylines`, `prepare_positioned_plot_svg`, `_resolve_clip_rect` or the call site that builds `ClipRect` in `plot_viewport.py`. Intersect the user rectangle with the printable rectangle before `clip_segment`.
- `position_and_clip_geometry`, `compute_interactive_preview`, `prepare_layer_plot_svg`, `build_prepared_layer_preview`.
- Tests beside `tests/test_geometry_clipping.py` and `tests/test_positioned_plot.py`.

**Dependencies.** None. Liang–Barsky stays.

**Risks.** Forgetting to intersect with the printable area would let a user rectangle override the margins. Plot and preview callers must both receive the rectangle.

**Acceptance criteria.**

- No shape: existing clipping tests pass unchanged.
- A rectangle inside the printable area cuts segments on its edges and splits a path that exits and re-enters, same topology as today’s viewport tests.
- A rectangle that crosses the margin clips to the intersection only. No vertex fails `_validate_output_geometry`.
- A rectangle that misses the artwork yields the existing empty-intersection error.
- Preview polylines and `prepare_layer_plot_svg` output describe the same polylines for the same inputs.

**Complexity:** Low.

### Slice 2 — Draw, move, and delete that rectangle

**Objective.** The user draws the rectangle on the preview. The black ink and a later plot use it. Projects remember it.

**Files / components.**

- `PreviewWorkspace` tool strip and `LayerPreviewWidget` mouse and paint (`widget_to_mm`, printable-area clamp, overlay in a non-accent colour).
- `MainWindow` preview scheduling, plot start, estimate, multi-layer start: pass the shape next to `print_margins`.
- `ProjectSession`, `session_to_document`, `read_project_file` with an optional key. Do not bump `SUPPORTED_VERSION`.
- Widget tests in the style of the existing preview and main-window tests. No pixel snapshot required; assert the machine-mm shape and that plot preparation receives it.

**Dependencies.** Slice 1.

**Risks.** Left-drag currently moves artwork when the move tool is on (`_can_move_artwork`). The clip tool and the move tool must be mutually exclusive. Zoomed placement must use `_current_physical_layout`.

**Acceptance criteria.**

- Dragging on the printable area creates a rectangle in machine millimetres. Zoom and pan do not change those millimetres for the same paper point.
- Move and resize update the preview through the existing worker. The outline tracks the pointer without waiting for the clip.
- Delete clears the shape and restores the margin-only preview.
- Plot and pre-plot estimate use the same shape as the preview.
- An old `.plotpilot` file with no clipping key opens with no shape.
- The move tool, zoom, and middle-button pan still behave as they do today when the clip tool is off.
- While plotting, the clip tool is inert.

**Complexity:** Medium (UI wiring), geometry still Low.

### Slice 3 — Ellipse and circle, Keep inside

**Objective.** Keep inside a circle or an ellipse, after the printable clip.

**Files / components.**

- New function beside Liang–Barsky, for example `src/plotpilot/geometry/convex_clip.py`: line vs circle, ellipse via the unit-circle map, one inside span.
- `_clip_document_subpaths` calls it only when the shape is an ellipse. The rectangle path from slice 1 stays on `clip_segment`.
- Preview: ellipse drawing and handles. Shift constrains equal radii. Rectangle Shift constrains a square.
- Tests: horizontal chord through a circle, segment missing the circle, tangent, exit and re-enter, ellipse with unequal radii, circle overlapping the margin (no output point outside the printable rect).

**Dependencies.** Slices 1 and 2. Stdlib `math` only.

**Risks.** Tangent flicker and a zero radius. The unit-circle map must use the same y-down millimetres as the rest of the pipeline, with no extra y flip.

**Acceptance criteria.**

- A segment through a circle is trimmed to the chord inside the circle.
- A closed path that leaves the circle splits, with no bridge across the outside.
- Equal radii stay a circle under the isotropic preview scale.
- Points remain inside the printable rectangle.
- Rectangle Keep inside behaviour from slice 1 is unchanged.

**Complexity:** Medium.

### Slice 4 — Remove inside

**Objective.** Remove the inside of the current rectangle or ellipse. The rest of the printable area stays.

**Files / components.**

- Walker change in `_clip_document_subpaths`: a segment may append two disjoint pieces and flush between them.
- Rectangle hole and ellipse hole share that walker. Rectangle Keep inside can remain the single `ClipRect` fast path.
- Mode control on the overlay, visible only when a shape exists.
- Tests: a line across a hole becomes two segments; a segment fully inside the hole disappears; a segment fully outside the hole and inside the printable area is kept; margins still win.

**Dependencies.** Slice 1 for rectangles. Slice 3 for ellipses. The walker change can ship for rectangles before ellipses exist.

**Risks.** This is the first change to the one-span assumption. A mistake here regresses ordinary margin clipping if the new walker is used when no shape is set. Keep the no-shape path on today’s `plot_segment`.

**Acceptance criteria.**

- No shape: current tests pass on the old path.
- Remove inside a rectangle centred on a line produces two polylines and no stroke across the hole.
- Remove inside a circle does the same for a chord.
- Output still validates inside the printable rectangle.
- Switching mode updates preview and plot together.

**Complexity:** Medium.

### Later, not in the first delivery

- Polygon and freeform: a span list or a polygon clipper. Dependency decision belongs in that slice, not now.
- Several shapes: only after one shape is solid. Union and intersection of convex shapes are not convex.
- Numeric fields for exact millimetres.
- Rotated rectangles as convex polygons.
- Per-layer shapes.
- Undo stack.

## 13. Estimated complexity

| Piece | Complexity |
| --- | --- |
| Rectangle / square, Keep inside, geometry only | **Low** |
| Preview drawing, session, plot wiring | **Medium** |
| Circle / ellipse, Keep inside | **Medium** |
| Remove inside (walker spans) | **Medium** |
| Phase 1 together (slices 1–4) | **Medium** |
| Polygon, freeform, or multiple shapes | **High** |

## Recommendation

**Yes. The feature fits the existing clipping architecture.** Flattened polylines, the subpath splitter, the printable-area safety clip, the worker, and the polyline preview are the right base. Liang–Barsky alone is not a general shape clipper. It is the right tool for the margin rectangle and for Keep inside an axis-aligned user rectangle.

**Simplest technical approach:** one optional `ClipShape` in machine millimetres, applied after the printable Liang–Barsky pass, inside `_clip_document_subpaths`, and passed into preview, plot, estimate, and multi-layer the way `print_margins` is. No new dependency. No SVG mask. No second engine.

**Simplest UX:** one Clip tool on the existing preview strip, Rectangle or Ellipse, Shift for square or circle, Keep inside or Remove inside, drag to edit, Delete to remove. Live preview. No Apply button and no new panel.

**Implement first:** slice 1, then slice 2. A rectangle that only affects a test is not the feature; a rectangle the user can draw, that the preview and the plot both cut, proves the coordinate system, the non-destructive session, and the margin intersection before any new intersection math. Ellipse next. Remove inside after the one-span walker is no longer the only path.
