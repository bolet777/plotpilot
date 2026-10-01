"""Qt widget that renders prepared plot geometry matching axicli output."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QResizeEvent,
)
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


def _polygons_from_polylines(
    polylines: tuple[tuple[tuple[float, float], ...], ...],
) -> list[QPolygonF]:
    polygons: list[QPolygonF] = []
    for subpath in polylines:
        if len(subpath) < 2:
            continue
        polygons.append(QPolygonF([QPointF(x, y) for x, y in subpath]))
    return polygons


@dataclass(slots=True)
class _PhysicalPreviewState:
    svg_width_mm: float
    svg_height_mm: float
    work_area: PreviewWorkArea


class LayerPreviewWidget(QWidget):
    """Machine work area with prepared plot geometry and optional faint source context."""

    _PREVIEW_MARGIN_PX = 12.0
    artwork_transform_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)
        self._context_renderer = QSvgRenderer(self)
        self._prepared_renderer = QSvgRenderer(self)
        self._message: str | None = "Open an SVG to preview a layer."
        self._last_svg: str | None = None
        self._prepared_svg: str | None = None
        self._prepared_error: str | None = None
        self._status_lines: tuple[str, ...] = ()
        self._physical: _PhysicalPreviewState | None = None
        self._artwork_transform = ArtworkTransform.identity()
        self._transform_controls_enabled = True
        self._dragging = False
        self._drag_last_px: QPointF | None = None
        self._clipped_polylines: tuple[tuple[tuple[float, float], ...], ...] = ()
        self._clipped_polygons: list[QPolygonF] = []
        self._plot_pixmap: QPixmap | None = None
        self._plot_pixmap_key: tuple[int, int, int, int] | None = None

    @property
    def last_svg(self) -> str | None:
        return self._last_svg

    @property
    def prepared_svg(self) -> str | None:
        return self._prepared_svg

    @property
    def message(self) -> str | None:
        return self._message

    @property
    def status_lines(self) -> tuple[str, ...]:
        return self._status_lines

    @property
    def physical_layout(self) -> PhysicalPreviewLayout | None:
        """Latest mm-space layout for the current widget size (for tests)."""
        return self._current_physical_layout()

    def clear_preview(self, message: str = "Open an SVG to preview a layer.") -> None:
        self._context_renderer = QSvgRenderer(self)
        self._prepared_renderer = QSvgRenderer(self)
        self._message = message
        self._last_svg = None
        self._prepared_svg = None
        self._prepared_error = None
        self._status_lines = ()
        self._physical = None
        self._clipped_polylines = ()
        self._clipped_polygons = []
        self._plot_pixmap = None
        self._plot_pixmap_key = None
        self.update()

    def set_preview_svg(self, svg_text: str) -> bool:
        """Load source/context SVG; return False if Qt cannot render it."""
        self._last_svg = svg_text
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")), self)
        if not renderer.isValid():
            self._context_renderer = QSvgRenderer(self)
            self._message = "Preview unavailable for this layer."
            self._physical = None
            self.update()
            return False

        self._context_renderer = renderer
        if self._prepared_svg is None and self._prepared_error is None:
            self._message = None
        self.update()
        return True

    def set_prepared_plot(
        self,
        *,
        prepared_svg: str | None,
        error_message: str | None,
        status_lines: tuple[str, ...] = (),
    ) -> None:
        """Set clipped machine-space plot SVG (same bytes sent toward axicli)."""
        self._prepared_error = error_message
        self._status_lines = status_lines
        self._clipped_polylines = ()
        self._clipped_polygons = []
        self._plot_pixmap = None
        self._plot_pixmap_key = None
        self._prepared_svg = prepared_svg
        if prepared_svg:
            renderer = QSvgRenderer(QByteArray(prepared_svg.encode("utf-8")), self)
            if renderer.isValid():
                self._prepared_renderer = renderer
            else:
                self._prepared_renderer = QSvgRenderer(self)
        else:
            self._prepared_renderer = QSvgRenderer(self)

        if self._context_renderer.isValid():
            self._message = None
        elif error_message:
            self._message = error_message
        self.update()

    def set_clipped_plot(
        self,
        *,
        polylines: tuple[tuple[tuple[float, float], ...], ...] | None,
        error_message: str | None,
        status_lines: tuple[str, ...] = (),
    ) -> None:
        """Show already-clipped machine-space polylines. Does not parse SVG."""
        self._prepared_error = error_message
        self._status_lines = status_lines
        self._prepared_svg = None
        self._prepared_renderer = QSvgRenderer(self)
        self._clipped_polylines = polylines or ()
        self._clipped_polygons = _polygons_from_polylines(self._clipped_polylines)
        self._plot_pixmap = None
        self._plot_pixmap_key = None
        if self._context_renderer.isValid():
            self._message = None
        elif error_message:
            self._message = error_message
        self.update()

    def clear_clipped_plot(self) -> None:
        """Drop plotted ink while a new layer is prepared. Context SVG stays."""
        self.set_clipped_plot(polylines=(), error_message=None, status_lines=())

    @property
    def clipped_polylines(self) -> tuple[tuple[tuple[float, float], ...], ...]:
        return self._clipped_polylines

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
        """Configure mm-space document size and plotter boundary."""
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
        self._plot_pixmap = None
        self._plot_pixmap_key = None
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

        if self._message and not self._context_renderer.isValid():
            painter.setPen(QColor("#555555"))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                self._message,
            )
            painter.end()
            return

        layout = self._current_physical_layout()
        if layout is not None:
            self._paint_physical_preview(painter, layout)
        else:
            self._paint_legacy_preview(painter)

        if self._status_lines or self._prepared_error:
            self._paint_status_footer(painter)

        painter.end()

    def _paint_status_footer(self, painter: QPainter) -> None:
        lines = list(self._status_lines)
        if not lines and self._prepared_error:
            lines = [self._prepared_error]
        if not lines:
            return
        painter.save()
        painter.setPen(QColor("#664400"))
        font = QFont(painter.font())
        font.setPointSize(max(font.pointSize() - 1, 8))
        painter.setFont(font)
        footer = self.rect().adjusted(8, 0, -8, -4)
        painter.drawText(
            footer,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            "\n".join(lines),
        )
        painter.restore()

    def _paint_legacy_preview(self, painter: QPainter) -> None:
        available = self._available_rect()
        if self._prepared_renderer.isValid():
            source_width = self._prepared_renderer.defaultSize().width()
            source_height = self._prepared_renderer.defaultSize().height()
            if source_width <= 0 or source_height <= 0:
                view_box = self._prepared_renderer.viewBoxF()
                source_width = view_box.width()
                source_height = view_box.height()
            target = fit_rect_preserve_aspect(source_width, source_height, available)
            if target.width() > 0 and target.height() > 0:
                self._prepared_renderer.render(painter, target)
            return

        if not self._context_renderer.isValid():
            painter.setPen(QColor("#555555"))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                "Preview unavailable for this layer.",
            )
            return

        source_width, source_height = svg_render_source_size(self._context_renderer)
        target = fit_rect_preserve_aspect(source_width, source_height, available)
        if target.width() > 0 and target.height() > 0:
            self._context_renderer.render(painter, target)

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

        if self._context_renderer.isValid() and page_w_px > 0 and page_h_px > 0:
            painter.save()
            painter.translate(transform.x_mm * scale_px, transform.y_mm * scale_px)
            painter.scale(transform.scale, transform.scale)
            painter.fillRect(page_target, QColor("#ffffff"))
            painter.setOpacity(0.22)
            self._context_renderer.render(painter, page_target)
            painter.restore()

        if self._clipped_polygons and work_w_px > 0 and work_h_px > 0:
            pixmap = self._plot_pixmap_for(work_w_px, work_h_px, scale_px)
            if pixmap is not None:
                painter.drawPixmap(QPointF(0.0, 0.0), pixmap)
        elif self._prepared_renderer.isValid() and work_w_px > 0 and work_h_px > 0:
            painter.save()
            painter.setClipRect(work_target)
            self._prepared_renderer.render(painter, work_target)
            painter.restore()
        elif self._prepared_error and not self._prepared_renderer.isValid():
            painter.setPen(QColor("#884400"))
            painter.drawText(
                work_target,
                int(Qt.AlignmentFlag.AlignCenter),
                self._prepared_error,
            )

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

    def _plot_pixmap_for(
        self,
        work_w_px: float,
        work_h_px: float,
        mm_to_px: float,
    ) -> QPixmap | None:
        """Rasterize clipped strokes once per geometry or widget size."""
        if not self._clipped_polygons or work_w_px < 1.0 or work_h_px < 1.0 or mm_to_px <= 0:
            return None
        dpr = self.devicePixelRatioF()
        key = (
            round(work_w_px),
            round(work_h_px),
            round(dpr * 100),
            id(self._clipped_polygons),
        )
        if self._plot_pixmap is not None and self._plot_pixmap_key == key:
            return self._plot_pixmap

        pixmap = QPixmap(max(1, int(work_w_px * dpr)), max(1, int(work_h_px * dpr)))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        plot_painter = QPainter(pixmap)
        plot_painter.setClipRect(QRectF(0.0, 0.0, work_w_px, work_h_px))
        plot_painter.scale(mm_to_px, mm_to_px)
        pen = QPen(QColor("#000000"))
        pen.setWidthF(0.2)
        plot_painter.setPen(pen)
        plot_painter.setBrush(Qt.BrushStyle.NoBrush)
        for polygon in self._clipped_polygons:
            if polygon.size() >= 2:
                plot_painter.drawPolyline(polygon)
        plot_painter.end()
        self._plot_pixmap = pixmap
        self._plot_pixmap_key = key
        return pixmap
