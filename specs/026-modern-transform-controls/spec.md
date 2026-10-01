# 026 — Modern artwork transform controls

## Problem

Position and scale are edited only through spinboxes in a single crowded row. Large jumps are tedious, fine adjustment is fiddly, and the separate “Artwork — X/Y/Scale” status line duplicates what the controls already show. Ranges (±2000 mm) are unrelated to the active plot area, so sliders would feel arbitrary without rework.

## Interaction model

- **POSITION**: horizontal slider for fast moves plus mm spinbox (0.1 mm) for precision; Reset X / Reset Y per axis; optional double-click on an axis slider resets that axis to zero.
- **SCALE**: horizontal slider mapped to existing `ArtworkTransform` scale limits, percent spinbox, preset buttons at 50 / 100 / 150 / 200 % when in range; preset highlighted only on exact match.
- **Footer**: plot-area summary and Reset All (X=0, Y=0, scale=100%).
- Sliders and numeric fields stay synchronized. One authoritative `ArtworkTransform`; preview drag updates controls without re-entering the control→preview path.
- Slider callbacks stay lightweight and use the interactive preview pipeline (immediate context move, deferred prepared geometry).

## Slider ranges

- X: approximately −width → +width mm of the active work area.
- Y: approximately −height → +height mm.
- Numeric mm fields may keep a wider safe range (±2000 mm).
- Changing plotter model, fallback size, or orientation updates slider ranges without changing stored transform values.

## Success criteria

- Continuous slider drag updates preview context immediately; prepared preview catches up asynchronously.
- Preview drag updates X/Y sliders and spinboxes; scale unchanged; no feedback loop.
- Project open restores control state from saved transform.
- No change to prepared plot geometry, clipping, estimates, axicli, or project file format.

## Out of scope

- Changing `ArtworkTransform` semantics, clip math, or preview-performance architecture internals.
- New persisted settings.
- Custom-painted controls or light-mode-breaking hardcoded colors.
