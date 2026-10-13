# Feature Specification: Ellipse Keep-Inside

**Feature Branch**: `031-ellipse-keep-inside`

**Created**: 2026-10-13

**Status**: Implemented on `031-ellipse-keep-inside`. Not merged.

**Input**: Slice 3 of shape clipping: circle and ellipse keep-inside on the existing clip tool. Rectangle clipping stays. No remove-inside. No new panel.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Draw an ellipse or circle (Priority: P1)

With the clip tool on, the user picks Ellipse and drags. Shift constrains a circle. Strokes inside the shape stay; the rest become the faint ghost. The amber outline is not plotted.

**Independent Test**: Drag an ellipse, hold Shift, and confirm equal radii in machine millimetres after zoom and pan.

### User Story 2 - Edit and plot (Priority: P1)

Move, resize from handles, and delete. Preview, estimate, plot, and multi-layer use the same cut. The printable area is still applied first. A rectangle still uses the single Liang–Barsky pass.

**Independent Test**: A horizontal and a vertical line through an ellipse are cut to the chord. A tangent emits nothing. A path that crosses twice becomes two polylines.

### User Story 3 - Project file (Priority: P2)

`clipping.ellipse` stores center and radii. Version stays 1. A project that only has `clipping.rectangle` still opens.

## Requirements

- Store `cx_mm`, `cy_mm`, `rx_mm`, `ry_mm`. A circle is equal radii.
- Map each segment into the unit circle, cut, and map the hits back to millimetres.
- Drop tangents and other zero-length contacts. Do not bridge separated spans.
- Reject non-positive radii.
- Editing stays inside the printable area.
- Artwork transform, zoom, and pan do not move the shape.
- No SVG `clipPath`, no `QPainter` mask, no new dependency, no Qt in geometry.

## Out of scope

Remove-inside, rotated ellipses, and a numeric clipping panel. Those belong to later slices.
