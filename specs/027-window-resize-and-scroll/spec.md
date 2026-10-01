# Feature Specification: Resizable window and scrollable content

**Feature Branch**: `027-window-resize-and-scroll`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Make the PlotPilot main window usable on smaller screens and at reduced window sizes, with scrolling when the content does not fit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reach every control in a short or narrow window (Priority: P1)

A plotter operator on a laptop, or anyone who has made the window short, can still reach the layer list, the preview, the position and scale controls, and every plotter action (including estimate, plot, stop, home, and motors off).

**Why this priority**: Bottom controls are currently unreachable when the window is taller than the screen, which blocks plotting.

**Independent Test**: Shrink the window well below its preferred size and confirm every control is still reachable by scrolling. Enlarge it again and confirm scrolling is no longer required.

**Acceptance Scenarios**:

1. **Given** the main window is open, **When** the user shortens it below the height of the full layout, **Then** a vertical scrollbar appears only as needed and scrolling reveals the plotter controls at the bottom.
2. **Given** the window is narrower than the control rows, **When** the user looks for a clipped button, **Then** a horizontal scrollbar appears and those controls can be scrolled into view instead of being cut off.
3. **Given** a window large enough for the whole layout, **When** the user is not scrolling, **Then** scrollbars stay hidden and the preview still takes the spare space.

---

### User Story 2 - Open at a size the screen can show (Priority: P2)

The window opens at about 900×560 when the screen has room, and smaller when the usable screen is smaller, without covering the menu bar or Dock.

**Why this priority**: A window that opens larger than the screen hides the same controls before the user has resized anything.

**Independent Test**: Compare the launch size with the screen’s usable area (menu bar and Dock already excluded).

**Acceptance Scenarios**:

1. **Given** a screen larger than 900×560, **When** PlotPilot starts, **Then** the window opens at about 900×560 and can still be enlarged.
2. **Given** a smaller usable screen, **When** PlotPilot starts, **Then** the window opens inside that usable area.
3. **Given** the window has been open, **When** the screen configuration changes, **Then** PlotPilot does not keep resizing itself.

---

### User Story 3 - Scrolling stays predictable (Priority: P3)

Startup and opening a drawing leave the view at the top. Changing plot settings or loading a file does not jump the view to the bottom. The layer list keeps its own scrolling when the list is long.

**Why this priority**: A global scrollbar that moves on its own makes the plotter controls hard to find again.

**Independent Test**: Open a drawing and change a setting while scrolled, and confirm the scroll position stays put. Scroll the layer list on its own when it overflows.

**Acceptance Scenarios**:

1. **Given** a fresh launch, **When** the window first appears, **Then** the content is scrolled to the top-left.
2. **Given** the user has not scrolled, **When** they open an SVG, **Then** the view stays at the top.
3. **Given** a scrolled window, **When** they change plot settings, **Then** the scroll position does not jump.

---

### Edge Cases

- Usable screen smaller than the sensible minimum: the minimum shrinks to the usable screen so the window can still be shown.
- Very short and very narrow at the same time: both scrollbars can appear together; no control is permanently off-screen.
- Maximize, restore, then shrink: the window remains resizable and scrollbars follow the new size.
- Long layer names: the layer list stays visible and can scroll its own names; it does not force the whole window to stay wide.
- Preview keeps its proportions when the area around it grows or shrinks, and does not add a second scrollbar of its own.
- Trackpad and mouse-wheel scrolling use the system scrollbars, including horizontal trackpad scrolling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The main window MUST remain freely resizable. It MUST NOT use a fixed width or height.
- **FR-002**: The window MUST use only a modest minimum size so the user can make it substantially smaller than the preferred 900×560 size.
- **FR-003**: When the content is taller than the visible area, a vertical scrollbar MUST appear. When the content is wider, a horizontal scrollbar MUST appear. Scrollbars MUST stay hidden when the content fits.
- **FR-004**: At a size large enough for the layout, the preview MUST still receive most of the spare space, and controls MUST NOT collapse or overlap.
- **FR-005**: Plotter settings, estimate, plot, stop, home, motors off, progress, and multi-layer controls MUST remain reachable by scrolling when the window is short.
- **FR-006**: Position, scale, numeric fields, presets, reset actions, and the plot-area row MUST remain fully reachable when the window is narrow. They MAY reflow or rely on horizontal scrolling; they MUST NOT be clipped with no way to reach them.
- **FR-007**: The preview MUST keep a modest minimum size, expand when space exists, and preserve artwork proportions. Its minimum MUST NOT force the window larger than the screen.
- **FR-008**: The layer list MUST stay usable and readable. It MUST NOT force the window to stay as wide as the full layout.
- **FR-009**: Launch size MUST be about 900×560 when the usable screen is at least that large, and MUST be clamped to the usable screen otherwise (menu bar and Dock already excluded). The app MUST NOT resize itself again after launch.
- **FR-010**: The layer list MUST keep its own scrolling when it has more rows than fit. Page scrolling MUST be available for the rest of the window without a custom scrollbar appearance.
- **FR-011**: Scroll position MUST start at the top-left, stay put when a drawing is opened or settings change, and be preserved across an ordinary resize when that is practical. Scroll position MUST NOT be saved between sessions.

### Key Entities

- **Main window**: The single desktop window. Resizable, with a modest minimum and a screen-aware launch size.
- **Page content**: The existing layout (layers, preview, transform controls, plotter controls). Scrolls as one page when it does not fit.
- **Layer list**: A list that scrolls on its own when its rows overflow, inside the page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a screen whose usable area is at least 900×560, the window opens at that size (within the window frame) and can be resized both larger and substantially smaller.
- **SC-002**: On a shorter or narrower usable screen, the entire window frame lies inside that usable area at launch.
- **SC-003**: After shrinking below the content size, a person can bring every bottom plotter control and every transform control into view within one scrolling action in the needed direction.
- **SC-004**: After enlarging until the content fits, both scrollbars are hidden and the preview is larger than its minimum.
- **SC-005**: Opening a drawing and changing a plot setting does not move the page away from the top when the user has not scrolled.

## Assumptions

- Preferred launch size stays 900×560, matching the size the window already requests.
- A sensible minimum is about 480×320, reduced further only when the usable screen is smaller than that.
- Scrolling is a fallback. The large-window arrangement of layers, preview, and plotter controls stays as it is.
- System scrollbars are used, including light and dark appearance and trackpad scrolling. No custom-drawn scrollbars.
- Plot geometry, plot behavior, and the project file format are unchanged.
- No docking, detachable windows, or phone-style responsive redesign.
