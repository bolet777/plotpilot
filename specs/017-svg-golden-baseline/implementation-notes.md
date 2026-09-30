# Implementation notes: 017 SVG golden baseline

**Status**: Ready for review. Not merged.  
**Branch**: `017-svg-golden-baseline`

## What changed

Test and documentation only, plus the audit report that the docs index already linked.

- B11 follows the async failure path (`PlotPhase.FAILED`, job `ERROR`, no warning modal).
- Golden expectations are JSON millimeters. The oracle parses prepared `M`/`L` paths and does not reuse the clipper, flattener, or unit heuristic.
- XFAIL reasons carry audit ids. Expected geometry is the correct result.

## What did not change

`geometry/plot_viewport.py`, `geometry/liang_barsky.py`, `svg/preview.py`, `svg/layers.py`, and preview DPI. B1, B2, B3, B4, B5, B6, B7, B8, B9, B10, B12, and B13 are not fixed here.

## Oracle notes for the next slice

- **B2**: do not "fix" the test toward the audit's (30..70) box. That box is the other arc center. This path's center is about (89.97, 51.01). After a correct flatten, points should lie near that circle (or on the 100 mm viewport edge) and there should be dozens of points, not 3.
- **B8**: leave `policy: pending` until Q1 is decided.
- **B10**: `groups/b10_marker_viewbox_10` passes today by coincidence. `groups/b10_marker_viewbox_200` is the case that shows the nested viewBox changing scale.
- Removing an `xfail` mark is in scope for the slice that fixes that bug. Editing expected JSON to match broken output is not.

## Commands

```bash
uv run pytest tests/test_golden_svg.py -q
./scripts/test_fast.sh
uv run pytest -m "not hardware" -q
uv run ruff check src tests
uv run ruff format --check src tests
```

No `-m hardware`. No physical AxiDraw plot.
