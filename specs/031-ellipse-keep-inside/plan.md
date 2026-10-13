# Implementation Plan: Ellipse Keep-Inside

**Branch**: `031-ellipse-keep-inside` | **Date**: 2026-10-13

## Summary

Add `ClipEllipse` and a unit-circle segment clip that runs after the printable Liang–Barsky pass. Rectangles keep `overlap_clip_rect`. The clip tool gains a rectangle/ellipse choice. Shift on an ellipse draws a circle. The project file gains an optional `clipping.ellipse` object on version 1.

## Technical context

Python 3.12, PySide6, no new dependencies. Geometry stays in `src/plotpilot/geometry/ellipse_clip.py`.

## Project structure

- `src/plotpilot/models/clip_shape.py` — ellipse value, drag helpers
- `src/plotpilot/geometry/ellipse_clip.py` — intersection
- `src/plotpilot/geometry/plot_viewport.py` — second cut, rectangle fast path unchanged
- Preview widget and workspace — kind, handles, overlay
- Project file — optional ellipse object
- `tests/test_ellipse_keep_inside.py`
