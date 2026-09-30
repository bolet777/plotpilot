# Plan: 018-fix-core-geometry

## Phase 1 — B1 clipping invariant

1. Remove `pen_xy` source mutation in `plot_segment`.
2. Clip each `(source_start, source_end)` pair independently.
3. Merge output only when `current[-1]` ≈ clipped start.
4. Add topology unit tests + remove B1 golden xfails.

## Phase 2 — B2 arc length

1. Use `Arc.length()` in `_estimate_segment_length_rendered`.
2. Keep chord fallback for cubics/quadratics (avoid slow `length()` on extreme cubics).
3. Add arc matrix tests + remove B2 golden xfail.

## Phase 3 — B13 cleanup

1. `_dedupe_consecutive_points` + `_sanitize_polyline` on flush.
2. Skip zero-length clipped segments before merge.
3. Unit tests for duplicate and all-zero paths.

## Phase 4 — Validation

1. `./scripts/test_fast.sh`
2. `pytest -m "not hardware"`
3. ruff check/format
4. Spec artifacts and PR (no merge)
