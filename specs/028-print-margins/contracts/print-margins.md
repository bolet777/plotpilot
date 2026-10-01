# Contract: Print margins

## Geometry

`clip_document_polylines` and `prepare_positioned_plot_svg` accept optional machine-space bounds:

- `clip_x_min_mm` (default 0)
- `clip_y_min_mm` (default 0)
- `clip_x_max_mm` (default viewport width)
- `clip_y_max_mm` (default viewport height)

`prepare_layer_plot_svg`, preview preparation, estimate, and plot accept `print_margins: PrintMargins | None`. `None` means `PrintMargins()` (10 / 10).

Emitted plot SVG keeps the machine viewport size. Every `M`/`L` coordinate satisfies:

```text
printable_x_min - 0.01 <= x <= printable_x_max + 0.01
printable_y_min - 0.01 <= y <= printable_y_max + 0.01
```

and the same inequality against the machine work area. Failure cancels preparation.

## UI

Main window, next to the plot-area line:

- Horizontal `QDoubleSpinBox`, suffix ` mm`, range 0 to the current maximum, 1 decimal, step 1.
- Vertical `QDoubleSpinBox`, same.
- Informational printable size, updated immediately.

Signals update settings, mark a loaded document dirty, clear the stale estimate text, and schedule a cached preview refresh. They do not invalidate flattened geometry.

## QSettings

| Key | Type | Default when missing or invalid |
|-----|------|----------------------------------|
| `print/margin_horizontal_mm` | float | 10.0 |
| `print/margin_vertical_mm` | float | 10.0 |

Written only when no project session is active.

## Project JSON

Optional `print.margin_horizontal_mm` and `print.margin_vertical_mm` on format version 1.

Load errors (friendly `ProjectFileError`, project not applied):

- `print` is not an object
- a margin is not a finite number
- a margin is negative
- the pair does not leave 0.1 mm of printable width and height on the project's resolved work area

## Preview overlay

`set_work_area_overlay` accepts an optional `PrintableArea`. When set, paint draws:

1. Existing red dashed work-area rectangle.
2. Solid inner rectangle in the palette text color, inset to the printable origin and size.

Prepared polylines are already clipped; the widget does not shift them.
