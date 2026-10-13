# Data model: Interactive keep-inside rectangle

## ClipRectangle

Unchanged from Slice 1 (`src/plotpilot/models/clip_shape.py`).

Drag helpers, also Qt-free:

- `drag_rectangle(anchor, pointer, *, square, bounds)` builds one rectangle. Shift uses equal width and height, shrunk so the square stays inside the bounds. Returns `None` when either side is under 1 mm.
- `translate_rectangle(rect, dx, dy, bounds)` slides the rectangle without changing its size, stopping at the printable edges.

## ProjectSession

New optional field `clip_rectangle: ClipRectangle | None = None`.

JSON, only when a rectangle is present:

```json
"clipping": {
  "rectangle": {"x_mm": 10.0, "y_mm": 20.0, "width_mm": 40.0, "height_mm": 40.0}
}
```

## MultiLayerPlotJob

New optional field `keep_inside: ClipRectangle | None = None`, copied onto every layer plot in the job.

## Preview widget state

One rectangle. Gesture is draw, move, or resize-from-corner. The move tool and the clip tool are not both on. Zoom and pan stay on the view, not on the rectangle.
