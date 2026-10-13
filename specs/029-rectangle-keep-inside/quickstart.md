# Quickstart: Rectangle keep-inside clip

## Prerequisites

From the repository root, on branch `029-rectangle-keep-inside`:

```bash
uv sync --group dev
```

No plotter and no display are required.

## Validate

```bash
uv run pytest tests/test_rectangle_keep_inside.py tests/test_geometry_clipping.py \
  tests/test_positioned_plot.py tests/test_preview_plot_parity.py \
  tests/test_print_margins.py -q

uv run ruff check src tests
uv run ruff format --check src tests
```

Expect the new rectangle tests to pass and the existing clip, margin, and preview/plot parity tests to pass unchanged.

## What success looks like

- A line that crosses a keep-inside rectangle is trimmed to that rectangle.
- A path that leaves the rectangle and re-enters becomes two runs, with no bridge.
- A rectangle that overlaps the margin keeps points only in the overlap.
- No rectangle: prepared geometry matches the current printable-area clip.
- The same inputs to preview preparation and plot preparation yield the same polylines.
- The source SVG text is unchanged after preparation.

## Not covered here

Drawing the rectangle in the preview, saving it in a project, circles, and remove-inside. Those are later slices.
