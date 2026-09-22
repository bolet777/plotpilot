"""Layer preview widget behavior."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QByteArray, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from plotpilot.services.preview_work_area import PreviewWorkArea
from plotpilot.ui.preview_widget import (
    LayerPreviewWidget,
    fit_rect_preserve_aspect,
    svg_render_source_size,
)

_PLOT_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm">
  <line x1="0" y1="50" x2="100" y2="50" stroke="black"/>
</svg>"""

MINIMAL_SVG = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <rect width="10" height="10" fill="#000000"/>
</svg>"""


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_valid_preview_loads(qapp) -> None:
    widget = LayerPreviewWidget()
    assert widget.set_preview_svg(MINIMAL_SVG) is True
    assert widget.message is None
    assert widget.last_svg == MINIMAL_SVG


def test_invalid_preview_does_not_crash(qapp) -> None:
    widget = LayerPreviewWidget()
    assert widget.set_preview_svg("<not-valid-svg") is False
    assert widget.message is not None
    widget.repaint()


def _ratio(width: float, height: float) -> float:
    return width / height


def _assert_inside(target: QRectF, available: QRectF) -> None:
    assert target.left() >= available.left() - 1e-9
    assert target.top() >= available.top() - 1e-9
    assert target.right() <= available.right() + 1e-9
    assert target.bottom() <= available.bottom() + 1e-9


def _assert_same_ratio(
    source_w: float,
    source_h: float,
    target: QRectF,
    *,
    tol: float = 1e-9,
) -> None:
    assert abs(_ratio(target.width(), target.height()) - _ratio(source_w, source_h)) <= tol


def test_fit_square_in_wide_widget() -> None:
    available = QRectF(0, 0, 400, 100)
    target = fit_rect_preserve_aspect(100, 100, available)
    _assert_inside(target, available)
    _assert_same_ratio(100, 100, target)
    assert abs(target.width() - 100) <= 1e-9
    assert abs(target.height() - 100) <= 1e-9
    assert abs(target.x() - 150) <= 1e-9


def test_fit_square_in_tall_widget() -> None:
    available = QRectF(0, 0, 100, 400)
    target = fit_rect_preserve_aspect(100, 100, available)
    _assert_inside(target, available)
    _assert_same_ratio(100, 100, target)
    assert abs(target.width() - 100) <= 1e-9
    assert abs(target.y() - 150) <= 1e-9


def test_fit_portrait_in_landscape_widget() -> None:
    available = QRectF(10, 20, 300, 150)
    target = fit_rect_preserve_aspect(50, 100, available)
    _assert_inside(target, available)
    _assert_same_ratio(50, 100, target)
    assert abs(target.height() - 150) <= 1e-9
    assert abs(target.width() - 75) <= 1e-9


def test_fit_landscape_in_portrait_widget() -> None:
    available = QRectF(0, 0, 150, 300)
    target = fit_rect_preserve_aspect(200, 100, available)
    _assert_inside(target, available)
    _assert_same_ratio(200, 100, target)
    assert abs(target.width() - 150) <= 1e-9
    assert abs(target.height() - 75) <= 1e-9


def test_fit_repeated_resize_preserves_ratio() -> None:
    source_w, source_h = 16.0, 9.0
    sizes = [(800, 600), (200, 50), (50, 800), (640, 480), (1200, 1200)]
    for w, h in sizes:
        available = QRectF(0, 0, w, h)
        target = fit_rect_preserve_aspect(source_w, source_h, available)
        _assert_inside(target, available)
        _assert_same_ratio(source_w, source_h, target)


def test_fit_invalid_source_geometry() -> None:
    available = QRectF(0, 0, 200, 200)
    target = fit_rect_preserve_aspect(0, 100, available)
    assert target.width() == 0.0 and target.height() == 0.0


def test_svg_render_source_size_uses_viewbox(qapp) -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
        '<rect width="40" height="20"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    assert renderer.isValid()
    assert svg_render_source_size(renderer) == (40.0, 20.0)


def test_svg_render_source_size_fallback_default_size(qapp) -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
        '<rect width="80" height="40"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    assert renderer.isValid()
    w, h = svg_render_source_size(renderer)
    assert w > 0 and h > 0
    _assert_same_ratio(80, 40, QRectF(0, 0, w, h))


def test_drag_updates_artwork_transform_in_mm(qapp) -> None:
    widget = LayerPreviewWidget()
    widget.resize(520, 420)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg(_PLOT_SVG) is True
    widget.set_work_area_overlay(
        svg_width_mm=100.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(
            width_mm=210.0,
            height_mm=297.0,
            label="A4",
            from_fallback=True,
        ),
    )
    layout = widget.physical_layout
    assert layout is not None
    start_x = widget.artwork_transform.x_mm
    start_y = widget.artwork_transform.y_mm
    origin = QPoint(260, 210)
    delta_px = 40
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, origin)
    move_pos = QPoint(origin.x() + delta_px, origin.y())
    widget.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(move_pos),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, move_pos)
    qapp.processEvents()
    expected_delta_mm = delta_px / layout.mm_to_px
    assert widget.artwork_transform.x_mm == pytest.approx(start_x + expected_delta_mm)
    assert widget.artwork_transform.y_mm == pytest.approx(start_y)


def test_resize_triggers_repaint_only(qapp) -> None:
    widget = LayerPreviewWidget()
    assert widget.set_preview_svg(MINIMAL_SVG) is True
    widget.resize(640, 480)
    widget.resize(100, 400)
    widget.resize(900, 200)
    assert widget.last_svg == MINIMAL_SVG
