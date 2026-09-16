# Implementation Plan: SVG Layer Preview

**Branch**: `003-layer-preview` | **Spec**: [spec.md](./spec.md)

## Summary

Pure `build_layer_preview_svg(document, layer) -> str` in `svg/preview.py` (deep-copy layer
subtree + root geometry attrs + full `<defs>`). `LayerPreviewWidget` uses `QSvgRenderer` (PySide6
QtSvg, already available). `preview_service` wraps builder for UI. Split layout in `main_window`.

## Technical Context

- **Rendering**: `PySide6.QtSvg.QSvgRenderer` — no new project dependency
- **Tests**: stdlib assertions on generated SVG strings; Qt widget/window tests for selection flow

## Constitution Check

UI → services → svg; no mutation of `SvgDocument.root`; no plotter code.
