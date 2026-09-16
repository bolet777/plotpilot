# Feature Specification: Plot Settings

**Feature Branch**: `006-plot-settings`

**Created**: 2026-09-16

**Status**: Draft

**Input**: Persistent, compact plot settings (speeds, acceleration, model) for future layer plots without becoming a full device preferences system.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tune plot motion (Priority: P1)

User adjusts pen-down speed, pen-up speed, acceleration, and AxiDraw model; the next plot uses those values.

### User Story 2 - Defaults preserved (Priority: P1)

Fresh install or after Reset, PlotPilot does not override official axicli defaults.

### User Story 3 - Persistence (Priority: P1)

Settings survive app restart via local Qt preferences.

### User Story 4 - Safe plotting (Priority: P1)

Changing settings during an active plot does not alter the running job; controls disable while plotting.

## Requirements *(mandatory)*

- **FR-001**: Plot Settings panel with four controls and Reset to defaults.
- **FR-002**: Optional overrides (`None` = omit CLI flag); validated ranges.
- **FR-003**: QSettings persistence (Organization PlotPilot, Application PlotPilot).
- **FR-004**: Plot Selected Layer uses a settings snapshot at start.
- **FR-005**: No multi-layer queue, copies UI, vpype, profiles, or cloud sync.

## Success Criteria *(mandatory)*

- **SC-001**: Overrides appear on axicli command line; defaults do not add extra flags.
- **SC-002**: pytest and ruff pass without hardware.
- **SC-003**: Reset clears stored overrides and UI state.
