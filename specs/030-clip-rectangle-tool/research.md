# Research: Interactive keep-inside rectangle

## 1. Where does the rectangle live during a drag?

**Decision**: `LayerPreviewWidget` stores `ClipRectangle | None` and paints the overlay on the UI thread. Each change emits a signal. `MainWindow` schedules the existing 50 ms preview job and passes `keep_inside` into `compute_interactive_preview`. The worker clips. The widget does not call the clipper.

**Rationale**: Slice 025 already hides stale ink and keeps the ghost live while a clip runs. The outline has to follow the pointer without waiting for that job.

**Alternatives considered**: Clip inside `mouseMoveEvent`. Rejected: that would put the 1k-path clip back on the UI thread. A painter clip of the ink. Rejected: the plot file would stay uncut.

## 2. How do zoom and the artwork transform interact?

**Decision**: Store machine millimetres only. Drags use `widget_to_mm`, which already divides by the zoomed `mm_to_px`. The rectangle is not a child of `ArtworkTransform`.

**Rationale**: `widget_to_mm` and the move-tool delta already map a zoomed, panned view into machine millimetres. The bed mask must stay put when the drawing is scaled or rotated.

## 3. How is the rectangle kept inside the margins?

**Decision**: Pointer positions and the resulting rectangle are clamped to `PrintableArea` before `ClipRectangle` is stored. Slice 1 still intersects with the printable window, so a stored rectangle cannot plot in the margin.

**Rationale**: The outline the user sees should be the outline that cuts. The geometry intersection remains the safety net.

## 4. Project file

**Decision**: Optional `clipping.rectangle` with `x_mm`, `y_mm`, `width_mm`, `height_mm` on version 1. Omit the object when there is no rectangle. Missing or null loads as no rectangle. Invalid numbers raise `ProjectFileError`. Do not change `SUPPORTED_VERSION`.

**Rationale**: `read_project_file` rejects versions below 1. An optional key keeps old files valid.

## 5. Plot path

**Decision**: Add `keep_inside: ClipRectangle | None = None` to `PlotterService.start_plot_layer`, `request_pre_plot_estimate`, `MultiLayerPlotService.start_job`, and `MultiLayerPlotJob`. Default `None` preserves every current caller.

**Rationale**: Slice 1 already taught `prepare_layer_plot_svg` the argument. These call sites were intentionally left unwired until a rectangle existed.
