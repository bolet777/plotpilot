# Implementation notes: Ellipse keep-inside

**Status: frozen.** Slice 3 is merged. Pytest and ruff passed, and the main window was driven through rectangle, ellipse, Shift-to-circle, move, resize, zoom, and a small window. That is not a user sign-off.

A circle is an ellipse with equal radii. The rectangle overlap pass is unchanged.

## Decisions

**Unit-circle cut after the printable clip.** Each segment is divided by the radii, intersected with the unit circle, and mapped back to millimetres. Tangents and other spans shorter than 0.01 mm are dropped. A path that leaves and re-enters stays split.

**One shape.** Rectangle and ellipse are choices on the clip tool, shown only while that tool is on. Shift draws a square or a circle. A drag on the current shape still moves or resizes it. Delete clears it only while the clip tool is on.

**Project version stays 1.** `clipping.ellipse` stores center and radii. A file that only has `clipping.rectangle` still opens. Both keys at once is a project error.
