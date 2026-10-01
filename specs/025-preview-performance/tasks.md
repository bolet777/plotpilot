# Tasks — 025 preview performance

- [X] Measure the monolithic preview pipeline on simple, 80-path, 1k, and 10k fixtures before changing it.
- [X] Split flatten (stable) from transform/clip (dynamic) without changing plot geometry.
- [X] Cache `PreparedLayerGeometry` per document and layer; invalidate on document or layer change only.
- [X] Run flatten and clip off the UI thread; drop stale generations; shut down safely.
- [X] Draw interactive plotted geometry with `QPainter` from already clipped polylines.
- [X] Keep SVG emission and `_validate_output_geometry` on the plot path.
- [X] Parity tests: preview polylines match emitted plot SVG.
- [X] Cache, stale-result, shutdown, and source-unchanged tests.
- [X] Re-benchmark cold vs cached X/Y/scale/orientation.
- [X] Leave context `QSvgRenderer` uncached; do not add a coarse flatten tolerance.
