# PlotPilot Constitution

Engineering principles for PlotPilot, an open-source macOS application for
controlling pen plotters. This document governs SpecKit slices, reviews, and
implementation choices.

## Core Principles

### I. macOS-first, portable where it costs little

PlotPilot targets macOS first (packaging, UX, and primary testing). Avoid
macOS-only APIs in core logic when a portable alternative is equally clear.
Platform-specific code belongs in thin adapters, not in SVG or plotting logic.

### II. Layered boundaries (NON-NEGOTIABLE)

The UI must not talk to hardware or embed plotting protocols. SVG parsing,
preview geometry, and plot job preparation live outside the UI. Device I/O lives
behind a plotter abstraction so AxiDraw is one implementation, not the whole
system.

### III. Testable without hardware

SVG and plotting preparation must be unit-testable with no plotter attached.
Hardware integration tests are optional and explicit; they never block default CI.

### IV. SpecKit slices, minimal scope

Each feature is delivered as one numbered SpecKit slice (`specs/NNN-slug/`).
Implement only what the current spec requires. No speculative frameworks, no
background daemons, no premature optimization.

### V. Clarity over abstraction

Prefer readable modules and direct dependencies over indirection. Introduce an
interface only when a second plotter or a hard test boundary requires it.
Keep third-party dependencies minimal and justified.

## Technology & structure

- **Language**: Python 3.12
- **UI**: PySide6 (Qt)
- **Plotters**: AxiDraw via dedicated adapter(s) under `plotpilot/plotter/` (future)
- **Layout**: `src/plotpilot/` with `app`, `ui`, `svg`, `plotter`, `services`, `models`
- **Packaging**: PyInstaller `.app` (later); GitHub Actions builds (later)

## Quality gates

- **Tests**: `pytest` for logic; UI smoke tests only where they add signal
- **Lint/format**: `ruff` check and format on `src/` and `tests/`
- **Reviews**: Verify boundary rules (UI vs services vs plotter) on every slice

## Development workflow

1. Ratify or amend this constitution when principles change.
2. For each feature: `/speckit-specify` → plan → tasks → implement → converge.
3. Use the git extension feature branches (`NNN-slug`) aligned with `specs/NNN-slug/`.
4. Do not merge slice work without passing tests and ruff.

## Governance

This constitution overrides ad-hoc decisions. Amendments update this file with
a version bump and brief rationale. Complexity beyond these rules requires an
explicit note in the feature plan.

**Version**: 1.0.0 | **Ratified**: 2026-09-16 | **Last Amended**: 2026-09-16
