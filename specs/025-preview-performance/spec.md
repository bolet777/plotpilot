# 025 — Interactive preview performance

## Problem

Moving or scaling artwork, or changing the work-area orientation, froze the window on dense drawings. Each spinbox step and each drag update ran the full plot preparation on the interface thread: isolate the layer, parse it, count diagnostics, parse it again, flatten every curve, transform, clip, write an SVG, validate that SVG, and build a new renderer.

The settled preview must still match the geometry that will be plotted. Clipping rules and the final plot safety check stay as they are.

## What the user gets

- X, Y, and scale controls keep accepting steps while a new preview is computed.
- The faint source drawing moves immediately.
- The black plotted preview catches up to the latest position. An older result is never shown after a newer one.
- Changing A4/A3 or portrait/landscape reuses the already flattened drawing.
- Changing the file or the selected layer prepares that layer again.
- When the user plots, the machine still receives SVG that was flattened at 0.05 mm, clipped, and checked by the existing output validator.

## Success criteria

- On a normal drawing, a position or scale step does not re-flatten the file, and the control handler returns without waiting for that work.
- On a dense drawing, the interface keeps accepting input while the previous black preview stays visible until the latest one is ready.
- At rest, preview polylines match the polylines written into the plot SVG, within 0.01 mm, for a square, curves, a clip that exits and re-enters, translation, scale, and A4 portrait and landscape.
- The source file in memory is unchanged by preview preparation.

## Out of scope

- Changing clip math, the 0.05 mm plot tolerance, axicli arguments, or the project file format.
- vpype.
- A coarser preview while the pointer is down. Not needed for this slice; the exact tolerance is used for both preview and plot.
- Undo/redo and a visual redesign.
