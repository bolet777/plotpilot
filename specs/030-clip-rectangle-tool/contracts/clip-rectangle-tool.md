# Contract: Interactive keep-inside rectangle

## Preview

`LayerPreviewWidget` exposes `clip_rectangle` and `clip_tool_active`.

- Clip tool on: left-drag on the printable area draws. Shift squares the drag. Inside the rectangle moves it. A corner resizes it. Delete and Backspace clear it when the preview has focus.
- Clip tool off: left-drag does not edit the rectangle. The overlay still draws if a rectangle exists.
- Move tool and clip tool: turning one on turns the other off.
- `widget_to_mm` remains the pixel-to-machine mapping, including zoom and pan.
- The overlay uses `ThemeColors.clip_outline`, not `printable_outline`.
- The widget emits `clip_rectangle_changed` and does not clip paths itself.

## Preparation and plot

`MainWindow` passes `preview.clip_rectangle` as `keep_inside` to:

- `compute_interactive_preview`
- `PlotterService.start_plot_layer`
- `PlotterService.request_pre_plot_estimate`
- `MultiLayerPlotService.start_job`

`None` keeps the Slice 1 default: printable area only.

The plot SVG is still only cut `M`/`L` strokes. The rectangle is not an element in that file.

## Project JSON

Format version stays 1.

- No `clipping` key, or `clipping` null: no rectangle.
- `clipping.rectangle` with four finite numbers and positive width and height: that rectangle.
- Any other `clipping` value: `ProjectFileError`, project not applied.
