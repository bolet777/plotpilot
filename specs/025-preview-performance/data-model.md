# Data model — 025 preview performance

## PreparedLayerGeometry

Immutable. No Qt types.

| Field | Meaning |
| --- | --- |
| `context_svg_text` | Isolated layer SVG |
| `page_width_mm`, `page_height_mm` | Physical page |
| `content_counts` | Stroke / fill / text / image counts |
| `polylines` | Document-millimeter subpaths, flattened, not yet placed |
| `preparation_error` | Set when the page or the flatten step fails |

## ClippedLayerGeometry

| Field | Meaning |
| --- | --- |
| `polylines` | Machine-millimeter subpaths after transform and clip |
| `path_count` | Number of those subpaths |
| `error_message` | Preparation failure, or no intersection with the plot area |

## LayerGeometryCache

One entry: `(document_id, layer_id) → PreparedLayerGeometry`.

- `prepare_count` increments when a miss builds geometry.
- `clip_count` increments on each placement.
- `invalidate()` drops the entry.

`document_id` is `id(document)`. A newly loaded file is a new object.

## PreviewResultGate

- `issue()` returns the next generation.
- `accept(generation)` is true only when that generation is current and `shutdown()` has not been called.
- `shutdown()` rejects every generation, including one that was current.

## InteractivePreview

Worker result: document id, layer id, optional fresh geometry (cache miss only), page size, clipped geometry, status lines, work area. The UI stores `fresh_geometry` only if the gate accepts the generation and the document id still matches.
