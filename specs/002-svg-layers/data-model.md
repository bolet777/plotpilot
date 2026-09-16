# Data Model: SVG Layers

## SvgLayer (new)

| Field | Type | Notes |
|-------|------|-------|
| `layer_id` | str | Stable id from XML `id` or generated |
| `name` | str | Display name (label / id / fallback) |
| `order` | int | 0-based document order |
| `element` | Element | Layer `<g>` or `<svg>` root for synthetic |
| `representative_color` | str \| None | Raw stroke/fill value if detected |
| `drawable_count` | int | Descendant drawable elements |

Frozen dataclass in `models/svg_layer.py`.

## SvgDocument (unchanged)

Input to `extract_layers(document)`.
