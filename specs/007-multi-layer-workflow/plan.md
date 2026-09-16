# Implementation Plan: Multi-Layer Plot Workflow

**Branch**: `007-multi-layer-workflow` | **Spec**: [spec.md](./spec.md)

## Summary

`MultiLayerPlotJob` model + `MultiLayerPlotService` orchestrates sequential
`PlotterService.start_plot_layer` calls, pen-up between layers, and job lifecycle signals.
MainWindow adds checkboxes, multi plot button, confirmation, and pen-change panel.

## Structure

- `models/multi_layer_job.py` — job state enum and snapshots
- `services/multi_layer_plot_service.py` — state machine, pen_change_required signal
- `ui/main_window.py` — layer checkboxes, controls, dialogs
- `tests/test_multi_layer_*.py` — service + UI coverage with FakePlotterBackend
