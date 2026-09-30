# Feature Specification: Canonical SVG page geometry (B3, B5, B10)

**Feature Branch**: `019-canonical-svg-geometry`  
**Created**: 2026-09-30  
**Status**: In review  
**Input**: Audit roadmap step 3 — one authoritative user-space → mm mapping; no regex/content heuristics.

## Root causes

### B3 — viewBox-less unit heuristic

Without a root `viewBox`, the pipeline inferred user units from geometry magnitude and root width/height regex values. Small coordinates were treated as millimeters; large coordinates flipped to viewport pixels. SVG defines viewBox-less user units as **CSS pixels** (`1 px = 25.4/96 mm`), independent of other elements.

### B5 — layer isolation + regex parsing

Isolated layer SVG is serialized with prefixed tags (e.g. `ns0:svg`). Global regexes for root `width`/`height` failed on isolated documents, so fallback viewBox dimensions differed from the whole document and scale changed.

### B10 — global viewBox regex

A document-wide `viewBox=` search matched nested `<marker viewBox="…">` (or symbol) attributes instead of the root `<svg>` viewBox, rescaling the page incorrectly.

## Canonical unit rules

| Root state | User-space semantics | Mapping to mm |
|------------|---------------------|---------------|
| No `viewBox` | CSS px | `coord × (25.4/96)` |
| Has `viewBox` | viewBox user units (via svgelements viewport pixels) | viewBox → page using physical `width`/`height` mm |

Physical page size always comes from root `width` and `height` attributes (mm, cm, in, pt, px, unitless).

## Architecture

- **`SvgPageGeometry`** (`src/plotpilot/svg/page_geometry.py`): Qt-free model parsed from the root XML element only.
- **`plot_viewport._SvgToMm`**: consumes `SvgPageGeometry`; no regex viewBox/width parsing; no `_coordinates_are_viewport_pixels`.
- **Layer preview**: namespace registration for stable serialization; geometry uses Element attributes, not tag spelling.

## Out of scope (later tasks)

B4, B6, B7, B8, B9, B12 — preview DPI, CSS isolation, nested layers, fill-only, preserveAspectRatio preview, auto-rotate.

## Success criteria

- Golden XFAIL removed for B3, B5, B10.
- Remaining XFAIL: B6, B7 (and unrelated known bugs).
- Fast suite and non-hardware pytest under 15s; ruff clean.
