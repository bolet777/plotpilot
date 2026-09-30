# Research: Core geometry fixes

## B1 root cause

In `_clip_svg_geometry()` → `plot_segment()`, when `pen_xy` (the last clipped endpoint) differed from the true source segment start, the code replaced `(ax0, ay0)` with `pen_xy` before Liang–Barsky clipping.

That rewrote input geometry: after clipping the top edge of a square, the next source segment (vertical left edge starting at the true corner) was forced to start at the previous clip exit on the top boundary, producing an invented diagonal to the next visible point.

**Incorrect output (B1 golden)**: one polyline `(50,50)→(100,50)→(75,100)→(50,50)`.

**Correct output**: two polylines `(50,50)→(100,50)` and `(50,100)→(50,50)`.

## B2 root cause

`_estimate_segment_length_rendered()` summed chord lengths through control points. For `Arc` segments with nearly coincident endpoints, that estimate collapsed toward zero, so flattening used ~2 steps (~3 points) instead of sampling the ~2πr arc.

svgelements exposes `Arc.length()` with correct elliptical arc length; using it for `Arc` instances restores adaptive sampling at `CURVE_FLATNESS_MM` (0.05 mm).

## B13 root cause

Move/line combinations and clipping could emit consecutive identical coordinates or single-point polylines. Cleanup is applied at flush time via `_sanitize_polyline()`.

## Boundary float noise

viewBox SVGs can yield segment coordinates like `100.00000000000004` mm, which Liang–Barsky rejects as outside `x_max=100`. `_snap_point_to_clip()` snaps near-boundary values within `COORD_TOLERANCE_MM` before clipping.
