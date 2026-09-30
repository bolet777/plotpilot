# Implementation notes — 020

## Files

| Area | Module |
|------|--------|
| Isolation | `src/plotpilot/svg/preview.py` |
| Extraction / hidden / defs filter | `src/plotpilot/svg/layers.py` |
| Layer model | `src/plotpilot/models/svg_layer.py` |
| UI label | `src/plotpilot/ui/main_window.py` |

## `preview.py`

- `_append_root_resources`: deep-copy root `<defs>` and `<style>`.
- `_build_parent_map` + `_ancestor_chain` + `_append_isolated_layer`: shallow ancestor shells, deep target copy.

## `layers.py`

- Single `parent_map` per `extract_layers` call; O(depth) defs checks replace repeated full-tree walks.
- `_is_layer_hidden` for U11.

## Tests

- `tests/test_svg_preview.py`: style retention, nested ancestor chain, sibling exclusion.
- `tests/test_svg_layers.py`: defs layer ignored, hidden flag/label.
- `tests/test_golden_svg.py`: B6/B7 xfail removed.
