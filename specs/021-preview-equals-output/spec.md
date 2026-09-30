# 021 — Preview equals plot output

## Problem (B4, B9, D1, U5)

The UI used two visual pipelines:

- **Preview**: `QSvgRenderer` on isolated source layer SVG (Qt’s viewBox/DPI semantics).
- **Plot**: `prepare_positioned_plot_svg` → clipped machine-space SVG for axicli.

That divergence caused incorrect preview for viewBox-less CSS-px scale (B4), `preserveAspectRatio` mapping (B9), clipping/transform parity (D1), and misleading display of unplottable content (U5).

## Solution

Single source of truth for “what will plot”:

```
source layer SVG
  → canonical page geometry
  → ArtworkTransform
  → flatten / clip (prepare_positioned_plot_svg)
  → PreparedPlotSvg
       ├─ preview (authoritative, normal opacity, clipped to work area)
       └─ temp SVG → axicli (unchanged)
```

Optional faint overlay: same isolated source SVG with transform applied (context only).

## Preview mode

- Machine work area border remains visible.
- Prepared/clipped geometry is rendered at full opacity inside the work area.
- Source SVG may render faintly behind the transform (not clipped to imply plot extent).
- Status lines warn about text, images, fill-only, and other non-plottable items.

## Caching / performance

- `MainWindow` calls `build_prepared_layer_preview` when layer, transform, scale, plot settings, or fallback work area change.
- A 50 ms debounced `QTimer` batches rapid transform edits (drag/spin) so flatten/clip does not run on every `paintEvent`.
- `LayerPreviewWidget` only renders cached SVG strings; it does not compute plot geometry.

## Out of scope

- B8 fill-only product policy
- B12 auto-rotate / `-N`
- vpype migration
- axicli flag changes

## Success criteria

- Preview prepared polylines/bbox match `PreparedPlotSvg` for B4, B9, clipping, and golden parity tests.
- `./scripts/test_fast.sh` and non-hardware pytest remain green.
