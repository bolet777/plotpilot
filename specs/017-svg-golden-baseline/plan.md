# Implementation Plan: SVG golden baseline

**Branch**: `017-svg-golden-baseline` | **Spec**: [spec.md](./spec.md)

## Summary

Repair test hygiene (B11, ruff), add a test-only golden harness, and commit hand-calculated millimeter expectations. Production geometry stays as it is. Confirmed bugs are `xfail`.

## Files

| Path | Role |
|------|------|
| `tests/golden_oracle.py` | Load fixture, prepare, parse `M`/`L`, compare |
| `tests/test_golden_svg.py` | PASS / XFAIL cases with audit ids |
| `tests/fixtures/golden/` | SVG + expected JSON |
| `tests/test_main_window_multi_layer.py` | B11 waits for FAILED / ERROR |
| `tests/test_square_pipeline_regression.py` | T7 restated as CSS px; ruff |
| `README.md`, `specs/README.md`, `docs/ARCHITECTURE.md` | D10 slice list and `geometry/` |

## Comparison

1. Read `<case>.expected.json`.
2. Load the SVG (or `svg` override) and, when requested, isolate a named layer with the current preview/plot isolation path.
3. Call `prepare_positioned_plot_svg` with the JSON viewport and transform.
4. Parse output paths.
5. Compare bbox and/or polylines within `tolerance_mm` (default 0.02).
6. Optional `min_points` and `circle_mm` for arcs whose exact samples depend on flattening.

`policy: pending` skips steps 2–6.

## XFAIL map

| Test | Audit | Correct result | Current result |
|------|-------|----------------|----------------|
| square exit/reenter | B1 | two open edges, no diagonal | one polyline through `(75, 100)` |
| scale-2 square | B1 | `(20,20)→(100,20)` and `(20,100)→(20,20)` | through `(60, 100)` |
| near-complete arc | B2 | circle around (89.97, 51.01), ≥ 30 points | 3 points, bbox y ≈ 50..51.5 |
| viewBox-less rect | B3 | CSS px bbox ≈ (2.65, 2.65, 29.10, 15.88) | (10, 10, 110, 60) mm |
| scale invariant | B3 | same rect bbox with or without the long line | small file stays in mm |
| isolated px layer | B5 | 100 px = 26.458333 mm | isolated bbox 100 mm |
| isolated CSS class | B6 | Layer 1 rect 10..60 mm | `No artwork intersects` |
| nested child layer | B7 | square at (40, 40, 50, 50) | `No artwork intersects` |
| marker viewBox 200 | B10 | same CSS px rect as the 10×10 marker | bbox (5, 5, 30, 30) |

## Non-goals

Do not change `src/plotpilot/geometry/`, `svg/preview.py`, or `svg/layers.py` to make an xfail pass.
