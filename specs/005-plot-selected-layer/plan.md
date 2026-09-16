# Implementation Plan: Plot Selected Layer

**Branch**: `005-plot-selected-layer`

## Summary

Reuse `build_layer_preview_svg` for plot input via `plot_service`. Validate dimensions in
`svg/plot_dimensions.py`. Extend `AxiDrawCliBackend.plot_svg` with `Popen` + SIGINT cancel.
`PlotterService.start_plot_layer` writes tempfile and tracks `PlotState`. Main window adds Plot /
Stop and confirmation dialog.
