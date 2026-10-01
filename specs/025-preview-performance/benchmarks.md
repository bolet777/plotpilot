# Benchmarks — 025 preview performance

Command: `uv run python scripts/bench_preview_pipeline.py`

Fixtures: `tests/fixtures/simple.svg`, plus generated cubic paths (80, 1000, 10000) on a 210×297 mm page. Same generator as the before run.

Times are milliseconds, one run. Cold is `prepare_layer_geometry` (includes flattening). Cached rows are `position_and_clip_geometry` only.

## Before (full pipeline, every move, UI thread)

| Fixture | Cold / full prepare | Repeat X |
| --- | ---: | ---: |
| simple | 0.4 | 0.2 |
| 80 cubics | 524.8 | 403.1 |
| 1k paths | 3901.9 | 3732.1 |
| 10k paths | 13155.0 | 12739.9 |

Repeat X re-parsed and re-flattened. Stage breakdown: [research.md](research.md).

## After (flatten once, then clip)

| Fixture | Cold prepare | Cached X | Cached Y | Cached scale | Cached orientation |
| --- | ---: | ---: | ---: | ---: | ---: |
| simple | 0.3 | 0.0 | 0.0 | 0.0 | 0.0 |
| 80 cubics | 376.4 | 67.0 | 61.8 | 57.0 | 55.7 |
| 1k paths | 2903.6 | 578.5 | 573.7 | 531.1 | 517.9 |
| 10k paths | 9910.3 | 1924.2 | 1892.2 | 1736.8 | 1685.0 |

Cold stays dominated by flattening, as expected. A repeated move no longer pays parse, flatten, SVG emission, or validation.

Those cached times run on the worker, not the UI thread. The spinbox handler returns without flattening. On a dense file the previous black preview can stay up until the worker finishes; the faint source moves immediately.

## Rendering note

Before, each move also built a prepared `QSvgRenderer` (25 ms at 1k, 82 ms at 10k) and painted it (41 ms / 135 ms). Interactive preview draws the clipped polylines directly and keeps a pixmap until the geometry or the widget size changes. Context SVG render was 1.0 ms (80 paths), 6.6 ms (1k), 36.5 ms (10k) and was left on `QSvgRenderer`.
