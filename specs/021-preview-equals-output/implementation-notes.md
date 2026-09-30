# Implementation notes — 021 preview equals output

## Files

| Area | Module |
|------|--------|
| Prepare preview state | `services/preview_prepared_service.py` |
| Render prepared + context | `ui/preview_widget.py` |
| Orchestration + debounce | `ui/main_window.py` |
| Parity tests | `tests/test_preview_plot_parity.py` |

## API

- `build_prepared_layer_preview(document, layer, plot_settings, transform, fallback)` returns `PreparedLayerPreview` with context SVG, optional `PreparedPlotSvg`, diagnostics, and status lines.
- `LayerPreviewWidget.set_prepared_plot(prepared_svg=..., error_message=..., status_lines=...)` loads machine-space SVG into a second `QSvgRenderer`.

## B4

ViewBox-less documents: preview displays the prepared path bbox in CSS-px mm (via plot pipeline), not Qt’s independent 90 dpi SVG layout.

## B9

Documents with `preserveAspectRatio` meet: preview renders prepared square bbox `(50,0)–(150,100)` on a 200×100 mm page, not a stretched page rectangle.

## U5

`count_layer_content` scans isolated layer SVG for stroke shapes, fill-only shapes, text, and images. Status lines surface concise warnings; stroke candidates that fail clipping/preparation increment “not plottable” when detectable.
