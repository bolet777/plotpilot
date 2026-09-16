# Plan: Safe Stop and Home

## Design

- Add `PlotPhase.STOPPING` for cleanup (messages: Stopping plot…, Raising pen…, Returning home…, Motors disabled).
- `PlotterService.request_safe_stop()` coalesces repeated calls; blocks new plots while stopping.
- Worker thread runs: wait for plot exit → `pen_up` → `walk_home` → `disable_xy` with failure gates from research.md.
- Emit `safe_stop_finished(SafeStopResult)` for multi-layer job finalization.
- `AxiDrawCliBackend`: `walk_home()`, `disable_xy()` via `_manual`.
- `FakePlotterBackend`: record ordered `manual_sequence` for tests.
- `MultiLayerPlotService.stop_job()` delegates to `request_safe_stop()`; finalize job on `safe_stop_finished`.
- `MainWindow`: call `request_safe_stop()`; show STOPPING messages even during active multi-layer job.

## Tests

New `tests/test_safe_stop.py` covering the 15 cases from the feature brief.
