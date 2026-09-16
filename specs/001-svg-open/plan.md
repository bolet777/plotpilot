# Implementation Plan: Open SVG File

**Branch**: `001-svg-open` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-svg-open/spec.md`

## Summary

Add **File → Open SVG…** (**Cmd+O**) with a native `.svg` picker. Successful selection
loads file content into a single in-memory `SvgDocument` (path, name, raw text, parsed root).
Validation uses the Python standard library only (`xml.etree.ElementTree`). UI delegates to
`SvgLoader`; parsing helpers live under `plotpilot/svg/` with no Qt imports.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: PySide6 (UI only); stdlib `xml.etree.ElementTree` for parsing

**Storage**: In-memory only (no persistence this slice)

**Testing**: pytest unit tests for loader/parser; existing smoke tests unchanged

**Target Platform**: macOS desktop (primary); portable core logic

**Project Type**: Desktop app (`src/plotpilot/`)

**Performance Goals**: N/A for slice (single-file open)

**Constraints**: No SVG libraries, no plotter code, no preview rendering

**Scale/Scope**: One active document; replace on success only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
|-----------|--------|
| UI does not talk to hardware | Pass — no plotter code |
| SVG/prep outside UI | Pass — parse in `svg/`, orchestration in `services/` |
| Testable without hardware | Pass — unit tests on loader/parser |
| Minimal slice scope | Pass — open + validate + display name only |
| Clarity over abstraction | Pass — dataclass + functions, no extra frameworks |

## Project Structure

### Documentation (this feature)

```text
specs/001-svg-open/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── svg-loader.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/plotpilot/
├── models/svg_document.py
├── svg/parse.py
├── services/svg_loader.py
└── ui/main_window.py

tests/
├── fixtures/
│   ├── valid_basic.svg
│   ├── malformed.xml
│   └── not_svg.xml
├── test_svg_parse.py
└── test_svg_loader.py
```

**Structure Decision**: Single Python package layout per existing `docs/ARCHITECTURE.md`.
Parsing in `svg/`; file read + model assembly in `services/svg_loader.py`.

## Complexity Tracking

No constitution violations requiring justification.
