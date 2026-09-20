# Feature Specification: macOS PlotPilot.app Bundle

**Feature Branch**: `010-macos-app-bundle`

**Created**: 2026-09-20

**Status**: Draft

**Input**: User description: "Bundle macOS PlotPilot.app with correct Dock name, icon, and a standard repeatable build workflow (Speckit slice)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch from Finder (Priority: P1)

A macOS user double-clicks **PlotPilot.app** in Finder (or pins it to the Dock) and the application opens with PlotPilot branding.

**Why this priority**: Running via `uv run plotpilot` shows the Python runtime in the Dock; a native `.app` is the standard macOS delivery format.

**Independent Test**: Build the app, open it from Finder, confirm the window appears and the Dock tooltip reads **PlotPilot** (not Python).

**Acceptance Scenarios**:

1. **Given** a successful build, **When** the user opens `PlotPilot.app`, **Then** the main PlotPilot window appears.
2. **Given** the app is running, **When** the user hovers the Dock icon, **Then** the label is **PlotPilot**.
3. **Given** the app is running, **When** the user views the menu bar application menu, **Then** it shows **PlotPilot**.

---

### User Story 2 - Reproducible build (Priority: P2)

A developer rebuilds the macOS application after code or icon changes using documented commands.

**Why this priority**: The bundle must stay in sync with source without manual Finder edits.

**Independent Test**: Run the documented build command twice; the second run succeeds and produces an updated `.app` under `dist/`.

**Acceptance Scenarios**:

1. **Given** a dev environment with project dependencies installed, **When** the developer runs the macOS build script, **Then** `dist/PlotPilot.app` is created or refreshed.
2. **Given** updated icons in `assets/icons/`, **When** icons are regenerated and the app is rebuilt, **Then** the new icon appears on the bundle.

---

### Edge Cases

- Build on non-macOS: build script exits with a clear message (macOS-only).
- Missing ICNS or icon assets: build fails with an actionable error.
- Stale `dist/` output: rebuild replaces the previous bundle (`--clean`).

## Requirements

- **FR-001**: Provide a standard macOS `.app` bundle named **PlotPilot.app** with `CFBundleName` and `CFBundleDisplayName` set to **PlotPilot**.
- **FR-002**: The bundle uses the project ICNS (`plotpilot.icns`) as its icon.
- **FR-003**: A single documented script builds the app into `dist/PlotPilot.app` on macOS.
- **FR-004**: Bundled resources include application icons required at runtime.
- **FR-005**: `uv run plotpilot` remains supported for development; the `.app` is the recommended way to get correct Dock branding.
- **FR-006**: PyInstaller build artifacts under `build/` and `dist/` remain gitignored; sources live under `packaging/macos/`.

## Success Criteria

- **SC-001**: After build, opening `dist/PlotPilot.app` shows **PlotPilot** in the Dock hover label.
- **SC-002**: `pytest` and `ruff` pass on the branch.
- **SC-003**: `specs/010-macos-app-bundle/quickstart.md` documents build and launch steps verifiable in under 5 minutes on macOS.

## Assumptions

- Primary packaging tool for this slice is **PyInstaller** (aligned with constitution “PyInstaller `.app` (later)” — this slice delivers the first working bundle).
- Code signing and notarization are out of scope for this slice.
- GitHub Actions release builds are a follow-up slice.
