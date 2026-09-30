# Feature Specification: Fix core geometry (B1, B2, B13)

**Feature Branch**: `018-fix-core-geometry`  
**Created**: 2026-09-30  
**Status**: In review  
**Input**: Audit roadmap step 2 — correct clipping, arc flattening, and degenerate output cleanup without touching unit heuristics, preview, layers, or plotter backend.

## Invariant

Clipping may split visible geometry into separate polylines, but it must never invent segments that were not part of the original flattened source path.

## User Scenarios & Testing

### User Story 1 — Square stays a square when clipped (P0, B1)

A rectangle that exits and re-enters the machine viewport plots as separate visible edges, never as a triangle bridged by a diagonal.

**Independent Test**: Golden `clipping/b1_square_exit_reenter` and scaled variant pass.

### User Story 2 — Near-complete arcs flatten correctly (P0, B2)

An SVG arc whose endpoints nearly coincide still produces enough samples along the true arc/circle geometry.

**Independent Test**: Golden `paths/b2_near_complete_arc` passes (≥30 points, circle/bbox oracle).

### User Story 3 — No degenerate plot noise (P1, B13)

Prepared output drops consecutive duplicate points and zero-length polylines without simplifying real geometry.

**Independent Test**: Unit tests in `tests/test_geometry_clipping.py`.

## Requirements

- **FR-001**: Each source segment is clipped independently; prior clipped endpoints must not replace later segment starts.
- **FR-002**: Polyline merging happens only when the next clipped start matches the previous emitted point within tolerance.
- **FR-003**: Arc flattening step count uses svgelements `Arc.length()` (not chord polyline length).
- **FR-004**: B13 cleanup at polyline flush: dedupe consecutive points within `COORD_TOLERANCE_MM`, discard polylines with fewer than two distinct points.
- **FR-005**: Do not fix B3, B4, B5, B6, B7, B8, B9, B10, B12 in this slice.

## Success Criteria

- Former B1/B2 golden XFAIL tests pass; B3/B5/B6/B7/B10 remain XFAIL.
- Known-good goldens unchanged.
- Fast suite and non-hardware pytest under 15s; ruff clean.
