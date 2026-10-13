# Feature Specification: Rectangle Keep-Inside Clip

**Feature Branch**: `029-rectangle-keep-inside`

**Created**: 2026-10-13

**Status**: Frozen — not user-tested. Geometry only; no in-app validation and no UI.

**Input**: User description: "Slice 1 of shape clipping: an optional axis-aligned rectangle in machine millimetres that keeps strokes inside the intersection of that rectangle and the printable area. Original artwork stays unchanged. Preview and plot geometry stay identical. No interactive UI."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep pen strokes inside a rectangle (Priority: P1)

Someone preparing a plot supplies an axis-aligned rectangle on the machine bed. PlotPilot keeps only the pen strokes that fall inside both that rectangle and the existing printable area. Strokes that cross the rectangle are cut at the boundary. Strokes that leave and come back become separate pen-down runs, with no invented line across the gap.

**Why this priority**: This is the cut the later drawing tools will call. Without a correct geometric result, a preview button would only hide ink that the plotter would still draw.

**Independent Test**: Prepare a line that crosses a rectangle inside the printable area and confirm the kept segment starts and ends on the rectangle edges. Prepare a closed path that leaves the rectangle and re-enters, and confirm two separate runs with no bridge across the outside.

**Acceptance Scenarios**:

1. **Given** a printable area and a keep-inside rectangle that sits entirely inside it, **When** a straight stroke crosses that rectangle, **Then** only the portion inside the rectangle is kept, and the cut points lie on the rectangle boundary.
2. **Given** a closed stroke that starts inside the rectangle, travels outside, and re-enters, **When** it is prepared, **Then** the result is two separate runs and no new segment joins the exit point to the re-entry point.
3. **Given** a stroke that lies entirely inside the rectangle and the printable area, **When** it is prepared, **Then** the stroke is kept.
4. **Given** a stroke that misses the rectangle, **When** it is prepared, **Then** that stroke is omitted.
5. **Given** artwork that misses the rectangle entirely, **When** it is prepared, **Then** preparation reports that nothing intersects the plot area, using the same outcome as artwork that misses the printable area today.
6. **Given** a keep-inside rectangle that overlaps the margin, **When** artwork is prepared, **Then** the kept region is only the overlap of the rectangle and the printable area. No prepared point lies in the margin or outside the machine work area.
7. **Given** a keep-inside rectangle that does not overlap the printable area, **When** artwork is prepared, **Then** the result is the same empty-plot outcome as artwork that misses the printable area.

---

### User Story 2 - Leave today's plots unchanged (Priority: P1)

When no keep-inside rectangle is supplied, preview preparation and plot preparation behave exactly as they do today: strokes are still limited to the printable area, margins still inset that area, and existing drawings prepare to the same geometry.

**Why this priority**: A new optional cut must not move, scale, or trim jobs that do not use it.

**Independent Test**: Prepare the existing clipping fixtures with no rectangle and confirm the prepared strokes match the current results, including margin insets, exit-and-re-enter splits, and the empty-plot message.

**Acceptance Scenarios**:

1. **Given** no keep-inside rectangle, **When** a drawing is prepared, **Then** the prepared strokes match preparation without this feature.
2. **Given** no keep-inside rectangle and non-zero print margins, **When** a stroke crosses the printable edge, **Then** it is still cut on the printable boundary and the machine origin is unchanged.
3. **Given** the original SVG text and the flattened drawing, **When** a keep-inside rectangle is applied, **Then** that source text and that flattened drawing are not modified. The cut exists only on the prepared result.

---

### User Story 3 - Preview and plot describe the same cut (Priority: P2)

The geometry shown as the prepared preview and the geometry written for the plotter are the same polylines when both are given the same drawing, placement, margins, and keep-inside rectangle.

**Why this priority**: A plot that differs from the prepared preview would send the pen somewhere the user did not see.

**Independent Test**: Run preview preparation and plot preparation on the same inputs, with and without a keep-inside rectangle, and confirm the polyline lists match.

**Acceptance Scenarios**:

