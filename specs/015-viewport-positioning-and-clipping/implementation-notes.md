# Implementation notes: 015 viewport positioning and clipping

**Branch**: `015-viewport-positioning-and-clipping`  
**Status**: Core delivered on branch; merge to `main` pending PR and full CI pass.

## Delivered

| Area | Location | Notes |
|------|----------|--------|
| Safety research | [research.md](./research.md) | axicli 3.9.6 `boundsclip`, Default/CLI policy, svgelements (MIT), 0.05 mm flatten |
| Transform model | `models/artwork_transform.py` | `x_mm`, `y_mm`, uniform `scale`; validation |
| Clipping engine | `geometry/plot_viewport.py`, `geometry/liang_barsky.py` | Transform → flatten → Liang–Barsky → machine-sized SVG → coordinate validator |
| Plot pipeline | `services/positioned_plot_service.py`, `plotter_service.py` | Isolated layer → clip → temp SVG → axicli plot + estimate |
| Multi-layer | `multi_layer_job.py`, `multi_layer_plot_service.py` | Snapshots `artwork_transform` + fallback work area for all layers |
| Bounds policy | `bounds_service.py`, `plot_bounds.py` | Page `OUT_OF_BOUNDS` is informational; only `INVALID_DIMENSIONS` blocks UI |
| Viewport resolution | `preview_work_area.py` | `resolve_plot_viewport()` — explicit model or user A3/A4 fallback |
| Preview UI | `preview_widget.py`, `main_window.py` | Fixed red viewport; drag + X/Y/scale + Reset; dim outside / bright inside |
| Dependency | `pyproject.toml` | `svgelements` |

**Defense in depth**: transform validation → geometric clip → output validator → axicli bounds clip (unchanged).

**Original SVG**: `SvgDocument.raw_text` and disk file never modified.

## Intentionally omitted (spec scope)

- Rotation, skew, per-layer transform, Fit control, project persistence of transform
- Proactive UI disable when clip result is empty (block at plot start with message only)
- Hardware validation (manual test plan in slice brief)

## Tests

**Targeted (fast, recommended during this slice)**:

```bash
uv run pytest tests/test_geometry_clipping.py tests/test_artwork_transform.py \
  tests/test_positioned_plot.py tests/test_plot_bounds.py tests/test_preview_work_area.py -q
```

**Updated for clipping policy**: `tests/test_plot_bounds.py`, `tests/test_main_window_plot_bounds.py`.

**Not yet expanded** to the full checklist in the slice brief (sections 25–26): exhaustive curve/shape matrix, multi-layer transform snapshot tests, preview drag mm tests, argv inspection for `-G1` on clipped file.

**Full suite** (`uv run pytest -m "not slow" -q`): not used as merge gate for this commit — a full run was observed to hang or run very long (Qt/plotter integration waits). Re-run locally before merge; fix any deadlock separately.

**Ruff**: run `uv run ruff check src tests` and `uv run ruff format --check src tests` before merge.

## Known limitations

- Clipping targets **stroked** vector geometry via svgelements; fill-only / text / images not guaranteed safe.
- Default (CLI): clip rectangle = user-selected A3/A4 fallback, labeled as not hardware-verified.
- Preview uses painter clip for dimming; authoritative geometry is plot preparation only.

## Follow-up before closing slice on main

1. Stabilize or bisect full `pytest -m "not slow"` runtime/hang.
2. Add remaining application tests from spec §25–26 where high value.
3. PR, CI green, merge, delete branch.
