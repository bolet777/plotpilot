# Implementation Plan: SVG Layer Detection and List

**Branch**: `002-svg-layers` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

## Summary

Add pure `extract_layers(SvgDocument) -> list[SvgLayer]` using stdlib ElementTree on the
existing parsed root. Detect Inkscape layers via namespaced `groupmode="layer"`; otherwise
return one synthetic document layer. Extend the main window with a selectable **Layers** list
(color swatch + name). Refresh layers only on successful open; failed opens unchanged.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: PySide6 (UI); stdlib XML only in `svg/layers.py`

**Storage**: In-memory

**Testing**: pytest for `layers.py` and fixtures; lightweight Qt tests for open/replace/preserve

**Constraints**: No SVG libraries, no preview/plotter, no visibility toggles

## Constitution Check

| Principle | Status |
|-----------|--------|
| UI vs hardware | Pass |
| SVG logic outside UI | Pass — `svg/layers.py`, `models/svg_layer.py` |
| Testable without hardware | Pass |
| Minimal slice | Pass |
| Clarity | Pass — one extraction function |

## Project Structure

```text
src/plotpilot/
├── models/svg_layer.py
├── svg/layers.py
└── ui/main_window.py

tests/
├── fixtures/*.svg
├── test_svg_layers.py
└── test_main_window_layers.py
```

**Structure Decision**: No separate `layer_service` unless UI needs a thin wrapper; call
`extract_layers` from `MainWindow` after load.

## Complexity Tracking

None.
