"""Qt widget that renders prepared plot geometry matching axicli output.

V2 adds a dark canvas, mm rulers, view zoom/pan, and a cursor readout. All of
those are presentation only: the mm-space layout, the clipped geometry, and
the drag-to-move artwork transform are unchanged from V1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.print_margins import PrintableArea
from plotpilot.services.preview_work_area import (
    PhysicalPreviewLayout,
    PreviewWorkArea,
    compute_physical_preview_layout,
)
from plotpilot.ui.theme import COLORS, scaled_font

VIEW_ZOOM_MIN = 0.25
VIEW_ZOOM_MAX = 8.0
_ZOOM_STEP = 1.25


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


def clamp_view_zoom(zoom: float) -> float:
    if not math.isfinite(zoom):
        return 1.0
    return max(VIEW_ZOOM_MIN, min(VIEW_ZOOM_MAX, zoom))


def ruler_step_mm(mm_to_px: float, *, min_label_px: float = 56.0) -> tuple[float, int]:
    """Return ``(major_step_mm, minor_divisions)`` so labels stay at least *min_label_px* apart."""
    if mm_to_px <= 0:
        return 50.0, 5
    for step, minor in (
        (1.0, 2),
        (2.0, 2),
        (5.0, 5),
        (10.0, 5),
        (20.0, 2),
        (25.0, 5),
        (50.0, 5),
        (100.0, 5),
        (200.0, 2),
        (500.0, 5),
    ):
        if step * mm_to_px >= min_label_px:
            return step, minor
    return 1000.0, 5


def _polygons_from_polylines(
    polylines: tuple[tuple[tuple[float, float], ...], ...],
) -> list[QPolygonF]:
    polygons: list[QPolygonF] = []
    for subpath in polylines:
        if len(subpath) < 2:
            continue
        polygons.append(QPolygonF([QPointF(x, y) for x, y in subpath]))
    return polygons


def _polylines_bounds(
    polylines: tuple[tuple[tuple[float, float], ...], ...],
) -> QRectF | None:
    """Axis-aligned bounds (document mm) of all polyline points, or None if empty."""
    xs = [x for subpath in polylines for x, _ in subpath]
    ys = [y for subpath in polylines for _, y in subpath]
    if not xs or not ys:
        return None
    return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys)))


@dataclass(slots=True)
class _PhysicalPreviewState:
    svg_width_mm: float
    svg_height_mm: float
    work_area: PreviewWorkArea
    printable_area: PrintableArea | None = None


class LayerPreviewWidget(QWidget):
    """Machine work area with prepared plot geometry and optional faint source context."""

    _PREVIEW_MARGIN_PX = 16.0
    _INFO_PAD = 6.0
    RULER_PX = 22.0
    _GHOST_OPACITY = 0.18
    _GHOST_OPACITY_PENDING = 0.45
    _CONTEXT_PIXMAP_MAX_PX = 8192
    artwork_transform_changed = Signal(object)
    view_changed = Signal()
    cursor_mm_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
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
        self._panning = False
        self._pan_last_px: QPointF | None = None
        self._pan_tool = False
        self._view_zoom = 1.0
        self._view_pan_px = QPointF(0.0, 0.0)
        self._show_rulers = True
        self._clipped_polylines: tuple[tuple[tuple[float, float], ...], ...] = ()
        self._clipped_polygons: list[QPolygonF] = []
        self._plot_pixmap: QPixmap | None = None
        self._plot_pixmap_key: tuple[int, int, int, int] | None = None
        # Unplaced, unclipped document-mm polylines of the current layer. When present
        # they replace the QSvgRenderer "ghost" so the context and the clipped ink come
        # from the same flattened geometry (same viewBox / aspect-ratio mapping).
        self._context_polylines: tuple[tuple[tuple[float, float], ...], ...] = ()
        self._context_polygons: list[QPolygonF] = []
        self._context_bounds_mm: QRectF | None = None
        self._context_pixmap: QPixmap | None = None
        self._context_pixmap_key: tuple[int, int, int] | None = None
        # True between "a transform/clip refresh was scheduled" and the next
        # set_clipped_plot(): the stale clipped ink is hidden meanwhile.
        self._clip_pending = False
        self._painted_printable_boundary = False

    # ------------------------------------------------------------- content API
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
        self._clip_pending = False
        self._reset_context_polylines()
        self.update()

    def _reset_context_polylines(self) -> None:
        self._context_polylines = ()
        self._context_polygons = []
        self._context_bounds_mm = None
        self._context_pixmap = None
        self._context_pixmap_key = None

    def set_context_polylines(
        self,
        polylines: tuple[tuple[tuple[float, float], ...], ...] | None,
    ) -> None:
        """Provide the layer's flattened document-mm polylines for the context ghost.

        Pass ``None``/empty to fall back to the source-SVG renderer.
        """
        self._reset_context_polylines()
        if polylines:
            self._context_polylines = polylines
            self._context_polygons = _polygons_from_polylines(polylines)
            self._context_bounds_mm = _polylines_bounds(polylines)
        self.update()

    @property
    def context_polylines(self) -> tuple[tuple[tuple[float, float], ...], ...]:
        return self._context_polylines

    @property
    def uses_geometry_context(self) -> bool:
        """True when the ghost is painted from flattened geometry, not the source SVG."""
        return bool(self._context_polygons) and self._context_bounds_mm is not None

    def set_clip_pending(self) -> None:
        """Hide stale clipped ink until the next ``set_clipped_plot``."""
        if not self._clip_pending:
            self._clip_pending = True
            self.update()

    @property
    def clip_pending(self) -> bool:
        return self._clip_pending

    def set_preview_svg(self, svg_text: str) -> bool:
        """Load source/context SVG; return False if Qt cannot render it."""
        if svg_text != self._last_svg:
            self._reset_context_polylines()
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
        self._clip_pending = False
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
        self._clip_pending = False
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

    @property
    def printable_area(self) -> PrintableArea | None:
        if self._physical is None:
            return None
        return self._physical.printable_area

    @property
    def painted_printable_boundary(self) -> bool:
        return self._painted_printable_boundary

    def set_work_area_overlay(
        self,
        *,
        svg_width_mm: float,
        svg_height_mm: float,
        work_area: PreviewWorkArea | None,
        printable_area: PrintableArea | None = None,
    ) -> None:
        """Configure mm-space document size, machine boundary, and printable inset."""
        if work_area is None or svg_width_mm <= 0 or svg_height_mm <= 0:
            self._physical = None
        else:
            self._physical = _PhysicalPreviewState(
                svg_width_mm=svg_width_mm,
                svg_height_mm=svg_height_mm,
                work_area=work_area,
                printable_area=printable_area,
            )
        self.update()

    # ---------------------------------------------------------------- view API
    @property
    def view_zoom(self) -> float:
        """Display magnification relative to "fit" (1.0). Never affects plotting."""
        return self._view_zoom

    @property
    def pan_tool_active(self) -> bool:
        return self._pan_tool

    def set_pan_tool_active(self, active: bool) -> None:
        self._pan_tool = active
        self._update_cursor()

    def set_rulers_visible(self, visible: bool) -> None:
        self._show_rulers = visible
        self._invalidate_pixmap()
        self.update()

    def set_view_zoom(self, zoom: float, *, anchor_px: QPointF | None = None) -> None:
        """Zoom the view around *anchor_px* (widget coordinates; default: center)."""
        new_zoom = clamp_view_zoom(zoom)
        if math.isclose(new_zoom, self._view_zoom, rel_tol=1e-9):
            return
        available = self._available_rect()
        center = available.center()
        if anchor_px is None:
            anchor_px = center
        # Keep the point under the anchor fixed: origin' = anchor + (origin - anchor) * k
        base = self._base_layout()
        if base is not None:
            old_origin = self._viewed_origin(base, center)
            k = new_zoom / self._view_zoom
            new_origin = QPointF(
                anchor_px.x() + (old_origin.x() - anchor_px.x()) * k,
                anchor_px.y() + (old_origin.y() - anchor_px.y()) * k,
            )
            self._view_zoom = new_zoom
            fit_origin = QPointF(
                center.x() + (base.workspace_x_px - center.x()) * new_zoom,
                center.y() + (base.workspace_y_px - center.y()) * new_zoom,
            )
            self._view_pan_px = new_origin - fit_origin
        else:
            self._view_zoom = new_zoom
        self._invalidate_pixmap()
        self.view_changed.emit()
        self.update()

    def zoom_in(self) -> None:
        self.set_view_zoom(self._view_zoom * _ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_view_zoom(self._view_zoom / _ZOOM_STEP)

    def fit_view(self) -> None:
        changed = not math.isclose(self._view_zoom, 1.0) or not self._view_pan_px.isNull()
        self._view_zoom = 1.0
        self._view_pan_px = QPointF(0.0, 0.0)
        self._invalidate_pixmap()
        if changed:
            self.view_changed.emit()
        self.update()

    def pan_by(self, delta_px: QPointF) -> None:
        if delta_px.isNull():
            return
        self._view_pan_px = self._view_pan_px + delta_px
        self.view_changed.emit()
        self.update()

    def widget_to_mm(self, point_px: QPointF) -> tuple[float, float] | None:
        """Machine-space mm under a widget pixel, or None without a physical layout."""
        layout = self._current_physical_layout()
        if layout is None or layout.mm_to_px <= 0:
            return None
        return (
            (point_px.x() - layout.workspace_x_px) / layout.mm_to_px,
            (point_px.y() - layout.workspace_y_px) / layout.mm_to_px,
        )

    # ----------------------------------------------------------------- layout
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._invalidate_pixmap()
        self.update()

    def _invalidate_pixmap(self) -> None:
        self._plot_pixmap = None
        self._plot_pixmap_key = None

    def _ruler_px(self) -> float:
        return self.RULER_PX if self._show_rulers else 0.0

    def _info_lines(self) -> list[tuple[str, QColor]]:
        """Lines of the top-left info chip: work-area label plus preparation warnings."""
        warnings = list(self._status_lines)
        if not warnings and self._prepared_error:
            warnings = [self._prepared_error]
        lines: list[tuple[str, QColor]] = []
        if self._physical is not None and self._physical.work_area.label:
            lines.append((self._physical.work_area.label, QColor(COLORS.ruler_text)))
        lines.extend((line, QColor(COLORS.warning)) for line in warnings)
        return lines

    def _info_font(self) -> QFont:
        return scaled_font(self.font(), -1.0, minimum=8.0)

    def _info_chip_height(self) -> float:
        lines = self._info_lines()
        if not lines:
            return 0.0
        return QFontMetrics(self._info_font()).height() * len(lines) + 2 * self._INFO_PAD

    def _available_rect(self) -> QRectF:
        margin = self._PREVIEW_MARGIN_PX
        ruler = self._ruler_px()
        # Reserve room under the rulers for the info chip so it never covers the paper
        # at the default (fit) zoom.
        chip = self._info_chip_height()
        top_inset = margin + ruler + (chip + 4.0 if chip else 0.0)
        return QRectF(self.rect()).adjusted(margin + ruler, top_inset, -margin, -margin)

    def _base_layout(self) -> PhysicalPreviewLayout | None:
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

    def _viewed_origin(self, base: PhysicalPreviewLayout, center: QPointF) -> QPointF:
        return QPointF(
            center.x()
            + (base.workspace_x_px - center.x()) * self._view_zoom
            + self._view_pan_px.x(),
            center.y()
            + (base.workspace_y_px - center.y()) * self._view_zoom
            + self._view_pan_px.y(),
        )

    def _current_physical_layout(self) -> PhysicalPreviewLayout | None:
        base = self._base_layout()
        if base is None:
            return None
        if math.isclose(self._view_zoom, 1.0) and self._view_pan_px.isNull():
            return base
        origin = self._viewed_origin(base, self._available_rect().center())
        return replace(
            base,
            mm_to_px=base.mm_to_px * self._view_zoom,
            workspace_x_px=origin.x(),
            workspace_y_px=origin.y(),
        )

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _event) -> None:  # noqa: N802
        self._painted_printable_boundary = False
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS.canvas))

        if self._message and not self._context_renderer.isValid():
            painter.setPen(QColor(COLORS.text_secondary))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                self._message,
            )
            painter.end()
            return

        layout = self._current_physical_layout()
        if layout is not None:
            painter.save()
            painter.setClipRect(self._canvas_clip_rect())
            self._paint_physical_preview(painter, layout)
            painter.restore()
            if self._show_rulers:
                self._paint_rulers(painter, layout)
        else:
            self._paint_legacy_preview(painter)

        if layout is not None or self._status_lines or self._prepared_error:
            self._paint_status_footer(painter)

        painter.end()

    def _canvas_clip_rect(self) -> QRectF:
        ruler = self._ruler_px()
        return QRectF(self.rect()).adjusted(ruler, ruler, 0.0, 0.0)

    def _paint_status_footer(self, painter: QPainter) -> None:
        """Top-left info chip: work-area label (muted) plus any preparation warnings."""
        lines = self._info_lines()
        if not lines:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._info_font())
        metrics = painter.fontMetrics()
        max_width = max(120.0, min(self.width() - 2 * (self._ruler_px() + 10) - 60, 480.0))
        line_height = metrics.height()
        # +2 px slack: horizontalAdvance() rounds while elidedText() measures
        # fractionally, so an exact fit can still elide the longest line.
        text_width = min(
            max_width,
            max(metrics.horizontalAdvance(text) for text, _ in lines) + 2.0,
        )
        pad = self._INFO_PAD
        box = QRectF(
            self._ruler_px() + self._PREVIEW_MARGIN_PX,
            self._ruler_px() + 8.0,
            text_width + 2 * pad,
            line_height * len(lines) + 2 * pad,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(box, 5, 5)
        y = box.y() + pad
        for text, color in lines:
            painter.setPen(color)
            painter.drawText(
                QRectF(box.x() + pad, y, text_width, line_height),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, int(text_width)),
            )
            y += line_height
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
                painter.fillRect(target, QColor(COLORS.paper))
                self._prepared_renderer.render(painter, target)
            return

        if not self._context_renderer.isValid():
            painter.setPen(QColor(COLORS.text_secondary))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                "Preview unavailable for this layer.",
            )
            return

        source_width, source_height = svg_render_source_size(self._context_renderer)
        target = fit_rect_preserve_aspect(source_width, source_height, available)
        if target.width() > 0 and target.height() > 0:
            painter.fillRect(target, QColor(COLORS.paper))
            self._context_renderer.render(painter, target)

    def _paint_rulers(self, painter: QPainter, layout: PhysicalPreviewLayout) -> None:
        ruler = self._ruler_px()
        if ruler <= 0:
            return
        painter.save()
        width = float(self.width())
        height = float(self.height())
        painter.fillRect(QRectF(0, 0, width, ruler), QColor(COLORS.ruler_bg))
        painter.fillRect(QRectF(0, 0, ruler, height), QColor(COLORS.ruler_bg))
        painter.setPen(QPen(QColor(COLORS.border_subtle), 1.0))
        painter.drawLine(QPointF(ruler, ruler), QPointF(width, ruler))
        painter.drawLine(QPointF(ruler, ruler), QPointF(ruler, height))

        painter.setFont(scaled_font(painter.font(), -3.0, minimum=7.0))
        step_mm, minor = ruler_step_mm(layout.mm_to_px)
        tick_pen = QPen(QColor(COLORS.ruler_tick), 1.0)
        text_color = QColor(COLORS.ruler_text)

        # Horizontal ruler
        x0 = layout.workspace_x_px
        start_mm = math.floor((ruler - x0) / layout.mm_to_px / step_mm) * step_mm
        end_mm = (width - x0) / layout.mm_to_px
        mm = start_mm
        while mm <= end_mm:
            x = x0 + mm * layout.mm_to_px
            if x >= ruler:
                painter.setPen(tick_pen)
                painter.drawLine(QPointF(x, ruler - 8), QPointF(x, ruler))
                painter.setPen(text_color)
                painter.drawText(
                    QRectF(x + 3, 1, step_mm * layout.mm_to_px - 4, ruler - 8),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    _fmt_ruler(mm),
                )
            painter.setPen(tick_pen)
            for i in range(1, minor):
                xm = x + i * step_mm / minor * layout.mm_to_px
                if xm >= ruler:
                    painter.drawLine(QPointF(xm, ruler - 4), QPointF(xm, ruler))
            mm += step_mm

        # Vertical ruler
        y0 = layout.workspace_y_px
        start_mm = math.floor((ruler - y0) / layout.mm_to_px / step_mm) * step_mm
        end_mm = (height - y0) / layout.mm_to_px
        mm = start_mm
        while mm <= end_mm:
            y = y0 + mm * layout.mm_to_px
            if y >= ruler:
                painter.setPen(tick_pen)
                painter.drawLine(QPointF(ruler - 8, y), QPointF(ruler, y))
                painter.save()
                painter.translate(1, y + step_mm * layout.mm_to_px - 3)
                painter.rotate(-90)
                painter.setPen(text_color)
                painter.drawText(
                    QRectF(0, 0, step_mm * layout.mm_to_px - 4, ruler - 8),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    _fmt_ruler(mm),
                )
                painter.restore()
            painter.setPen(tick_pen)
            for i in range(1, minor):
                ym = y + i * step_mm / minor * layout.mm_to_px
                if ym >= ruler:
                    painter.drawLine(QPointF(ruler - 4, ym), QPointF(ruler, ym))
            mm += step_mm

        painter.fillRect(QRectF(0, 0, ruler, ruler), QColor(COLORS.ruler_bg))
        painter.setPen(text_color)
        painter.drawText(
            QRectF(0, 0, ruler, ruler),
            int(Qt.AlignmentFlag.AlignCenter),
            "mm",
        )
        painter.restore()

    # ----------------------------------------------------------------- mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        layout = self._current_physical_layout()
        wants_pan = event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._pan_tool
        )
        if wants_pan and layout is not None:
            self._panning = True
            self._pan_last_px = event.position()
            self._update_cursor()
            event.accept()
            return
        if (
            not self._transform_controls_enabled
            or self._message is not None
            or event.button() != Qt.MouseButton.LeftButton
        ):
            super().mousePressEvent(event)
            return
        if layout is None:
            super().mousePressEvent(event)
            return
        self._dragging = True
        self._drag_last_px = event.position()
        self._update_cursor()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.cursor_mm_changed.emit(self.widget_to_mm(event.position()))
        if self._panning and self._pan_last_px is not None:
            delta = event.position() - self._pan_last_px
            self._pan_last_px = event.position()
            self.pan_by(delta)
            event.accept()
            return
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
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._dragging = False
            self._drag_last_px = None
            self._panning = False
            self._pan_last_px = None
            self._update_cursor()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.cursor_mm_changed.emit(None)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._current_physical_layout() is None:
            super().wheelEvent(event)
            return
        modifiers = event.modifiers()
        zoom_modifier = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        if modifiers & zoom_modifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                factor = _ZOOM_STEP if delta > 0 else 1.0 / _ZOOM_STEP
                self.set_view_zoom(self._view_zoom * factor, anchor_px=event.position())
            event.accept()
            return
        if math.isclose(self._view_zoom, 1.0) and self._view_pan_px.isNull():
            # At "fit" there is nothing to scroll to; let the event propagate.
            super().wheelEvent(event)
            return
        pixels = event.pixelDelta()
        if pixels.isNull():
            angle = event.angleDelta()
            pixels = angle / 4
        self.pan_by(QPointF(pixels.x(), pixels.y()))
        event.accept()

    def _update_cursor(self) -> None:
        if self._panning:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._pan_tool:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._dragging:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.unsetCursor()

    # ------------------------------------------------------------ physical
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

        # Paper (physical work area) with a soft shadow; margins read as a darker band.
        if work_w_px > 0 and work_h_px > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            shadow = QColor(COLORS.paper_shadow)
            shadow.setAlpha(140)
            painter.setBrush(shadow)
            painter.drawRect(work_target.translated(0.0, 3.0).adjusted(-1, -1, 1, 1))
            painter.setBrush(QColor(COLORS.margin_zone))
            painter.drawRect(work_target)
            printable = self._printable_rect_px(scale_px)
            if printable is not None:
                painter.setBrush(QColor(COLORS.paper))
                painter.drawRect(printable)

        # Context ghost at the live transform. While a clip refresh is pending the
        # ghost is the only artwork shown, so it is drawn a little stronger.
        ghost_opacity = self._GHOST_OPACITY_PENDING if self._clip_pending else self._GHOST_OPACITY
        if self.uses_geometry_context and work_w_px > 0 and work_h_px > 0:
            self._paint_geometry_context(painter, transform, scale_px, work_target, ghost_opacity)
        elif self._context_renderer.isValid() and page_w_px > 0 and page_h_px > 0:
            painter.save()
            painter.setClipRect(work_target)
            painter.translate(transform.x_mm * scale_px, transform.y_mm * scale_px)
            painter.scale(transform.scale, transform.scale)
            painter.setOpacity(ghost_opacity)
            self._context_renderer.render(painter, page_target)
            painter.restore()

        show_ink = not self._clip_pending
        if show_ink and self._clipped_polygons and work_w_px > 0 and work_h_px > 0:
            pixmap = self._plot_pixmap_for(work_w_px, work_h_px, scale_px)
            if pixmap is not None:
                painter.drawPixmap(QPointF(0.0, 0.0), pixmap)
        elif show_ink and self._prepared_renderer.isValid() and work_w_px > 0 and work_h_px > 0:
            painter.save()
            painter.setClipRect(work_target)
            self._prepared_renderer.render(painter, work_target)
            painter.restore()
        elif self._prepared_error and not self._prepared_renderer.isValid():
            painter.setPen(QColor("#8a5a00"))
            painter.drawText(
                work_target,
                int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                self._prepared_error,
            )

        if work_w_px > 0 and work_h_px > 0:
            pen = QPen(QColor(COLORS.work_area_outline))
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setWidthF(1.0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(work_target)
            self._paint_printable_boundary(painter, scale_px)

        painter.restore()

    def _printable_rect_px(self, scale_px: float) -> QRectF | None:
        if self._physical is None or self._physical.printable_area is None or scale_px <= 0:
            return None
        area = self._physical.printable_area
        if area.width_mm <= 0 or area.height_mm <= 0:
            return None
        return QRectF(
            area.x_mm * scale_px,
            area.y_mm * scale_px,
            area.width_mm * scale_px,
            area.height_mm * scale_px,
        )

    def _paint_printable_boundary(self, painter: QPainter, scale_px: float) -> None:
        """Dashed accent rectangle with corner marks around the printable area."""
        rect = self._printable_rect_px(scale_px)
        if rect is None:
            return
        pen = QPen(QColor(COLORS.printable_outline))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidthF(1.2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        corner_pen = QPen(QColor(COLORS.printable_outline))
        corner_pen.setWidthF(2.0)
        corner_pen.setCosmetic(True)
        painter.setPen(corner_pen)
        arm = min(10.0, rect.width() / 4, rect.height() / 4)
        for cx, cy, sx, sy in (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ):
            painter.drawLine(QPointF(cx, cy), QPointF(cx + sx * arm, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * arm))
        self._painted_printable_boundary = True

    def _paint_geometry_context(
        self,
        painter: QPainter,
        transform: ArtworkTransform,
        mm_to_px: float,
        work_target: QRectF,
        opacity: float,
    ) -> None:
        """Blit the cached ghost raster at the live transform (translation is free)."""
        bounds = self._context_bounds_mm
        if bounds is None or mm_to_px <= 0:
            return
        artwork_px = mm_to_px * transform.scale
        painter.save()
        painter.setClipRect(work_target)
        painter.setOpacity(opacity)
        origin = QPointF(
            transform.x_mm * mm_to_px + bounds.x() * artwork_px,
            transform.y_mm * mm_to_px + bounds.y() * artwork_px,
        )
        pixmap = self._context_pixmap_for(artwork_px)
        if pixmap is not None:
            painter.drawPixmap(origin, pixmap)
        else:
            # Too large to rasterize at this zoom: stroke directly.
            painter.translate(transform.x_mm * mm_to_px, transform.y_mm * mm_to_px)
            painter.scale(artwork_px, artwork_px)
            self._stroke_polygons(painter, self._context_polygons, artwork_px)
        painter.restore()

    def _context_pixmap_for(self, artwork_px: float) -> QPixmap | None:
        """Rasterize the unclipped artwork once per (scale, dpr); None if too large."""
        bounds = self._context_bounds_mm
        if bounds is None or artwork_px <= 0:
            return None
        dpr = self.devicePixelRatioF()
        width_px = bounds.width() * artwork_px
        height_px = bounds.height() * artwork_px
        if max(width_px, height_px) * dpr > self._CONTEXT_PIXMAP_MAX_PX:
            return None
        key = (round(artwork_px * 1000), round(dpr * 100), id(self._context_polylines))
        if self._context_pixmap is not None and self._context_pixmap_key == key:
            return self._context_pixmap
        pixmap = QPixmap(
            max(1, int(math.ceil(width_px * dpr)) + 2),
            max(1, int(math.ceil(height_px * dpr)) + 2),
        )
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        ghost_painter = QPainter(pixmap)
        ghost_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ghost_painter.scale(artwork_px, artwork_px)
        ghost_painter.translate(-bounds.x(), -bounds.y())
        self._stroke_polygons(ghost_painter, self._context_polygons, artwork_px)
        ghost_painter.end()
        self._context_pixmap = pixmap
        self._context_pixmap_key = key
        return pixmap

    @staticmethod
    def _stroke_polygons(painter: QPainter, polygons: list[QPolygonF], mm_to_px: float) -> None:
        pen = QPen(QColor(COLORS.artwork_ink))
        pen.setWidthF(max(0.2, 1.0 / mm_to_px))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for polygon in polygons:
            if polygon.size() >= 2:
                painter.drawPolyline(polygon)

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
        plot_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot_painter.setClipRect(QRectF(0.0, 0.0, work_w_px, work_h_px))
        plot_painter.scale(mm_to_px, mm_to_px)
        pen = QPen(QColor(COLORS.artwork_ink))
        pen.setWidthF(max(0.2, 1.0 / mm_to_px))
        plot_painter.setPen(pen)
        plot_painter.setBrush(Qt.BrushStyle.NoBrush)
        for polygon in self._clipped_polygons:
            if polygon.size() >= 2:
                plot_painter.drawPolyline(polygon)
        plot_painter.end()
        self._plot_pixmap = pixmap
        self._plot_pixmap_key = key
        return pixmap


def _fmt_ruler(mm: float) -> str:
    if abs(mm - round(mm)) < 1e-6:
        return str(int(round(mm)))
    return f"{mm:.1f}"
