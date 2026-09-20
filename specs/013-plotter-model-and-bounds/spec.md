# Feature Specification: Plotter model and bounds preflight

**Feature**: 013-plotter-model-and-bounds

## Problem

Users can select an AxiDraw model and load SVGs with physical dimensions, but PlotPilot does not verify that the document fits the machine before motion. Oversized art or wrong model selection should be caught early.

## Goals

- Show selected model context and document physical size
- Validate page dimensions against verified model travel when model is explicit
- Block plotting when known out-of-bounds; warn when model is Default (CLI)
- No silent scale, rotate, or reposition

## User scenarios

1. User loads A4 SVG, selects AxiDraw V3/A3 → clear error before plot
2. User loads fitting SVG with explicit model → green OK status
3. User keeps Default (CLI) → warning that PlotPilot cannot pre-verify; plot still allowed
4. User changes model dropdown → bounds status updates immediately
5. Multi-layer job uses same document-level check before start

## Functional requirements

- FR1: Model table codes 1–7 with official 3.9.6 travel dimensions (see research.md)
- FR2: Bounds check uses root SVG width/height via existing dimension parser
- FR3: Explicit model → OK / OUT_OF_BOUNDS; Default → UNKNOWN_MODEL
- FR4: OUT_OF_BOUNDS blocks single and multi-layer plot starts (no axicli)
- FR5: Compact status near plot controls
- FR6: Optional hint when art would fit only if rotated (no auto-rotate)

## Success criteria

- Verified dimensions for all seven models
- Oversized known cases blocked in tests without hardware
- Existing valid flows unchanged when art fits
- Fast test suite and ruff pass

## Out of scope

Auto fit/scale/rotate/center, path geometry engine, bed overlay, auto model detect.
