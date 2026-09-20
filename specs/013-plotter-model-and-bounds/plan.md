# Implementation Plan: Plotter model and bounds

**Branch**: `013-plotter-model-and-bounds` | **Spec**: [spec.md](./spec.md)

## Summary

Add `PlotterModelInfo`, `PlotBoundsCheck`, and `check_plot_bounds()` (Qt-free). Wire into `PlotterService.start_plot_layer`, `MultiLayerPlotService.start_job`, and `MainWindow` status label. Reuse `validate_plot_svg_dimensions`.

## Files

| Path | Role |
|------|------|
| `models/plotter_model.py` | Verified model table |
| `models/plot_bounds.py` | Status enum + result dataclass |
| `services/bounds_service.py` | `check_plot_bounds` |
| `svg/plot_dimensions.py` | `PhysicalSize` helper |
| `services/plotter_service.py` | Block on OUT_OF_BOUNDS |
| `services/multi_layer_plot_service.py` | Pre-job bounds |
| `ui/main_window.py` | Bounds label + control gating |
| `tests/test_plotter_model.py`, `test_plot_bounds.py`, main_window tests |

## Fit logic

Match axicli default auto-rotate: if height > width, compare (height, width) to (model X, model Y).
