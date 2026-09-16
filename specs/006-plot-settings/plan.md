# Implementation Plan: Plot Settings

**Branch**: `006-plot-settings` | **Spec**: [spec.md](./spec.md)

## Summary

`PlotSettings` dataclass with optional fields; `build_axicli_plot_argv()` in plotter layer;
`SettingsService` for QSettings; `PlotSettingsWidget` in main window; `PlotterService.start_plot_layer`
captures snapshot from settings service.

## Structure

- `models/plot_settings.py` — data, validation, argv builder, model labels
- `services/settings_service.py` — load/save/reset
- `plotter/axidraw.py` — `plot_svg(..., settings=...)`
- `ui/plot_settings_widget.py` — compact controls
- Tests with isolated QSettings org/app names
