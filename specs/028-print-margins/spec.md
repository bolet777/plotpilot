# Feature Specification: Editable Print Margins

**Feature Branch**: `028-print-margins`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Add editable print margins inside the physical work area so preview, clipping, estimate, and physical plot all use an inner safe printable area."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plot only inside a safe printable area (Priority: P1)

A plotter user keeps a blank margin inside the machine's physical travel so the pen does not run to the mechanical edge. PlotPilot still shows and respects the full machine work area, and it refuses to send any stroke that falls in the margin to the plotter.

**Why this priority**: Sending ink into the margin is the failure this feature exists to prevent. Preview, estimate, and the physical plot must agree on that inner limit.

**Independent Test**: Place a line that spans the full work area, set 10 mm horizontal and vertical margins, and confirm the prepared geometry (preview and plot file) runs only from the inner edges.

**Acceptance Scenarios**:

1. **Given** a 300 × 217.9 mm work area and margins of 10 mm horizontal and 10 mm vertical, **When** artwork is prepared, **Then** the printable area is x = 10 to 290 mm and y = 10 to 207.9 mm (280 × 197.9 mm), and no prepared point lies outside that rectangle.
2. **Given** a horizontal line from x = 0 to x = 300 on that work area, **When** it is prepared with 10 mm horizontal margins, **Then** the plotted line is x = 10 to 290 and the machine origin is unchanged.
3. **Given** artwork that leaves the printable area and later re-enters, including curves, **When** it is prepared, **Then** only the portions inside the printable rectangle are kept.
4. **Given** scale 200% or a translation that pushes artwork into a margin, **When** it is prepared, **Then** the overflow is clipped and the artwork is not auto-fitted or auto-centered.
5. **Given** margins of 0 mm, **When** artwork is prepared, **Then** the printable area equals the physical work area.
6. **Given** the user presses Estimate after changing margins, **When** the estimate runs, **Then** it measures the geometry clipped to the current printable area, not strokes that sit in the margin.

---

### User Story 2 - See and edit the margin (Priority: P2)

The user edits two margin values next to the work-area readout and immediately sees both the machine boundary and the inner safe area, plus the resulting printable size.

**Why this priority**: Without visible, editable margins the safe area cannot be checked before a plot.

**Independent Test**: Change horizontal and vertical margins and confirm the on-screen printable size and the inner boundary update without opening a separate settings window.

**Acceptance Scenarios**:

1. **Given** a loaded drawing, **When** the user looks at the work-area information, **Then** they see the physical plot area, horizontal and vertical margin fields (default 10.0 mm), and the printable width and height.
2. **Given** those fields, **When** the user types or steps a value, **Then** the value accepts 0.1 mm precision, steps of about 1 mm, and 0 mm, and the printable size updates immediately.
3. **Given** the preview, **When** both areas are shown, **Then** the outer rectangle is the existing machine work-area boundary and the inner rectangle is a visually distinct printable boundary that remains readable in light and dark appearance.
4. **Given** artwork crossing a margin, **When** the preview is shown, **Then** faint source context may still extend into the margin while the prepared plotted strokes stop on the printable boundary.
5. **Given** a work area that cannot support the typed margin (for example 110 mm horizontal on a 210 mm width), **When** the user edits the field, **Then** the control does not allow a margin that would erase the printable width or height.

---

### User Story 3 - Remember margins per session (Priority: P3)

Plain drawings use the user's saved default margins. A project file stores its own margins, restores them on open, and does not overwrite the global defaults. Older project files still open.

**Why this priority**: Margins are part of how a job is set up. They must survive restart and must not surprise someone who opens an older project.

**Independent Test**: Save a project with non-default margins, change the global defaults, reopen the project, and confirm the project values return and the global defaults are unchanged. Open a project file that has no margin fields and confirm 10 mm / 10 mm.

**Acceptance Scenarios**:

1. **Given** a plain SVG session, **When** the user changes margins and restarts, **Then** those values are the new defaults for plain sessions.
2. **Given** an open project, **When** the user changes either margin, **Then** the project is marked unsaved. **When** they save and reopen, **Then** the margins match what was saved and the project is clean.
3. **Given** a project file with no margin fields, **When** it is opened, **Then** margins are 10 mm horizontal and 10 mm vertical.
4. **Given** a project file with impossible or non-numeric margins, **When** it is opened, **Then** PlotPilot shows a clear validation error and does not apply the bad values.
5. **Given** an active project session, **When** margins change, **Then** the global defaults are left unchanged.

---

### Edge Cases

