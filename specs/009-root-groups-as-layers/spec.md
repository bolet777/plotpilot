# Feature Specification: Root SVG groups as layers

**Feature Branch**: `009-root-groups-as-layers`

**Status**: Implemented

## Summary

When an SVG has no Inkscape layers, treat meaningful direct child `<g>` elements of the root `<svg>` as PlotPilot layers, preserving order, naming, and colors. Otherwise fall back to a single synthetic document layer.

## Layer detection priority

1. Explicit Inkscape layers (unchanged behavior)
2. Direct root `<g>` groups with drawable content
3. Synthetic whole-document layer

## Requirements

- Inkscape layers remain authoritative when any exist; root groups are not mixed in.
- Only direct `<svg>` → `<g>` children; nested groups are not separate layers.
- Skip root groups with no drawable subtree content.
- Naming: inkscape:label, aria-label, humanized id, then `Group N`.
- Stable `layer_id` preserves raw `id` when present.
- Representative color and preview/plot isolation reuse existing pipelines.
- `SvgLayer.source` indicates INKSCAPE, ROOT_GROUP, or DOCUMENT.
