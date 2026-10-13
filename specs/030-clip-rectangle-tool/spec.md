# Feature Specification: Interactive Keep-Inside Rectangle

**Feature Branch**: `030-clip-rectangle-tool`

**Created**: 2026-10-13

**Status**: Frozen. Pytest, ruff, and a driven main-window pass were run before the merge. Not a user sign-off.

**Input**: User description: "Slice 2: draw, move, resize, and delete one keep-inside rectangle on the preview. Machine millimetres. Optional project field on the existing file version. Preview, plot, estimate, and multi-layer use the Slice 1 cut. No extra panel and no Apply button."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Draw and edit a rectangle on the page (Priority: P1)

The user turns on a Clip tool next to the existing move tool, drags a rectangle on the page, and sees the pen strokes cut to that rectangle. Shift keeps the drag square. They can move it, pull a corner to resize it, and delete it. The rectangle stays visible as an overlay. It is not a pen stroke.

**Why this priority**: Without a way to place the rectangle, the Slice 1 cut never runs in the application.

**Independent Test**: On a preview with a known millimetre scale, drag a rectangle, move it, resize a corner, hold Shift, and press Delete. Confirm the stored millimetres and that zoom or pan does not change them.

**Acceptance Scenarios**:

1. **Given** the Clip tool is on, **When** the user drags on the printable area, **Then** a rectangle is stored in machine millimetres and the prepared strokes update to the keep-inside cut.
2. **Given** a drag with Shift held, **When** the rectangle is created or resized, **Then** its width and height are equal, unless the printable edge stops the drag sooner.
3. **Given** an existing rectangle and the Clip tool, **When** the user drags inside it, **Then** the whole rectangle moves and stays inside the printable area.
4. **Given** an existing rectangle and the Clip tool, **When** the user drags a corner, **Then** that corner follows the pointer and the opposite corner stays put.
5. **Given** a rectangle and the Clip tool focused on the preview, **When** the user presses Delete or Backspace, **Then** the rectangle is removed and the strokes return to the printable-area cut only.
6. **Given** a rectangle, **When** the user zooms or pans, **Then** the stored millimetres are unchanged.
7. **Given** a rectangle, **When** the user moves, scales, or rotates the artwork, **Then** the rectangle stays on the bed and the artwork moves through it.
8. **Given** the Clip tool is on, **When** the user turns the move tool on, **Then** the Clip tool turns off, and the reverse is also true.

---

### User Story 2 - Plot and estimate use the same rectangle (Priority: P1)

A plot, a pre-plot estimate, and a multi-layer job all cut every layer with the rectangle currently on the page. The rectangle outline is not sent to the plotter.

**Why this priority**: A rectangle that only changes the preview would still draw the uncut file.

**Independent Test**: Prepare a preview and a plot with the same rectangle and confirm the polylines match. Run a two-layer job and confirm both plot files use that cut and neither file contains the rectangle as its own stroke.

**Acceptance Scenarios**:

1. **Given** a rectangle, **When** the selected layer is plotted or estimated, **Then** the prepared geometry matches the preview cut.
2. **Given** a rectangle, **When** checked layers are plotted in sequence, **Then** each layer is cut with that same rectangle.
3. **Given** any rectangle, **When** the plot file is written, **Then** it contains only cut artwork strokes.

---

### User Story 3 - Remember the rectangle in a project (Priority: P2)

Saving a project stores the rectangle. Opening it restores the rectangle. A project file that has no clipping information opens with no rectangle. The project file version does not change.

**Why this priority**: The rectangle is part of how a job is set up, like margins, but older projects must still open.

**Independent Test**: Round-trip a project with a rectangle. Open a version-1 file that has no clipping field and confirm there is no rectangle and the version is still 1.

**Acceptance Scenarios**:

1. **Given** a rectangle, **When** the user saves and reopens the project, **Then** the same millimetres return.
2. **Given** a project file with no clipping field, **When** it is opened, **Then** it loads and no rectangle is applied.
3. **Given** a saved project, **When** its version is read, **Then** the version is unchanged from today's project files.

### Edge Cases

- A drag that does not produce a positive rectangle of at least 1 mm on each side does not replace an existing rectangle.
- The rectangle cannot be drawn or moved outside the printable area. Margins still remove anything in the margin band.
- While a plot is running, the Clip tool does not edit the rectangle.
- Delete does nothing when the Clip tool is off, so typing elsewhere is left alone.
- Circles, ellipses, and remove-inside are out of scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The preview tool strip MUST offer a Clip tool. It and the move tool MUST NOT both be active.
- **FR-002**: With the Clip tool, a drag on the printable area MUST create one keep-inside rectangle in machine millimetres. Shift MUST constrain that drag, and a corner drag, to a square when the printable area allows it.
- **FR-003**: With the Clip tool, the user MUST be able to move the rectangle and resize it from its corners. Delete and Backspace MUST remove it when the preview has focus.
- **FR-004**: The rectangle MUST be drawn as an overlay distinct from the printable-area outline. It MUST NOT be written into the plot file.
- **FR-005**: Changing the rectangle MUST update prepared strokes through the existing background preparation. The faint unclipped artwork MUST remain visible. Zoom, pan, and artwork placement MUST NOT change the rectangle's machine millimetres.
- **FR-006**: Plot, estimate, and multi-layer plot MUST use the current rectangle. With no rectangle, they MUST match today's printable-area cut.
- **FR-007**: A project file MAY include the rectangle. Missing clipping information MUST load as no rectangle. The project format version MUST stay the same.
- **FR-008**: The printable area and margins MUST still limit every prepared stroke.

### Key Entities

- **Keep-inside rectangle**: The Slice 1 window (position, width, height in machine millimetres). At most one. Absent means no extra cut.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a drag, the stored rectangle's edges match the drag in machine millimetres within 0.1 mm.
- **SC-002**: After zoom or pan, those millimetres are unchanged.
- **SC-003**: Preview preparation and plot preparation of the same layer describe the same polylines with the rectangle.
- **SC-004**: A two-layer plot applies the rectangle to both layers, and the plot files do not add a stroke for the rectangle itself.
- **SC-005**: A version-1 project without a clipping field opens, and a project with a rectangle restores it.

## Assumptions

- One rectangle only. A new drag that is large enough replaces the previous rectangle.
- The Clip tool starts off. The move tool stays the default.
- No second panel, no Apply button, and no remove-inside control in this slice.
- "Background preparation" is the existing delayed preview update. The outline follows the pointer immediately.
