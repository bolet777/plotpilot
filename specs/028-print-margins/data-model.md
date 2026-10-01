# Data Model: Editable Print Margins

## PrintMargins

Qt-free frozen dataclass in `src/plotpilot/models/print_margins.py`.

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `horizontal_mm` | float | 10.0 | Left inset and right inset |
| `vertical_mm` | float | 10.0 | Top inset and bottom inset |

### Validation

`validate()`:

- Both values are finite.
- Both values are `>= 0`.
- Negative and non-finite values raise `PrintMarginsError`.

`validate_for_work_area(width_mm, height_mm)`:

- Work area width and height are finite and positive.
- `width - 2 * horizontal_mm >= 0.1`
- `height - 2 * vertical_mm >= 0.1`
- Otherwise raise `PrintMarginsError` with a message that names the margin and the work-area size.

`0` is valid whenever the work area itself is at least 0.1 mm on that axis.

`max_symmetric_margin_mm(span_mm)` is the largest 0.1 mm spin step that still leaves a 0.1 mm printable span: `floor((span - 0.1) / 2, 0.1)`.

## PrintableArea

Derived, not stored as a user setting.

| Field | Type | Meaning |
|-------|------|---------|
| `x_mm` | float | Left edge in machine mm (`horizontal_mm`) |
| `y_mm` | float | Top edge in machine mm (`vertical_mm`) |
| `width_mm` | float | `work_width - 2 * horizontal_mm` |
| `height_mm` | float | `work_height - 2 * vertical_mm` |

Derived edges: `x_max_mm = x_mm + width_mm`, `y_max_mm = y_mm + height_mm`.

`printable_area_for(work_width_mm, work_height_mm, margins)` validates and returns the rectangle. It does not move the work-area origin.

### Examples

| Work area | Margins | Printable area |
|-----------|---------|----------------|
| 300 × 217.9 | 10 / 10 | x=10, y=10, 280 × 197.9 |
| A4 portrait 210 × 297 | 10 / 10 | x=10, y=10, 190 × 277 |
| A4 landscape 297 × 210 | 10 / 10 | x=10, y=10, 277 × 190 (x 10..287, y 10..200) |
| AxiDraw model travel | 10 / 10 | same formula on that model's width and height |
| any | 0 / 0 | x=0, y=0, full work area |

## ProjectSession

New field, default `PrintMargins()`:

`print_margins: PrintMargins`

Existing constructors that omit it keep 10 / 10.

## MultiLayerPlotJob

New field, default `PrintMargins()`, snapshotted when the job starts so a later edit does not change an in-flight plot.

## Settings session

`SettingsService` keeps `_session_margins` while a project is active. The property `print_margins` returns the session value when set, otherwise the `QSettings` value. Global keys are not written during a project session.

## Project file (v1, optional)

```json
"print": {
  "margin_horizontal_mm": 10.0,
  "margin_vertical_mm": 10.0
}
```

Absent object or absent fields → 10 / 10. Version remains 1.

## Clip rectangle

Passed into geometry as millimeters:

```text
x_min = printable.x_mm
y_min = printable.y_mm
x_max = printable.x_max_mm
y_max = printable.y_max_mm
```

Omitted clip bounds mean the full viewport. That is not the product default; the product default is `PrintMargins()`.
