# Feature Specification: Plot Selected Layer

**Feature Branch**: `005-plot-selected-layer`

**Created**: 2026-09-16

**Status**: Draft

**Input**: Plot only the currently selected SVG layer on a connected AxiDraw with confirmation and stop.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plot one layer (Priority: P1)

User confirms and plots the selected layer only; preview and other layers are unchanged.

### User Story 2 - Safety and control (Priority: P1)

No plot without confirmation; Stop cancels an active plot; UI stays responsive.

### User Story 3 - Unchanged SVG workflow (Priority: P1)

Open, layers, and preview work regardless of plotter/plot state.

## Requirements *(mandatory)*

- **FR-001**: Plot Selected Layer control with physical-motion confirmation.
- **FR-002**: Isolated layer SVG via temp file → external `axicli`.
- **FR-003**: Validate root width/height before plotting; refuse ambiguous sizes.
- **FR-004**: Plot and stop off UI thread; subprocess lifecycle managed in backend.
- **FR-005**: No multi-layer automation, settings panel, or path optimization.

## Success Criteria *(mandatory)*

- **SC-001**: Selected layer only; document tree unchanged in tests.
- **SC-002**: pytest and ruff pass without hardware.
- **SC-003**: Explicit user action required for XY motion.
