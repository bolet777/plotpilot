# Feature Specification: Plot path optimization

**Feature Branch**: `012-plot-optimization`

**Created**: 2026-09-20

**Status**: Draft

**Input**: Add optional AxiDraw-native path reordering to reduce pen-up travel without changing artwork.

## User Scenarios & Testing

### User Story 1 - Enable optimization for faster plots (Priority: P1)

A user opens an SVG with paths in inefficient order, enables “Optimize path order” in Plot Settings, and plots a layer. The plot completes with the same visible result but potentially less pen-up travel.

**Why this priority**: Core value of the slice.

**Independent Test**: Toggle setting, start plot, verify axicli receives `-G1` when enabled and no `-G` when disabled (automated).

**Acceptance Scenarios**:

1. **Given** optimization is off, **When** the user plots a layer, **Then** the plot command omits `-G` (unchanged from prior behavior).
2. **Given** optimization is on, **When** the user plots a layer, **Then** the plot command includes `-G1`.
3. **Given** any setting, **When** plotting, **Then** the original SVG on disk is not modified.

---

### User Story 2 - Persist preference (Priority: P2)

The user enables optimization, restarts PlotPilot, and the choice is restored.

**Independent Test**: QSettings round-trip tests.

**Acceptance Scenarios**:

1. **Given** optimization enabled and saved, **When** the app reloads settings, **Then** the checkbox remains checked.
2. **Given** user clicks Reset to defaults, **When** settings reload, **Then** optimization is off.

---

### User Story 3 - Multi-layer workflow (Priority: P2)

During assisted multi-layer plotting, each layer plot uses the optimization setting snapshot from job start.

**Independent Test**: Multi-layer service tests with fake backend.

**Acceptance Scenarios**:

1. **Given** optimization on at job start, **When** each layer plots, **Then** every axicli invocation includes `-G1`.
2. **Given** a job in progress, **When** the user toggles optimization in the UI, **Then** the active job’s commands are unchanged.

---

### Edge Cases

- Invalid stored reordering value: reset to defaults (consistent with other plot settings).
- Optimization does not start plotting or motion by itself.
- Stop/cancel/safe-home behavior unchanged.

## Requirements

### Functional Requirements

- **FR-001**: Plot Settings MUST expose an optional “Optimize path order” control (default off).
- **FR-002**: When enabled, plot commands MUST pass axicli `-G1` (Basic reorder); when disabled, MUST omit `-G`.
- **FR-003**: Setting MUST persist via existing QSettings mechanism and clear on reset.
- **FR-004**: Single-layer and multi-layer plots MUST honor a snapshot of plot settings at job start.
- **FR-005**: The application MUST NOT write optimized SVG replacements to disk in this slice.

### Key Entities

- **PlotSettings**: extended with optional path reordering override (`None` = omit flag, `1` = basic reorder when user enables optimization).

## Success Criteria

- Users can turn path optimization on/off before plotting.
- Automated tests verify argv generation and persistence without hardware.
- Fast test suite and ruff pass after implementation.

## Assumptions

- axicli 3.9.6 semantics per `specs/012-plot-optimization/research.md`.
- Checkbox maps to `-G1` only; full reversal (`-G2`) deferred unless combo is added later.

## Out of Scope

- vpype, SVG rewriting, estimate/compare UI, custom planners, hardware tests in CI.
