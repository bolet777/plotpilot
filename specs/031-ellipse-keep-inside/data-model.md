# Data Model: Ellipse Keep-Inside

`ClipEllipse` (frozen): `cx_mm`, `cy_mm`, `rx_mm`, `ry_mm`. `validate()` rejects non-finite values and non-positive radii.

`ClipShape` is `ClipRectangle | ClipEllipse`. Callers pass one shape or `None`.

Project JSON, version 1, written only when a shape exists:

- Rectangle, unchanged: `clipping.rectangle.{x_mm,y_mm,width_mm,height_mm}`
- Ellipse: `clipping.ellipse.{cx_mm,cy_mm,rx_mm,ry_mm}`

Both keys at once is a project error. A missing `clipping` object is no shape.
