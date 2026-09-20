"""Qt widget that renders generated layer preview SVG."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QResizeEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget


def fit_rect_preserve_aspect(
    source_width: float,
    source_height: float,
    available: QRectF,
) -> QRectF:
    """Return a centered rect inside *available* with the same aspect ratio as the source."""
    avail_w = available.width()
    avail_h = available.height()
    if source_width <= 0 or source_height <= 0 or avail_w <= 0 or avail_h <= 0:
        return QRectF(available.x(), available.y(), 0.0, 0.0)

    scale = min(
        available.width() / source_width,
        available.height() / source_height,
    )
    target_width = source_width * scale
    target_height = source_height * scale
    target_x = available.x() + (available.width() - target_width) / 2
    target_y = available.y() + (available.height() - target_height) / 2
    return QRectF(target_x, target_y, target_width, target_height)


def svg_render_source_size(renderer: QSvgRenderer) -> tuple[float, float]:
    """Width and height used for aspect-preserving layout (viewBox, else default size)."""
    view_box = renderer.viewBoxF()
    if view_box.width() > 0 and view_box.height() > 0:
        return view_box.width(), view_box.height()

    default = renderer.defaultSize()
    if default.width() > 0 and default.height() > 0:
        return float(default.width()), float(default.height())

    return 0.0, 0.0


class LayerPreviewWidget(QWidget):
    """Neutral canvas with centered, aspect-preserving SVG render."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self._renderer = QSvgRenderer(self)
        self._message: str | None = "Open an SVG to preview a layer."
        self._last_svg: str | None = None

    @property
    def last_svg(self) -> str | None:
        return self._last_svg

    @property
    def message(self) -> str | None:
        return self._message

    def clear_preview(self, message: str = "Open an SVG to preview a layer.") -> None:
        self._renderer = QSvgRenderer(self)
        self._message = message
        self._last_svg = None
        self.update()

    def set_preview_svg(self, svg_text: str) -> bool:
        """Load preview SVG; return False if Qt cannot render it."""
        self._last_svg = svg_text
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")), self)
        if not renderer.isValid():
            self._renderer = QSvgRenderer(self)
            self._message = "Preview unavailable for this layer."
            self.update()
            return False

        self._renderer = renderer
        self._message = None
        self.update()
        return True

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#e8e8e8"))

        if self._message:
            painter.setPen(QColor("#555555"))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                self._message,
            )
            painter.end()
            return

        if not self._renderer.isValid():
            painter.setPen(QColor("#555555"))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                "Preview unavailable for this layer.",
            )
            painter.end()
            return

        available = QRectF(self.rect()).adjusted(12.0, 12.0, -12.0, -12.0)
        source_width, source_height = svg_render_source_size(self._renderer)
        target = fit_rect_preserve_aspect(source_width, source_height, available)
        if target.width() > 0 and target.height() > 0:
            self._renderer.render(painter, target)
        painter.end()
