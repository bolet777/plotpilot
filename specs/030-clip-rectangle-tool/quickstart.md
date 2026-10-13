# Quickstart: Interactive keep-inside rectangle

## Prerequisites

Branch `030-clip-rectangle-tool`, from the repository root:

```bash
uv sync --group dev
```

## Automated checks

```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```

## In the app

```bash
uv run plotpilot
```

Open an SVG with many strokes. Turn on the Clip tool (the rectangle button on the preview strip). Drag on the printable area. The amber overlay should follow the pointer while the black strokes catch up. Shift should make a square. Drag inside to move, drag a corner to resize, and press Delete to clear it. Zoom and pan, then confirm the cursor readout still matches the rectangle. Plot or estimate should use the cut. The move tool and the clip tool should not stay on together.

Resize the window to a narrow size and confirm the properties panel still scrolls and the action bar still wraps.
