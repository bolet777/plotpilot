# Performance benchmarks (evaluation spike)

Hardware: macOS dev machine, Python 3.12, warm process. Times are **wall clock**, single-threaded, no `--parallel`.

## Method

**Current engine:** `prepare_positioned_plot_svg` (parse + page geometry + flatten + Liang–Barsky + validate + emit).

**Vpype spike:** `vpype.read_svg` (q=0.05 mm) + mm normalization + transform + Liang–Barsky (same clip as parity tests).

Iterations chosen for ~sub-second total per case.

## Results

| Fixture | Paths (approx) | Current (ms/op) | Vpype spike (ms/op) | Ratio (vp/current) |
|---------|----------------|-----------------|---------------------|--------------------|
| Tiny square (`identity_inside`) | 1 | 0.1 | 0.1 | ~0.55× |
| A4 drawing (`carre_a4_rotate`) | few | 0.1 | 0.1 | ~0.67× |
| Synthetic 1k paths | 1000 | 21.1 | 17.4 | ~0.83× |
| Synthetic 10k paths | 10000 | 220.1 | 179.0 | ~0.81× |

50k paths: not run in CI (smoke only in local dev); expect roughly linear scaling ~1.1–1.2 s/op order-of-magnitude from 10k extrapolation.

## Memory (qualitative)

- **Current:** svgelements tree + polyline lists; no numpy/scipy.
- **Vpype:** numpy complex arrays per path; scipy/shapely loaded at import — **higher baseline RSS**.

## Optimization commands (not integrated)

vpype provides `linemerge`, `linesort`, `linesimplify`, `reverse`, `crop`, etc. — potential overlap with axicli `-G1` preprocessing. Not benchmarked here; would require pipeline integration tests against plot time, not just prepare time.

Pytest: `@pytest.mark.slow` smoke in `test_vpype_benchmark_smoke` (excluded from `./scripts/test_fast.sh`).
