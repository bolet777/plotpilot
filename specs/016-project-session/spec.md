# Feature Specification: Project session (.plotpilot)

**Feature Branch**: `016-project-session`  
**Created**: 2026-09-22  
**Status**: Draft  
**Input**: Native PlotPilot project/session file format for save and reopen.

## User Scenarios & Testing

### User Story 1 - Save and reopen a project (Priority: P1)

The user configures layers, position, scale, plot settings, and work area, saves a `.plotpilot` file, quits, and reopens the project to continue without manual setup.

**Independent Test**: Save Project As → relaunch → Open Project restores SVG and state.

**Acceptance Scenarios**:

1. **Given** a loaded SVG with checked layers and non-default transform, **When** the user saves `example.plotpilot`, **Then** the file is versioned JSON referencing the SVG path.
2. **Given** a saved project, **When** the user opens it after restart, **Then** the SVG loads and project-owned state is restored.

### User Story 2 - Safe failure (Priority: P1)

Malformed projects or missing SVG files must not destroy the current session.

**Independent Test**: Open bad project while a document is loaded; prior document remains.

**Acceptance Scenarios**:

1. **Given** an open document, **When** opening a project whose SVG is missing, **Then** a clear error appears and the current document stays open.
2. **Given** an open document, **When** opening invalid JSON, **Then** the current session is unchanged.

### User Story 3 - Plain SVG unchanged (Priority: P1)

Opening SVG without a project continues to use global application defaults from QSettings.

**Independent Test**: Open SVG only; no `.plotpilot` path; behavior matches pre-slice.

## Edge Cases

- Relative SVG path when project and SVG share a folder; absolute path when not.
- Layer ids in project that no longer exist in SVG → skip with status warning.
- Unsupported future `version` → friendly error, no load.
- Save Project without prior path → Save As dialog.

## Requirements

### Functional Requirements

- **FR-001**: Versioned JSON format `plotpilot-project` v1.
- **FR-002**: Persist SVG path, checked layer ids (`layer_id`), artwork transform, plot settings, preview fallback work area.
- **FR-003**: QSettings remain global defaults; project file holds per-project state.
- **FR-004**: File menu: Open Project, Save Project, Save Project As with standard shortcuts where applicable.
- **FR-005**: Transactional project load; dirty flag and window title when practical.
- **FR-006**: Never modify source SVG on save.

## Success Criteria

- Round-trip project save/open restores plotting-ready state.
- Fast test suite remains ~2–3s.
- macOS packaging can register `.plotpilot` later (documented in plan).

## Assumptions

- No embedded SVG, relink UI, autosave, or recent files in this slice.
