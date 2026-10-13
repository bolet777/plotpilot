# Implementation notes: Interactive clip rectangle

Slice 2. The rectangle is the Slice 1 `ClipRectangle`. The preview edits it. The existing worker still cuts the strokes.

## Decisions

**Machine millimetres, clamped to the printable area.** Drags use `widget_to_mm`, which already includes zoom and pan. Shift forces equal sides and shrinks the square so it stays inside that area. A drag whose width or height is under 1 mm does not replace the current rectangle. Moving stops at the printable edges and keeps the size.

**One rectangle.** A drag that starts on a corner resizes, with the opposite corner fixed. A drag that starts inside moves it. A drag that starts elsewhere draws a new one. Delete and Backspace clear it only while the clip tool is on and the preview receives the key. The move tool and the clip tool turn each other off. Both are disabled while a plot locks the transform controls.

**The overlay is not geometry.** It is painted in `clip_outline` (`#f0a63a`), separate from the blue printable outline. Corner handles show only while the clip tool is on. The plot SVG is still the clipped strokes. There is no `clipPath` and no `QPainter` mask on the cut.

**Preview stays on the existing timer.** Each change emits `clip_rectangle_changed`. The main window marks the project dirty and starts the 50 ms preview timer. It does not invalidate `LayerGeometryCache`. Flattening still happens once per layer.

**Project version stays 1.** `clipping.rectangle` is written only when a rectangle exists. A missing key loads as no rectangle. A present but invalid block is a project error. Opening an SVG clears the rectangle. Opening a project restores it without marking the file dirty.

## Tests

`tests/test_clip_rectangle_tool.py` covers draw, move, resize, Shift, Delete, Backspace, a sub-1 mm drag, zoom and pan, artwork transform independence, printable clamping, tool exclusion, the amber overlay, project round-trip, a legacy file, invalid clipping, preview/plot/estimate parity, margin overlap, multi-layer plot, and the main-window wiring plus flatten reuse.

## Left for Slice 3

Ellipse and circle keep-inside. Remove-inside is Slice 4. This slice has no undo stack.
