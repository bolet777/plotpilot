# Feature Specification: Remove Inside

**Feature Branch**: `032-remove-inside`

**Created**: 2026-10-13

**Status**: Frozen. Pytest, ruff, and a driven main-window pass were run before the merge. Not a user sign-off.

**Input**: Slice 4 of shape clipping. Remove the inside of the current rectangle or ellipse. Keep inside stays the default, including the rectangle fast path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cut a hole (Priority: P1)

With a clip shape drawn, the user chooses Remove inside. Strokes inside the shape disappear. Strokes in the rest of the printable area stay. A line through the shape becomes two pieces with a gap, and the pen does not bridge the gap.

**Independent Test**: A horizontal line through a rectangle, a circle, and an ellipse each becomes two polylines. A segment fully inside the shape is gone. A segment fully outside it remains.

### User Story 2 - Switch mode (Priority: P1)

Switching between Keep inside and Remove inside keeps the shape, its position, and the zoom and pan. The preview updates. The original SVG is unchanged.

### User Story 3 - Project file (Priority: P2)

`clipping.mode` is `remove_inside` when that mode is saved. A missing mode is Keep inside. Version stays 1.

## Requirements

- Clip to the printable area first, then subtract the shape.
- One segment may emit two spans. Those spans are separate paths.
- Drop zero-length contacts, including tangents.
- Rectangle Keep inside remains one Liang–Barsky pass on the overlap.
- No new dependency, no SVG mask, no Qt in geometry.

## Out of scope

Several shapes, rotated rectangles, freeform outlines, and numeric millimetre fields.
