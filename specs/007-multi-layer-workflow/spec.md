# Feature Specification: Multi-Layer Plot Workflow

**Feature Branch**: `007-multi-layer-workflow`

**Created**: 2026-09-16

**Status**: Draft

## Summary

Human-assisted sequential plotting of multiple checked SVG layers with mandatory pauses between
layers for physical pen/color changes.

## User Scenarios & Testing

### User Story 1 — Select layers for a job (P1)

User checks layers to include while clicking rows only changes preview.

### User Story 2 — Start with confirmation (P1)

User confirms layer count and order once before any motion.

### User Story 3 — Pause between layers (P1)

After each layer except the last, plotting stops until user clicks Continue.

### User Story 4 — Stop or failure (P1)

Stop cancels the whole job; a layer failure aborts remaining layers.

## Requirements

- **FR-001**: Checkboxes on layer rows; checked ≠ current preview selection.
- **FR-002**: Plot checked layers in document order; show order index in list.
- **FR-003**: `Plot Checked Layers` enabled when connected, document loaded, ≥1 checked, no active job/plot.
- **FR-004**: One confirmation dialog lists order before first layer.
- **FR-005**: Explicit Continue between layers; never auto-start next layer.
- **FR-006**: Pen-up safety step before pen-change wait (see research.md).
- **FR-007**: Progress as layer index of total; Stop cancels job during plot or wait.
- **FR-008**: Settings and layer list snapshotted at job start; UI locks checkboxes/settings/open during job.
- **FR-009**: Single-layer `Plot Selected Layer` unchanged in behavior.

## Success Criteria

- **SC-001**: All automated tests in slice test plan pass without hardware.
- **SC-002**: User can complete two-layer hardware smoke when device available.
- **SC-003**: pytest and ruff pass.
