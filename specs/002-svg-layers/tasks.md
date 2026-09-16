# Tasks: 002-svg-layers

## Phase 1 — Model & extraction

- [x] T001 Add `SvgLayer` in `models/svg_layer.py`
- [x] T002 Implement `extract_layers` in `svg/layers.py` (Inkscape detect, synthetic fallback, color, counts)
- [x] T003 Add SVG fixtures and `tests/test_svg_layers.py` (cases 1–13)

## Phase 2 — UI

- [x] T004 Add **Layers** list to `main_window.py` (swatch, name, selection)
- [x] T005 Refresh layers on successful open; preserve on failure (`test_main_window_layers.py`)

## Phase 3 — Verify

- [x] T006 Run pytest, ruff check, ruff format --check
