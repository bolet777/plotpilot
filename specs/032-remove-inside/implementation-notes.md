# Implementation notes: Remove inside

**Status: frozen.** Slice 4 is merged. Pytest and ruff passed, and the main window was driven through rectangle, ellipse, and circle in both Keep inside and Remove inside, including a small window. That is not a user sign-off.

Keep inside stays the default. A rectangle in that mode still uses the single overlap pass.

## Decisions

**Printable clip first, then the hole.** Remove inside subtracts the one interval already found by Liang–Barsky or the unit-circle test. The prefix and the suffix are flushed apart, so the plot file gets two paths and no stroke across the gap. A tangent is a zero-length interval and does not open a hole.

**The shape stays put.** Switching In and Out does not move the shape, the zoom, or the pan. The buttons appear only while a shape exists and the clip tool is on.

**Project version stays 1.** `clipping.mode` is `remove_inside` only when that mode is saved with a shape. A missing mode loads as keep inside.
