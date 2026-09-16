# Research: Qt SVG preview

**Choice**: `PySide6.QtSvg.QSvgRenderer` inside a custom `QWidget` (`LayerPreviewWidget`).

- Already available with the existing `PySide6` dependency (verified import; no pyproject change).
- `QSvgWidget` was not required; `render(painter, targetRect)` gives fit-to-area scaling.
- PlotPilot builds a temporary SVG string per layer; Qt performs actual rasterization.

**Alternative rejected**: WebEngine / third-party SVG libraries — out of scope and heavier than needed.