- Negative, blank, or non-numeric margins are rejected rather than applied.
- Margins that would leave zero or negative printable width or height are rejected. A small positive printable size must remain.
- Changing A4/A3, portrait/landscape, or an explicit machine model updates the printable size from the new work-area dimensions and the same margin pair. There is no extra rule per paper size.
- Changing margins does not re-read or re-flatten the source drawing. Placement and clipping are recomputed from the drawing that is already flattened.
- The physical machine travel limits do not change. The printable area is an inset of that rectangle, not a smaller machine and not a shifted drawing.
- Four independent side margins, auto-center, auto-fit, and printer calibration are out of scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: PlotPilot MUST keep the physical machine work area unchanged and MUST define an inner printable area inset by the horizontal margin on the left and the right and by the vertical margin on the top and the bottom.
- **FR-002**: Default margins MUST be 10 mm horizontal and 10 mm vertical. Zero margins MUST be allowed.
- **FR-003**: The printable area MUST be stored as an origin plus size (x, y, width, height) in machine millimeters. It MUST NOT be represented as a width and height that start at the machine origin.
- **FR-004**: Preview, clipping, estimate, and the plot sent to the machine MUST all use that same printable rectangle. Prepared coordinates MUST stay in real machine space.
- **FR-005**: Every prepared coordinate MUST lie inside the printable rectangle within the existing numerical tolerance. The machine work area remains the outer mechanical limit.
- **FR-006**: Users MUST edit horizontal and vertical margins next to the work-area information, without a separate settings dialog. The printable dimensions MUST update when margins, paper size, orientation, or machine model change.
- **FR-007**: The preview MUST show the physical work area and the inner printable area as two distinct boundaries. Prepared strokes MUST stop at the printable boundary. Faint source context MAY remain visible in the margin.
- **FR-008**: Position and scale MUST keep their current meaning. They move or resize artwork relative to the printable area. They MUST NOT change the work area, and PlotPilot MUST NOT auto-fit or auto-center.
- **FR-009**: Margin changes MUST reuse already-flattened drawing geometry and MUST NOT block the interface with a fresh parse or flatten.
- **FR-010**: Plain sessions MUST persist margins as global defaults. Project sessions MUST store margins in the project and MUST NOT overwrite those global defaults. Missing margins in an older project MUST mean 10 mm / 10 mm. The project format version stays compatible with existing files.
- **FR-011**: Changing either margin on an open project MUST mark that project unsaved. Opening a project MUST restore its margins. Saving MUST clear the unsaved mark as it does today.
- **FR-012**: Impossible margins (non-finite, negative, or too large for the current work area) MUST be rejected with a clear validation error, or prevented by the editor's range. They MUST NOT be applied silently and MUST NOT crash the application.

### Key Entities

- **Print margins**: One horizontal inset (used on both left and right) and one vertical inset (used on both top and bottom), in millimeters. Default 10 and 10.
- **Physical work area**: The machine travel rectangle, origin at the machine home, unchanged by this feature.
- **Printable area**: The inner rectangle where plotting is allowed. Its origin is offset by the margins; its size is the work area minus both insets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a 300 × 217.9 mm work area with 10 mm margins, prepared geometry for a full-width line is exactly the span 10 mm to 290 mm horizontally and the matching vertical inset, and 100% of prepared points fall inside the printable rectangle.
- **SC-002**: A user can set margins, including 0 mm, and see the updated printable size without leaving the main window.
- **SC-003**: Preview strokes and the geometry sent for estimate and plot match for the same margins, position, and scale, including 200% scale and artwork moved into each margin.
- **SC-004**: Changing margins on an already loaded drawing does not require parsing the source file again.
- **SC-005**: An older project file with no margin fields opens with 10 mm / 10 mm margins. A project opened after the global defaults were changed still shows the project's own margins, and those global defaults are unchanged.
- **SC-006**: A4 portrait, A4 landscape, A3 portrait, A3 landscape, and an explicit machine model all produce the printable rectangle from the same margin rule and that page's dimensions.

## Assumptions

- Horizontal margin means the same inset on the left and the right. Vertical margin means the same inset on the top and the bottom. Independent per-side margins are a later feature.
- A printable width and height of at least 0.1 mm is the smallest area the editor will allow.
- Existing numerical tolerance for prepared coordinates remains in force.
- "Legacy project" means a current-version project file that simply omits margin fields. The file version does not increase.
- Estimate is refreshed when the user asks for an estimate, using the margins in effect at that moment.
- Light and dark appearance must both keep the two boundaries distinguishable. The existing machine-boundary color may stay; the new inner boundary must not rely on a color that disappears in one appearance.
