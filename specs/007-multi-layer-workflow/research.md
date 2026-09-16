# Research: pen-up after plot & multi-layer orchestration

## Pen state after successful `axicli -m plot`

**CLI documentation** (https://axidraw.com/doc/cli_api/) states that `raise_pen` manual mode
“will only raise the pen if it was in the down state or an indeterminate state” and does not
move XY. Plot mode docs describe pause/stop behavior but do not explicitly guarantee final pen-up
in every edge case.

**Observed / industry behavior**: AxiDraw plot mode normally finishes with the pen raised after the
last segment (same as Inkscape AxiDraw extension). PlotPilot already treats a successful plot exit
as a completed job without an extra raise step for single-layer plots.

**PlotPilot policy for slice 007**:

1. After each **successful** intermediate layer in a multi-layer job, call `raise_pen` via the
   existing `PlotterService.pen_up()` → backend manual `raise_pen` before entering
   `WAITING_FOR_PEN_CHANGE`.
2. No XY movement is requested for pen change (manual raise only).
3. If `pen_up` fails (disconnect/error), the multi-layer job enters `ERROR` with a clear message;
   the user must not be prompted to swap pens while the pen state is unknown.

## Reuse of single-layer plotting

Each layer continues to use isolated temp SVG + `PlotterService.start_plot_layer` with settings
snapshotted at **job** start (not per layer).

## Future automated pen changer

Backend emits `pen_change_required(next_layer_snapshot)`; UI shows Continue. A future device could
subscribe to the same event and call `continue_after_pen_change()` without dialog changes in the
service.
