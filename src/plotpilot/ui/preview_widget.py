"""Qt widget that renders generated layer preview SVG."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QResizeEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.services.preview_work_area import (
    PhysicalPreviewLayout,
    PreviewWorkArea,
    compute_physical_preview_layout,
)


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


@dataclass(slots=True)
class _PhysicalPreviewState:
    svg_width_mm: float
    svg_height_mm: float
    work_area: PreviewWorkArea


class LayerPreviewWidget(QWidget):
    """Neutral canvas with centered, aspect-preserving SVG render."""

    _PREVIEW_MARGIN_PX = 12.0
    artwork_transform_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)
        self._renderer = QSvgRenderer(self)
        self._message: str | None = "Open an SVG to preview a layer."
        self._last_svg: str | None = None
        self._physical: _PhysicalPreviewState | None = None
        self._artwork_transform = ArtworkTransform.identity()
        self._transform_controls_enabled = True
        self._dragging = False
        self._drag_last_px: QPointF | None = None

    @property
    def last_svg(self) -> str | None:
        return self._last_svg

    @property
    def message(self) -> str | None:
        return self._message

    @property
    def physical_layout(self) -> PhysicalPreviewLayout | None:
        """Latest mm-space layout for the current widget size (for tests)."""
        return self._current_physical_layout()

    def clear_preview(self, message: str = "Open an SVG to preview a layer.") -> None:
        self._renderer = QSvgRenderer(self)
        self._message = message
        self._last_svg = None
        self._physical = None
        self.update()

    def set_preview_svg(self, svg_text: str) -> bool:
        """Load preview SVG; return False if Qt cannot render it."""
        self._last_svg = svg_text
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")), self)
        if not renderer.isValid():
            self._renderer = QSvgRenderer(self)
            self._message = "Preview unavailable for this layer."
            self._physical = None
            self.update()
            return False

        self._renderer = renderer
        self._message = None
        self.update()
        return True

    @property
    def artwork_transform(self) -> ArtworkTransform:
        return self._artwork_transform

    def set_artwork_transform(self, transform: ArtworkTransform) -> None:
        transform.validate()
        self._artwork_transform = transform
        self.update()

    def set_transform_controls_enabled(self, enabled: bool) -> None:
        self._transform_controls_enabled = enabled
        if not enabled:
            self._dragging = False
            self._drag_last_px = None

    def set_work_area_overlay(
        self,
        *,
        svg_width_mm: float,
        svg_height_mm: float,
        work_area: PreviewWorkArea | None,
    ) -> None:
        """Configure mm-space document size and plotter boundary (UI overlay only)."""
        if work_area is None or svg_width_mm <= 0 or svg_height_mm <= 0:
            self._physical = None
        else:
            self._physical = _PhysicalPreviewState(
                svg_width_mm=svg_width_mm,
                svg_height_mm=svg_height_mm,
                work_area=work_area,
            )
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update()

    def _available_rect(self) -> QRectF:
        margin = self._PREVIEW_MARGIN_PX
        return QRectF(self.rect()).adjusted(margin, margin, -margin, -margin)

    def _current_physical_layout(self) -> PhysicalPreviewLayout | None:
        if self._physical is None:
            return None
        available = self._available_rect()
        return compute_physical_preview_layout(
            self._physical.svg_width_mm,
            self._physical.svg_height_mm,
            self._physical.work_area.width_mm,
            self._physical.work_area.height_mm,
            available.width(),
            available.height(),
            origin_x_px=available.x(),
            origin_y_px=available.y(),
        )

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

        layout = self._current_physical_layout()
        if layout is not None:
            self._paint_physical_preview(painter, layout)
        else:
            self._paint_legacy_preview(painter)

        painter.end()

    def _paint_legacy_preview(self, painter: QPainter) -> None:
        available = self._available_rect()
        source_width, source_height = svg_render_source_size(self._renderer)
        target = fit_rect_preserve_aspect(source_width, source_height, available)
        if target.width() > 0 and target.height() > 0:
            self._renderer.render(painter, target)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            not self._transform_controls_enabled
            or self._message is not None
            or event.button() != Qt.MouseButton.LeftButton
        ):
            super().mousePressEvent(event)
            return
        layout = self._current_physical_layout()
        if layout is None:
            super().mousePressEvent(event)
            return
        self._dragging = True
        self._drag_last_px = event.position()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._dragging or self._drag_last_px is None:
            super().mouseMoveEvent(event)
            return
        layout = self._current_physical_layout()
        if layout is None or layout.mm_to_px <= 0:
            super().mouseMoveEvent(event)
            return
        delta_px = event.position() - self._drag_last_px
        self._drag_last_px = event.position()
        delta_x_mm = delta_px.x() / layout.mm_to_px
        delta_y_mm = delta_px.y() / layout.mm_to_px
        current = self._artwork_transform
        moved = ArtworkTransform(
            x_mm=current.x_mm + delta_x_mm,
            y_mm=current.y_mm + delta_y_mm,
            scale=current.scale,
        )
        self.set_artwork_transform(moved)
        self.artwork_transform_changed.emit(moved)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_last_px = None
        super().mouseReleaseEvent(event)

    def _paint_physical_preview(self, painter: QPainter, layout: PhysicalPreviewLayout) -> None:
        transform = self._artwork_transform
        scale_px = layout.mm_to_px
        page_w_px = layout.svg_rect_mm.width_mm * scale_px
        page_h_px = layout.svg_rect_mm.height_mm * scale_px
        page_target = QRectF(0.0, 0.0, page_w_px, page_h_px)
        work_w_px = layout.work_area_rect_mm.width_mm * scale_px
        work_h_px = layout.work_area_rect_mm.height_mm * scale_px
        work_target = QRectF(0.0, 0.0, work_w_px, work_h_px)

        painter.save()
        painter.translate(layout.workspace_x_px, layout.workspace_y_px)

        if page_w_px > 0 and page_h_px > 0:
            painter.save()
            painter.translate(transform.x_mm * scale_px, transform.y_mm * scale_px)
            painter.scale(transform.scale, transform.scale)
            painter.fillRect(page_target, QColor("#ffffff"))
            painter.setOpacity(0.35)
            self._renderer.render(painter, page_target)
            painter.setOpacity(1.0)
            if work_w_px > 0 and work_h_px > 0:
                painter.setClipRect(work_target)
            self._renderer.render(painter, page_target)
            painter.restore()

        wx, wy, ww, wh = work_target.x(), work_target.y(), work_target.width(), work_target.height()
        if ww > 0 and wh > 0:
            pen = QPen(QColor("#cc0000"))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidthF(1.5)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(work_target)

            label = self._physical.work_area.label if self._physical else ""
            if label:
                painter.setPen(QColor("#992222"))
                font = QFont(painter.font())
                font.setPointSize(max(font.pointSize() - 1, 8))
                painter.setFont(font)
                label_rect = QRectF(wx + 4.0, wy + 2.0, ww - 8.0, 16.0)
                painter.drawText(
                    label_rect,
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                    label,
                )
        painter.restore()
