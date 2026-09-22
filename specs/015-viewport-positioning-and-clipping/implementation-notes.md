# Implementation notes: 015 viewport positioning and clipping

**Status**: Merged on `main` via PR **#14** (`015-viewport-positioning-and-clipping`).  
**Convergence**: PR **#15** (Qt test helpers, fast suite) — merge `b3e70d72a2ac6434c78f18263a8ee9fe3181b37f` and follow-up coverage on `fix/015-convergence`.

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

**Fast suite** (CI gate):

```bash
./scripts/test_fast.sh
# uv run pytest -m "not slow and not hardware" -q
```

Typical runtime: **~2–3 s** (270+ tests, hardware/slow deselected).

**Full non-hardware suite**:

```bash
uv run pytest -m "not hardware" -q
```

Typical runtime: **~3–5 s**.

**Qt helpers** (`tests/qt_helpers.py`): `wait_until`, `wait_for_plot_started`, `wait_for_fake_plot_invocation`, etc. — use instead of sleeps in plotter integration tests.

**015 acceptance coverage** (convergence pass):

- Preview drag → mm: `tests/test_preview_widget.py::test_drag_updates_artwork_transform_in_mm`
- Multi-layer transform snapshot: `tests/test_multi_layer_plot_service.py::test_artwork_transform_snapshot_persists_for_all_layers`
- Clipped temp SVG + settings snapshot (`-G1` via `PlotSettings.path_reordering`): `tests/test_plotter_service_settings.py`
- Settings snapshot during in-flight plot: `test_changing_settings_during_plot_does_not_alter_snapshot` (waits on `plot_settings_used`)
- Geometry / safety: `tests/test_geometry_clipping.py`, `tests/test_positioned_plot.py`, `tests/test_plot_bounds.py`, existing safe-stop and multi-layer tests

**Ruff**: `uv run ruff check src tests` and `uv run ruff format --check src tests`.

## Known limitations

- Clipping targets **stroked** vector geometry via svgelements; fill-only / text / images not guaranteed safe.
- Default (CLI): clip rectangle = user-selected A3/A4 fallback, labeled as not hardware-verified.
- Preview uses painter clip for dimming; authoritative geometry is plot preparation only.
