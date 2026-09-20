# Feature Specification: Plot progress feedback

**Feature Branch**: `014-plot-progress`  
**Created**: 2026-09-20  
**Status**: Implemented  
**Input**: Clear plotting progress/status during single- and multi-layer jobs without fake precision.

## User Scenarios & Testing

### User Story 1 - Single-layer plot status (Priority: P1)

While a layer plots, the user sees the layer name, elapsed time, optional estimated progress
(labeled estimated), optional remaining time, and Stop remains available.

**Acceptance Scenarios**:

1. **Given** a connected plotter and selected layer, **When** plot starts, **Then** elapsed time updates and Stop is enabled.
2. **Given** a preview estimate succeeds, **When** plotting, **Then** progress shows as estimated and reaches 100% only on success.
3. **Given** preview fails, **When** plotting, **Then** elapsed time still shows and plot completes normally.

### User Story 2 - Multi-layer context (Priority: P1)

During multi-layer jobs, show layer X of N, next layer name when known, and pause progress during pen-change wait.

**Acceptance Scenarios**:

1. **Given** a multi-layer job, **When** layer 2 plots, **Then** UI shows "Layer 2 of N".
2. **Given** pen-change wait, **When** user has not continued, **Then** layer progress timer does not advance.

## Requirements

- FR-1: Show active plot state, layer name, elapsed MM:SS (or H:MM:SS).
- FR-2: Estimated percentage only from preview duration; label as estimated.
- FR-3: Never show 100% before backend success; cap running estimate at 99%.
- FR-4: Estimation failure must not block plotting.
- FR-5: Safe stop behavior unchanged; show stopping state.
- FR-6: No UI-thread blocking for preview.

## Success Criteria

- Users can tell a plot is active and which layer is running within one glance.
- Estimated progress is never presented as exact machine position.
