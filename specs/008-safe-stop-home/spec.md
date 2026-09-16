# Feature Specification: Safe Stop and Home

**Feature Branch**: `008-safe-stop-home`

**Created**: 2026-09-16

**Status**: Draft

## Summary

When the user stops plotting (single layer, multi-layer, or during pen-change wait), PlotPilot
cancels any active `axicli` plot process, then runs a fixed cleanup sequence: raise pen, walk to
the enable-origin position, disable XY motors.

## Requirements

- **FR-001**: Stop uses existing SIGINT → terminate → kill plot cancellation.
- **FR-002**: After the plot subprocess exits, run in order: `raise_pen`, `walk_home`, `disable_xy`.
- **FR-003**: Never call `lower_pen` in the stop sequence.
- **FR-004**: Applies to single-layer plot, multi-layer active plot, and stop while waiting for pen change.
- **FR-005**: `walk_home` runs only after successful `raise_pen`; `disable_xy` only after successful `walk_home`.
- **FR-006**: UI shows cleanup progress; plotting controls disabled during cleanup.
- **FR-007**: UI must not claim home or motors disabled unless the corresponding command succeeded.
- **FR-008**: Cleanup orchestration lives in `PlotterService`, not `MainWindow`.
- **FR-009**: Repeated Stop clicks are coalesced; no duplicate cleanup commands.

## Success Criteria

- **SC-001**: Automated tests cover ordering, coalescing, and failure handling.
- **SC-002**: pytest and ruff pass.
