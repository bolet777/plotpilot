# Implementation plan

**Branch**: `027-window-resize-and-scroll` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

The main window asks for 900×560, but the central layout’s minimum size is about 898×972, and Qt uses that as the window minimum. The window cannot shrink, and on a shorter screen the plotter controls sit past the bottom edge with no way to scroll to them.

Put the existing central widget in a `QScrollArea` (`ScrollBarAsNeeded`, `widgetResizable`) whose `minimumSizeHint` does not follow the document. Give the window a modest minimum (480×320, clamped to `availableGeometry`) and honor 900×560 when the usable screen allows it.

## Root cause (measured, offscreen 800×800, before the fix)

`MainWindow.resize(900, 560)` does not stick.

| Widget | minimum / minimumSizeHint | What it forces |
| --- | --- | --- |
| `MainWindow` | realized **898×972**; maximum is Qt’s default (not fixed) | `resize(400, 300)` stays 898×972 |
| Central widget | **898×952** | Becomes the window minimum (plus menu bar) |
| Plotter button row | visible buttons sum to ~898px wide | Horizontal minimum. Hidden Continue is excluded |
| `PlotSettingsWidget` | 336×302 | Large share of the vertical minimum |
| `ArtworkTransformControls` | 338×224 | Next largest vertical block; spin boxes are fixed width (72 / 88) but do not set the window width |
| `LayerPreviewWidget` | 200×200, Expanding × Expanding | Contributes 200px of height; not the window-size bug by itself |
| Layer list | `setMinimumWidth(220)`; size hint 256×192 | Does **not** set the window width (the button row is wider) |

There is no `setFixedSize`, `setMaximumSize`, or window-level `setMinimumSize`. The lock is the layout minimum propagating through `QMainWindow`. No child uses a scroll area, so overflow cannot be reached.

## Scroll architecture

- `QMainWindow` stays the top-level window. Only the existing central content goes inside the scroll area.
- `_MainContentScrollArea.minimumSizeHint()` returns `0×0` so the document size cannot become the window minimum. This is required: Qt’s effective minimum is the larger of `minimumSize` and `minimumSizeHint`.
- `widgetResizable = True` and `SizeAdjustPolicy.AdjustIgnored`.
  - Viewport larger than the document: the content widget grows and the preview’s stretch still takes the spare space. Scrollbars stay at maximum 0.
  - Viewport smaller than the document minimum: the content widget stays at its layout minimum (children are not clipped) and scrollbars report a range.
- Both policies are `ScrollBarAsNeeded`. No stylesheet and no custom painting, so macOS overlay scrollbars, light/dark, and trackpad axes stay native.
- Frame is `NoFrame` so the large-window layout does not gain a second border.

## Launch size

`window_size_bounds(available_width, available_height)`:

- Preferred 900×560, minimum 480×320.
- Both are clamped down to `QGuiApplication.primaryScreen().availableGeometry()` (menu bar and Dock already excluded).
- Applied once at the end of `MainWindow.__init__`. No later screen-change resize.

A 900×560 window is shorter than the ~952px document, so a vertical scrollbar at launch is expected until the user makes the window taller. That matches the size the code already requested; the old window only looked taller because Qt refused to honor 560.

## Nested scrolling

- The layer list keeps its own scrollbars. Long names scroll inside the list.
- `_LayerListWheelFilter` forwards a wheel/trackpad event to the scroll area’s viewport only when the list has no range on that axis. The viewport is what actually scrolls; sending the event to the `QScrollArea` itself does not. When the list can scroll, it keeps the event. No edge-chaining.
- The preview has no scrollbar. Transform rows and the plotter button row do not wrap; a narrow window scrolls horizontally instead of clipping them.
- Layer list minimum width stays 220. It no longer forces the window width, and shrinking it would change the large-window layout for no gain.

## Preview and transform controls

- Preview minimum stays 200×200 with Expanding × Expanding. Proportions stay in `fit_rect_preserve_aspect`.
- Transform sliders keep stretch; numeric fields keep their fixed widths. The global horizontal scrollbar reveals the full row.

## Tests

`tests/test_main_window_resize.py` uses structural checks (policies, ancestry, scrollbar `maximum()`, size bounds). No pixel snapshots.

## Constitution check

- macOS-first: native `QScrollArea`, `availableGeometry`. No platform-only API.
- UI-only slice. No plot geometry, plotter protocol, or project file changes.
- Testable offscreen. No hardware.

## Out of scope

Docking, detachable windows, custom scrollbars, wrapping the plotter button row, changing preview or plot behavior.
