# Data model: Rectangle keep-inside clip

## ClipRectangle

Qt-free value in `src/plotpilot/models/clip_shape.py`.

| Field | Type | Meaning |
| --- | --- | --- |
| `x_mm` | float | Left edge, machine millimetres, origin at machine home |
| `y_mm` | float | Top edge, machine millimetres, y down |
| `width_mm` | float | Extent to the right. Must be finite and `> 0` |
| `height_mm` | float | Extent downward. Must be finite and `> 0` |

Derived:

- `x_max_mm = x_mm + width_mm`
- `y_max_mm = y_mm + height_mm`

`validate()` raises `ClipRectangleError` (a `ValueError`) when any coordinate is non-finite or when width or height is not greater than zero.

This slice has no mode flag. The only operation is keep-inside. Absence of a rectangle is `None` at the call site, not a sentinel object.

## Effective clip window

Not stored. Computed at prepare time:

```text
overlap_x_min = max(printable.x_min, rectangle.x_mm)
overlap_y_min = max(printable.y_min, rectangle.y_mm)
overlap_x_max = min(printable.x_max, rectangle.x_max_mm)
overlap_y_max = min(printable.y_max, rectangle.y_max_mm)
```

The printable rectangle is the work area inset by `PrintMargins` (default 10 mm horizontal and vertical when the caller omits margins).

If `overlap_x_max <= overlap_x_min` or `overlap_y_max <= overlap_y_min`, there is no positive overlap. Preparation yields no polylines and the existing empty-plot outcome.

Otherwise the overlap is a `ClipRect` and the existing Liang–Barsky walk clips to it.

## What does not change

- `PreparedLayerGeometry.polylines` stay in document millimetres, before placement.
- `ArtworkTransform` still maps document points into machine space before the clip.
- The emitted SVG page is still the full machine viewport (`width`/`height`, `viewBox="0 0 W H"`, 1 unit = 1 mm).
- Project JSON and settings do not gain a field in this slice.
