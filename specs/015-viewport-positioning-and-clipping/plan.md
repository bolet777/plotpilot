# Implementation Plan: Viewport positioning and clipping

**Branch**: `015-viewport-positioning-and-clipping` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Summary

Add Qt-free `ArtworkTransform`, `prepare_positioned_plot_svg()` (svgelements + Liang–Barsky + validator), wire into plot/estimate/multi-layer snapshots, extend preview with transform controls and painter clip/dim.

## Files

| Path | Role |
|------|------|
| `models/artwork_transform.py` | Transform dataclass + validation |
| `geometry/liang_barsky.py` | Segment clip |
| `geometry/plot_viewport.py` | Extract, transform, flatten, clip, emit SVG |
| `services/positioned_plot_service.py` | Orchestration + empty check |
| `services/plotter_service.py` | Use prepared SVG; snapshot transform |
| `services/multi_layer_plot_service.py` | Snapshot transform |
| `services/bounds_service.py` | Do not block OUT_OF_BOUNDS when clipping active |
| `ui/preview_widget.py` | Transform render, drag, clip dim |
| `ui/main_window.py` | X/Y/scale controls, status |
| `tests/test_geometry_clipping.py`, `test_artwork_transform.py`, `test_positioned_plot.py`, updates to preview/main_window tests |

## Dependencies

- `svgelements` (MIT) — SVG path normalization

## Clip rectangle resolution

```python
resolve_plot_viewport_mm(plot_settings, fallback: FallbackWorkArea) -> (w, h, label, verified: bool)
```

- `model is not None` → `PlotterModelInfo`
- else → fallback A3/A4 mm, `verified=False`
