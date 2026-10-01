# Research — 025 preview performance

Measurements were taken on the monolithic pipeline **before** the split (`uv run python` against the same cubic-path generator now in `scripts/bench_preview_pipeline.py`). Times are one run on this machine, milliseconds.

## Before: where time went

Full `build_prepared_layer_preview` on the UI thread, including a repeated X move (same pipeline again).

| Stage | simple | 80 cubics | 1k paths | 10k paths |
| --- | ---: | ---: | ---: | ---: |
| Layer isolation | 0.0 | 0.0 | 0.0 | 0.0 |
| Physical size parse | 0.0 | 0.1 | 1.1 | 11.4 |
| Page geometry | 0.0 | 0.2 | 2.3 | 23.4 |
| Content diagnostics | 0.3 | 1.5 | 16.4 | 175.2 |
| svgelements parse | 0.1 | 3.1 | 31.7 | 339.0 |
| Curve flattening | 0.0 | 411.6 | 2846.1 | 9433.8 |
| Transform | 0.0 | 14.3 | 130.5 | 429.6 |
| Clip | 0.0 | 23.0 | 212.5 | 686.9 |
| SVG emission | 0.0 | 12.6 | 122.4 | 397.8 |
| Output validation | 0.1 | 17.4 | 160.1 | 538.3 |
| QSvgRenderer create (prepared) | 0.3 | 2.5 | 24.7 | 82.3 |
| QSvgRenderer render (prepared) | 0.1 | 5.4 | 40.7 | 135.1 |
| QSvgRenderer create (context) | 0.0 | 0.1 | 1.3 | 12.5 |
| Context render | 0.2 | 1.0 | 6.6 | 36.5 |
| **Full prepare** | **0.4** | **524.8** | **3901.9** | **13155.0** |
| **Repeat X (full pipe)** | **0.2** | **403.1** | **3732.1** | **12739.9** |

Flattening is the dominant cost and does not depend on X, Y, scale, or work-area orientation. Emission, validation, and a new `QSvgRenderer` are the next block, and they were repeated on every step. Context rendering is small next to that (1 ms at 80 paths, 6.6 ms at 1k, 36.5 ms at 10k) and happens once per layer for construction.

## Decisions

### Cache flattened document polylines

Decision: flatten once per layer; transform and clip on each edit.

Rationale: repeat-X was almost as expensive as the first prepare because nothing was reused.

Alternative: longer debounce. Rejected. It would hide the freeze and still block the event loop when the timer fired.

### Worker thread, newest generation wins

Decision: `QThreadPool` plus a generation gate. Stale results are dropped. Shutdown rejects anything still in flight.

Rationale: even a cached clip is 67 ms (80 paths) to about 1.9 s (10k paths). That must not run on the UI thread. The spinbox handler only arms the existing 50 ms timer and returns.

### Draw clipped polylines with QPainter

Decision: interactive black strokes use `drawPolyline`, rasterized into a widget pixmap when the polylines or the size change. The plot path still emits SVG and runs `_validate_output_geometry`.

Rationale: on the 1k fixture, emit + validate + renderer construction was about 307 ms on top of clip, and the prepared render was another 41 ms per paint. Skipping that round-trip is why the interactive path is faster. Keeping `QSvgRenderer` for the plotted result would put that cost back on every update.

The faint source stays on `QSvgRenderer`. Its cost is not the freeze, so it is not pixmap-cached.

### No coarse interactive tolerance

Decision: preview and plot both flatten at 0.05 mm.

Rationale: after the split, a normal drawing clips in tens of milliseconds off the UI thread. A second tolerance would risk a settled preview that does not match the plot. Not implemented.

## After

See [benchmarks.md](benchmarks.md). Cold prepare stays in the same range as before (flatten still runs once). Repeated X/Y/scale/orientation no longer re-parse or re-flatten.