1. **Given** the same layer, placement, work area, margins, and keep-inside rectangle, **When** preview preparation and plot preparation run, **Then** they produce the same polylines.
2. **Given** those same inputs with no keep-inside rectangle, **When** both preparations run, **Then** they still produce the same polylines as each other.

---

### Edge Cases

- A rectangle with zero or negative width or height, or a non-finite coordinate, is rejected and is not used as a clip window.
- A rectangle that only touches the printable area along an edge (no positive overlap area) is treated as no overlap.
- A stroke that only touches the rectangle at a single point does not become a zero-length pen-down run.
- A keep-inside rectangle does not change page orientation, scale, or translation. Those still happen before the cut, and the rectangle is applied in machine millimetres afterward.
- Curves are cut with the same smoothness already used for the printable-area cut. This slice does not introduce a second smoothness.
- The rectangle is axis-aligned on the machine bed. Rotated rectangles, circles, ellipses, and "remove the inside" are out of scope.
- Drawing the rectangle on screen, storing it in a project file, and choosing it per layer are out of scope. This slice only defines what preparation does when a rectangle is supplied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Preparation MUST accept an optional axis-aligned keep-inside rectangle expressed in machine millimetres (origin, width, and height, y increasing downward, same as the machine bed).
- **FR-002**: When a rectangle is supplied, prepared strokes MUST lie inside the overlap of that rectangle and the current printable area. The printable area remains the work area inset by the current margins.
- **FR-003**: Strokes that cross the overlap MUST be cut at the boundary. A stroke that leaves the overlap and re-enters MUST become separate pen-down runs, with no segment added across the excluded region.
- **FR-004**: When the overlap contains no artwork, or the rectangle does not overlap the printable area, preparation MUST report the same empty-plot outcome already used when artwork misses the printable area.
- **FR-005**: When no rectangle is supplied, prepared geometry MUST match today's printable-area result for the same drawing, placement, work area, and margins.
- **FR-006**: Applying a rectangle MUST NOT modify the source SVG text or the flattened drawing it was derived from.
- **FR-007**: Preview preparation and plot preparation MUST emit the same polylines for the same drawing, placement, work area, margins, and rectangle (including when the rectangle is absent).
- **FR-008**: A rectangle with non-finite coordinates or a non-positive width or height MUST be rejected.
- **FR-009**: Prepared points MUST remain inside the machine work area. A rectangle MUST NOT extend plotting into the margin.

### Key Entities

- **Keep-inside rectangle**: An optional axis-aligned window on the machine bed. It has a position and a positive width and height in millimetres. It does not replace the printable area; the kept region is their overlap. It is not stored in the project file in this slice and is not drawn by the user in this slice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a straight stroke that crosses a keep-inside rectangle inside the printable area, the prepared stroke's endpoints lie on the rectangle boundary and every prepared point lies inside that rectangle.
- **SC-002**: For a path that leaves the rectangle and re-enters, preparation yields at least two separate runs, and none of those runs connects the exit point directly to the re-entry point.
- **SC-003**: With no rectangle supplied, prepared geometry for the existing printable-area cases matches the results those cases have today.
- **SC-004**: When a rectangle overlaps a margin, every prepared point lies in the overlap, and none lies in the margin band.
- **SC-005**: On matching inputs, the polyline list from preview preparation and the polyline list from plot preparation are the same, both with a rectangle and without one.
- **SC-006**: After preparation, the source SVG text is byte-for-byte unchanged.

## Assumptions

- Callers that want this cut pass the rectangle into preparation. No on-screen drawing tool, project-file field, or plot-button wiring is part of this slice.
- "The same empty-plot outcome" means the message and empty result already produced when prepared artwork misses the printable area.
- A square is a rectangle whose width equals its height. This slice does not add a separate square concept.
- Default margins stay 10 mm unless the caller passes other margins. This slice does not change that default.
- Later slices may add a circle or ellipse, a remove-inside operation, and a way to draw the rectangle. They are not required for this slice to be complete.
