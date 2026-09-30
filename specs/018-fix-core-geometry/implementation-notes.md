# Implementation notes: 018-fix-core-geometry

## Production changes

**File**: `src/plotpilot/geometry/plot_viewport.py`

| Change | Purpose |
|--------|---------|
| Removed `pen_xy` rewrite of segment starts | B1 — preserve immutable source geometry |
| Continuity via `_points_near(current[-1], clipped_start)` | Output grouping only |
| `_snap_point_to_clip` before Liang–Barsky | Boundary float noise (100.0000…04 mm) |
| `Arc.length()` in `_estimate_segment_length_rendered` | B2 — correct flatten step count |
| `_sanitize_polyline` on flush | B13 — dedupe consecutive points, drop `<2` point paths |
| Skip zero-length clipped segments | Avoid emitting degenerate spans |

## B13 cleanup rule

Within tolerance `COORD_TOLERANCE_MM` (0.01 mm):

- Remove consecutive duplicate vertices.
- Do not emit polylines with fewer than two distinct vertices.
- Do not merge separate paths, simplify curves, or remove short but non-degenerate segments.

## Golden status after task

| Test | Before | After |
|------|--------|-------|
| B1 square / scaled | XFAIL | PASS |
| B2 near-complete arc | XFAIL | PASS |
| B3, B5, B6, B7, B10 | XFAIL | XFAIL (unchanged) |

B2 post-fix: ~344 flattened points, bbox `(69.97, 31.01, 100.0, 71.01)` mm.

## Tests added

- `tests/test_geometry_clipping.py` — clipping topology A–J + B13
- `tests/test_geometry_arcs.py` — arc flattening matrix
