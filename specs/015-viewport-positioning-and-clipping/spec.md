# Feature Specification: Viewport positioning and safe clipping

**Feature Branch**: `015-viewport-positioning-and-clipping`  
**Created**: 2026-09-22  
**Status**: Implemented (core); see [implementation-notes.md](./implementation-notes.md)  
**Input**: Position and scale artwork relative to a fixed machine viewport; geometrically clip before axicli.

## User Scenarios & Testing

### User Story 1 - Position artwork in the viewport (Priority: P1)

The user drags or enters X/Y (mm) to move artwork under a fixed red machine rectangle. Negative offsets are allowed; portions outside the rectangle will not plot.

**Independent Test**: Adjust X/Y, preview shows artwork moving while red boundary stays fixed; generated plot SVG contains only in-bounds geometry.

**Acceptance Scenarios**:

1. **Given** a loaded layer, **When** the user sets X = −25 mm, **Then** preview shows artwork shifted left and plot output clips to the machine rectangle.
2. **Given** artwork fully outside the rectangle, **When** the user starts plot, **Then** plotting is blocked with “No artwork intersects the plot area.”

### User Story 2 - Scale physical artwork (Priority: P1)

The user changes Scale (%) to resize plotted output (not camera zoom).

**Independent Test**: Scale 200% doubles plotted extent in preview and clipped output.

**Acceptance Scenarios**:

1. **Given** scale 150%, **When** plot prepares, **Then** estimate and axicli receive clipped SVG at 1.5× size (within viewport).

### User Story 3 - Safe multi-layer registration (Priority: P1)

Multi-layer jobs snapshot one `ArtworkTransform` for all layers.

**Independent Test**: Start multi-layer job; change X during pen-change wait does not alter queued layers.

**Acceptance Scenarios**:

1. **Given** an active multi-layer job, **When** layer 2 plots, **Then** it uses the same transform snapshot as layer 1.

## Edge Cases

- Empty clip result → block plot, clear message.
- Default (CLI) model → user-selected fallback defines clip rect with explicit unverified warning.
- Source SVG page larger than machine → informational bounds status; clip still governs motion.
- Path crossing boundary twice → two disconnected plotted paths, no bridge across outside region.

## Requirements

### Functional Requirements

- **FR-001**: Provide `ArtworkTransform` (x_mm, y_mm, uniform scale > 0) without rotation.
- **FR-002**: Preview shows fixed machine rectangle and transformed artwork; optional dimming outside.
- **FR-003**: Mouse drag updates x/y in mm via preview `mm_to_px`.
- **FR-004**: Pipeline: isolate layer → mm coordinates → transform → flatten → clip → validate → temp SVG → axicli.
- **FR-005**: Final validator rejects NaN/inf and coordinates outside machine rect (tolerance); cancel plot on failure.
- **FR-006**: Estimate and `-G1` optimization operate on clipped temp SVG only.
- **FR-007**: Original `SvgDocument.raw_text` and disk file never modified.
- **FR-008**: Explicit model or fallback work area required for clip dimensions when model is Default (CLI).
- **FR-009**: Reset sets x=0, y=0, scale=100%.

## Success Criteria

- Users can intentionally crop artwork by positioning under the red viewport.
- Generated plot SVG contains only geometry inside the machine rectangle (verified by tests + validator).
- Hardware tests remain manual; automated suite passes without plotter.

## Assumptions

- Stroke-based plotting; fill behavior documented in research.md limitations.
- Liang–Barsky segment clipping; curve flatten 0.05 mm.
