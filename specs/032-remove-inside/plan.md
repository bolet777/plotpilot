# Implementation Plan: Remove Inside

**Branch**: `032-remove-inside` | **Date**: 2026-10-13

## Summary

After the printable Liang–Barsky pass, subtract the current rectangle or ellipse. The inside of a convex shape is still one span; the kept result is the complement, so one segment can become two polylines. The walker flushes between those two. Keep-inside rectangles still use `overlap_clip_rect`.

The clip tool shows In and Out once a shape exists. The project file stores `clipping.mode` only for remove-inside. Version stays 1.

## Technical context

Python 3.12, PySide6, no new dependencies. The span split lives in `plot_viewport.py` next to the existing walker.
