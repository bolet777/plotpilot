# Research: 017 SVG golden baseline

Source: `docs/AUDIT-2026-09-30.md` on `main` at `5f507b4`. This slice records behavior. It does not choose a new geometry engine (O1 / Q2 stay open).

## Baseline before this slice

| Check | Result |
|---|---|
| Branch | `main` = `origin/main` = `5f507b4` |
| Working tree | Audit doc untracked; `docs/README.md` linked it |
| Fast suite | `test_synthetic_document_layer` failed immediately: no warning modal (B11). One later run also hit a svgelements bus error inside `test_plot_progress.py` during GC; not reproduced as an assertion failure. |
| Ruff | `I001` and format in `tests/test_square_pipeline_regression.py` |

B11 cause: plot preparation is asynchronous. The viewport error arrives as `PlotPhase.FAILED` and `MultiLayerJobState.ERROR`, not `QMessageBox.warning`.

## Oracle boundary

`prepare_positioned_plot_svg` is the system under test. The harness in `tests/golden_oracle.py` may call it, then parse the emitted SVG with the standard library. It must not import `_clip_svg_geometry`, `_estimate_segment_length_rendered`, `_coordinates_are_viewport_pixels`, or `_read_viewbox_user`.

Prepared output is `M`/`L` only, in millimeters, one `<path>` per polyline (`_emit_svg`).

## Hand calculations that disagree with a loose audit note

### B2

Path: `M 70 50 A 20 20 0 1 1 69.999 50.02` on a 100 mm page.

Endpoint-to-center conversion (radii 20, large-arc 1, sweep 1):

- center ≈ (89.9745, 51.0088)
- sweep ≈ 359.94°
- unclipped bbox ≈ (69.975, 31.009, 109.975, 71.009)

The 100 mm viewport clips x at 100, so the expected bbox is about `[69.975, 31.009, 100.0, 71.009]` with many samples. The audit box (30..70, 30..70) is the sweep-flag 0 center. Encoding that box would reject a correct fix.

Current output: 3 points, `(70, 50) → (100, 51.5075) → (69.999, 50.02)`.

### B3

Without `viewBox`, 1 user unit = 1 CSS px = 25.4/96 mm.

Rect `x=10 y=10 width=100 height=50` → bbox `(2.645833, 2.645833, 29.104167, 15.875)`.

Current output treats those numbers as millimeters: `(10, 10, 110, 60)`.

Adding `<line x2="1100">` makes the current heuristic switch to pixels, so that file already matches CSS px. The invariant test xfails because the two files disagree.

### B10

`_VIEWBOX_RE` takes the first `viewBox` in the text. The audit's marker `0 0 10 10` still plots the rect at CSS px (coincidence: the pixel heuristic turns on). Marker `0 0 200 200` scales the same rect to `(5, 5, 30, 30)` instead of CSS px. That second file is the xfail.

### B9

Plot mapping for `xMidYMid meet` on a 200×100 mm page and a square viewBox is bbox `(50, 0, 150, 100)`. A viewport of exactly 100 mm tall sits on the bottom edge and the current clipper drops a corner. The golden viewport is 200×150 mm so the test locks the mapping, not clipping. B1 covers clipping.

### B8 / Q1

Fill-only policy is undecided. Fixture only.

## Out of scope

B1 clipping continuity, B2 arc length, B3/B5/B10 unit and viewBox parsing, B4 preview DPI, B6 styles, B7 nested layers, B12 orientation, B13 degenerate points. Task 2 is B1/B2/B13.
