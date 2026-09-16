# Quickstart: 002-svg-layers

1. Run `plotpilot` (or `python -m plotpilot.app.main`).
2. **File → Open SVG…** and choose an Inkscape-layered SVG.
3. Confirm the **Layers** list shows names in order with color dots where detectable.
4. Open a flat SVG — expect one row named like the file.
5. Open a second file — list updates; cancel or open invalid file — prior state unchanged.

```bash
pytest tests/test_svg_layers.py tests/test_main_window_layers.py -q
ruff check src tests
ruff format --check src tests
```
