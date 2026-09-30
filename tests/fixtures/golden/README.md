# Golden SVG fixtures

Hand-calculated plot geometry for the preparation pipeline. These files are the
oracle for later geometry fixes. They do not change production behavior.

## Purpose

Each case is an input SVG plus the physical millimeters that preparation should
emit. A failing case that describes a confirmed bug is marked `xfail` in
`tests/test_golden_svg.py` with the audit id (`B1`, `B2`, …). A passing case
locks behavior the audit already verified.

## Layout

```text
tests/fixtures/golden/<category>/<case>.svg
tests/fixtures/golden/<category>/<case>.expected.json
```

Categories in this tranche: `square/`, `viewbox/`, `transforms/`, `groups/`,
`layers/`, `styles/`, `paths/`, `clipping/`.

## Expected JSON

Geometric cases use millimeters, independent of PlotPilot's internal units:

```json
{
  "audit_ids": ["B1"],
  "description": "Why this case exists",
  "viewport_mm": [100.0, 100.0],
  "tolerance_mm": 0.02,
  "bbox_mm": [50.0, 50.0, 100.0, 100.0],
  "polylines_mm": [
    [[50.0, 50.0], [100.0, 50.0]]
  ]
}
```

Optional fields:

- `transform`: `{ "x_mm", "y_mm", "scale" }` passed to preparation (default identity)
- `preparations`: `document` or `isolated_layer` (with `layer_name`)
- `svg`: sibling SVG filename when several expectations share one file
- `min_points`: lower bound when flattening makes an exact polyline unstable
- `circle_mm`: `{ "cx", "cy", "r", "radial_tolerance_mm" }` for arcs
- `policy`: `"pending"` means the fixture is recorded and plot output is not asserted

## Tolerance

Default `tolerance_mm` is **0.02**. Arc bounds may use a wider tolerance because
flattening does not hit every extremum. Do not loosen a tolerance to hide a
wrong shape.

## PASS vs XFAIL

- **PASS**: current preparation already matches the expected millimeters.
- **XFAIL**: current preparation does not. The JSON still holds the correct
  geometry. The pytest reason names the audit id (`B1: …`). When the bug is
  fixed the test becomes XPASS and the mark should be removed.
- **Pending policy** (`B8` / `Q1`): the SVG is stored, and the test checks only
  that no plot assertion was chosen.

## Audit ids

Use the ids from `docs/AUDIT-2026-09-30.md` exactly (`B1`, `B3`, `T7`, …).
Put them in `audit_ids` and in the `xfail` reason.

## Expected values

Calculate bbox and polyline coordinates by hand (SVG units, viewBox, CSS px =
25.4/96 mm, transforms). Do not generate expected JSON by calling
`prepare_positioned_plot_svg` or any other PlotPilot geometry function.
