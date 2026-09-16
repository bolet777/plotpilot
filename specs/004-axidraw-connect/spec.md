# Feature Specification: AxiDraw Connection and Pen Controls

**Feature Branch**: `004-axidraw-connect`

**Created**: 2026-09-16

**Status**: Draft

**Input**: First plotter integration — detect AxiDraw, show status, manual Pen Up/Down only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See plotter status (Priority: P1)

The user sees whether an AxiDraw is available without the app moving the machine on launch.

**Acceptance Scenarios**:

1. **Given** PlotPilot starts with no plotter attached, **When** the window opens, **Then** the plotter
   section shows a disconnected/not-connected state and pen controls are disabled.
2. **Given** the app is open, **When** the user taps Refresh, **Then** status updates to connected or
   disconnected with a clear message.

---

### User Story 2 - Manual pen control (Priority: P1)

When connected, the user can raise or lower the pen explicitly; no plotting or XY motion.

**Acceptance Scenarios**:

1. **Given** a connected AxiDraw, **When** the user chooses Pen Up, **Then** the pen raises.
2. **Given** a connected AxiDraw, **When** the user chooses Pen Down, **Then** the pen lowers.
3. **Given** no connection, **When** the user views the plotter section, **Then** pen buttons are disabled.

---

### User Story 3 - SVG workflow unchanged (Priority: P1)

Opening and previewing SVGs works regardless of plotter state or errors.

**Acceptance Scenarios**:

1. **Given** plotter detection fails, **When** the user opens an SVG, **Then** layers and preview behave as before.

---

### Edge Cases

- AxiDraw CLI not installed (`axicli` missing from PATH).
- USB disconnected mid-command.
- Multiple named units: report count; use default first unit behavior of official CLI.
- Rapid Refresh clicks must not stack unbounded detection jobs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Plotter section in main window with status, Refresh, Pen Up, Pen Down.
- **FR-002**: Passive startup — no automatic detection or pen motion on launch.
- **FR-003**: Device logic behind plotter abstraction; UI uses services only.
- **FR-004**: Hardware work off the UI thread; errors surfaced without crashing.
- **FR-005**: No SVG plotting, XY moves, pause/resume, or device profiles in this slice.

### Key Entities

- **Plotter status**: connection state, optional device label, user-facing message, backend hint.

## Success Criteria *(mandatory)*

- **SC-001**: pytest and ruff pass without hardware.
- **SC-002**: App launches and opens SVGs with no plotter attached.
- **SC-003**: Connected device can be detected via Refresh; pen commands work when hardware present.

## Assumptions

- Users install Evil Mad Scientist AxiDraw software separately; PlotPilot invokes `axicli` only.
- Detection uses official CLI manual modes that do not command XY walks.
