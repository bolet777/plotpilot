"""Qt widget that renders generated layer preview SVG."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget


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

        target = QRectF(self.rect()).adjusted(12.0, 12.0, -12.0, -12.0)
        self._renderer.render(painter, target)
        painter.end()
