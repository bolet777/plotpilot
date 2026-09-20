# Implementation Plan: Plot progress

**Branch**: `014-plot-progress` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Strategy

Strategy B: `axicli -v -T` preview before/during plot start; elapsed / estimated duration with explicit "estimated" label.

## Structure

| Area | Change |
|------|--------|
| `models/plot_progress.py` | Pure progress math + formatting |
| `models/plot_estimate.py` | Parse preview output |
| `models/plot_settings.py` | `build_axicli_preview_argv`, shared motion flags |
| `plotter/axidraw.py` | `estimate_plot_svg` |
| `services/plotter_service.py` | Timer, estimate async, `plot_progress_changed` |
| `ui/main_window.py` | Compact progress bar + labels |
| `ui/plot_progress_labels.py` | Headline/timing formatters |
| `services/multi_layer_plot_service.py` | Pass layer index/count to plotter |
