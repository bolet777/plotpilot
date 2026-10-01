# Quickstart — 025 preview performance

## Checks

```bash
uv run pytest tests/test_preview_performance.py -q
./scripts/test_fast.sh
uv run pytest -m "not hardware" -q
uv run ruff check src tests
uv run ruff format --check src tests
```

## Benchmark

```bash
uv run python scripts/bench_preview_pipeline.py
```

Compare with [benchmarks.md](benchmarks.md). Cold prepare includes flattening. Cached X/Y/scale/orientation must not.

## What to look at in the app

1. Open a dense SVG.
2. Hold a position or scale spinbox arrow. The number should keep stepping. The faint drawing moves at once. The black strokes catch up.
3. Switch portrait/landscape. The black strokes update without a multi-second freeze after the first prepare of that layer.
4. Plot still sends validated SVG (unchanged axicli path).
