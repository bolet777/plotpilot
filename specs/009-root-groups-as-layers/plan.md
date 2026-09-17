# Plan: Root SVG groups as layers

## Approach

Extend `extract_layers` in `plotpilot/svg/layers.py` with a root-group fallback between Inkscape detection and synthetic document layer. Add `LayerSource` on `SvgLayer`. No preview or plot pipeline changes required.

## Files

- `src/plotpilot/models/svg_layer.py` — `LayerSource` enum, `source` field
- `src/plotpilot/svg/layers.py` — fallback extraction and naming
- Tests and fixtures under `tests/`
