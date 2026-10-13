"""Circle and ellipse keep-inside: geometry, gestures, persistence, and plot parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from golden_oracle import parse_prepared_polylines
from plotpilot.geometry.ellipse_clip import clip_segment_to_ellipse
from plotpilot.geometry.plot_viewport import PlotViewportError, prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.clip_shape import (
    ClipEllipse,
    ClipEllipseError,
    ClipRectangle,
    ellipse_from_rectangle,
)
from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.print_margins import PrintMargins
from plotpilot.models.project_session import ProjectSession
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_compute_service import compute_interactive_preview
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    PreviewWorkArea,
    WorkAreaOrientation,
)
from plotpilot.services.project_file_service import (
    FORMAT_ID,
    ProjectFileError,
    read_project_file,
    write_project_file,
)
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.preview_widget import LayerPreviewWidget
from plotpilot.ui.preview_workspace import PreviewWorkspace
from qt_helpers import wait_for_plot_success, wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_EMPTY = "No artwork intersects the plot area."


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _line(x0: float, y0: float, x1: float, y1: float) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 100 100">\n'
        f'  <path d="M {x0} {y0} L {x1} {y1}" fill="none" stroke="black"/>\n'
        "</svg>\n"
    )


def _prepare(svg: str, shape: ClipEllipse | ClipRectangle, clip=None):
    kwargs = {}
    if clip is not None:
        kwargs = {
            "clip_x_min_mm": clip[0],
            "clip_y_min_mm": clip[1],
            "clip_x_max_mm": clip[2],
            "clip_y_max_mm": clip[3],
        }
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
        keep_inside=shape,
        **kwargs,
    )
    return parse_prepared_polylines(prepared.svg_text)


def _assert_line(actual, x0, y0, x1, y1) -> None:
    assert len(actual) == 1
    assert len(actual[0]) == 2
    assert actual[0][0][0] == pytest.approx(x0, abs=0.05)
    assert actual[0][0][1] == pytest.approx(y0, abs=0.05)
    assert actual[0][1][0] == pytest.approx(x1, abs=0.05)
    assert actual[0][1][1] == pytest.approx(y1, abs=0.05)


def test_horizontal_and_vertical_ellipse_chords() -> None:
    ellipse = ClipEllipse(50, 50, 20, 10)
    horizontal = _prepare(_line(0, 50, 100, 50), ellipse)
    vertical = _prepare(_line(50, 0, 50, 100), ellipse)
    _assert_line(horizontal, 30, 50, 70, 50)
    _assert_line(vertical, 50, 40, 50, 60)


def test_circle_chord_and_tangent_and_containment() -> None:
    circle = ClipEllipse(50, 50, 10, 10)
    _assert_line(_prepare(_line(0, 50, 100, 50), circle), 40, 50, 60, 50)
    _assert_line(_prepare(_line(45, 50, 55, 50), circle), 45, 50, 55, 50)
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(_line(0, 0, 20, 0), circle)
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(_line(0, 60, 100, 60), circle)
    chord = clip_segment_to_ellipse(30, 55, 70, 55, circle)
    assert chord is not None
    for x_mm, y_mm in ((chord[0], chord[1]), (chord[2], chord[3])):
        nx = (x_mm - 50) / 10
        ny = (y_mm - 50) / 10
        assert nx * nx + ny * ny == pytest.approx(1.0, abs=0.02)


def test_path_that_crosses_twice_stays_split() -> None:
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 100 100">\n'
        '  <path d="M 0 45 L 100 45 L 100 55 L 0 55" fill="none" stroke="black"/>\n'
        "</svg>\n"
    )
    polylines = _prepare(svg, ClipEllipse(50, 50, 10, 10))
    assert len(polylines) == 2
    assert polylines[0][0][1] == pytest.approx(45, abs=0.05)
    assert polylines[1][0][1] == pytest.approx(55, abs=0.05)
    assert abs(polylines[0][-1][1] - polylines[1][0][1]) > 1.0


def test_degenerate_radii_are_rejected() -> None:
    with pytest.raises(ClipEllipseError):
        ClipEllipse(0, 0, 0, 10).validate()
    with pytest.raises(ClipEllipseError):
        ClipEllipse(0, 0, 5, -1).validate()


def test_circle_overlapping_the_margin_stays_inside_the_printable_area() -> None:
    polylines = _prepare(
        _line(0, 50, 80, 50),
        ClipEllipse(0, 50, 20, 20),
        clip=(10, 0, 100, 100),
    )
    _assert_line(polylines, 10, 50, 20, 50)
    for line in polylines:
        for x_mm, _y_mm in line:
            assert x_mm >= 10 - 0.05


def test_rectangle_clip_still_uses_the_overlap_fast_path() -> None:
    rectangle = ClipRectangle(40, 40, 20, 20)
    _assert_line(_prepare(_line(0, 50, 100, 50), rectangle), 40, 50, 60, 50)
    square = ClipRectangle(20, 20, 30, 30)
    assert ellipse_from_rectangle(square).is_circle


def _preview(qapp) -> LayerPreviewWidget:
    widget = LayerPreviewWidget()
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg((FIXTURES / "square_100mm_path.svg").read_text(encoding="utf-8"))
    widget.set_work_area_overlay(
        svg_width_mm=100.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(210.0, 297.0, "A4", True),
    )
    return widget


def _px(widget: LayerPreviewWidget, x_mm: float, y_mm: float) -> QPointF:
    point = widget._mm_to_widget(x_mm, y_mm)  # noqa: SLF001
    assert point is not None
    return point


def _drag(
    widget: LayerPreviewWidget,
    start: QPointF,
    end: QPointF,
    *,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    button = Qt.MouseButton.LeftButton
    widget.mousePressEvent(
        QMouseEvent(QMouseEvent.Type.MouseButtonPress, start, button, button, modifiers)
    )
    widget.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, end, button, button, modifiers))
    widget.mouseReleaseEvent(
        QMouseEvent(QMouseEvent.Type.MouseButtonRelease, end, button, button, modifiers)
    )


def test_shift_draws_a_circle_and_zoom_does_not_move_it(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    widget.set_clip_kind("ellipse")
    widget.set_view_zoom(2.0)
    _drag(
        widget,
        _px(widget, 20, 20),
        _px(widget, 50, 35),
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    shape = widget.clip_shape
    assert isinstance(shape, ClipEllipse)
    assert shape.rx_mm == pytest.approx(15, abs=0.05)
    assert shape.ry_mm == pytest.approx(shape.rx_mm)
    assert shape.cx_mm == pytest.approx(35, abs=0.05)
    drawn = shape
    widget.pan_by(QPointF(30, -10))
    widget.set_artwork_transform(ArtworkTransform(x_mm=8, y_mm=-3, scale=1.4))
    assert widget.clip_shape == drawn


def test_ellipse_move_resize_and_delete(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    widget.set_clip_kind("ellipse")
    _drag(widget, _px(widget, 20, 30), _px(widget, 60, 50))
    shape = widget.clip_shape
    assert isinstance(shape, ClipEllipse)
    assert shape.rx_mm == pytest.approx(20, abs=0.05)
    assert shape.ry_mm == pytest.approx(10, abs=0.05)
    _drag(
        widget,
        _px(widget, shape.cx_mm, shape.cy_mm),
        _px(widget, shape.cx_mm + 10, shape.cy_mm + 4),
    )
    moved = widget.clip_shape
    assert isinstance(moved, ClipEllipse)
    assert moved.cx_mm == pytest.approx(shape.cx_mm + 10, abs=0.05)
    assert moved.rx_mm == pytest.approx(shape.rx_mm)
    _drag(
        widget,
        _px(widget, moved.cx_mm + moved.rx_mm, moved.cy_mm),
        _px(widget, moved.cx_mm + moved.rx_mm + 10, moved.cy_mm),
    )
    resized = widget.clip_shape
    assert isinstance(resized, ClipEllipse)
    assert resized.rx_mm == pytest.approx(moved.rx_mm + 5, abs=0.05)
    assert resized.ry_mm == pytest.approx(moved.ry_mm)
    widget.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    )
    assert widget.clip_shape is None


def test_shape_buttons_follow_the_clip_tool(qapp) -> None:
    _ = qapp
    workspace = PreviewWorkspace()
    assert not workspace.ellipse_shape_button.isVisible()
    workspace.clip_button.setChecked(True)
    assert workspace.rectangle_shape_button.isChecked()
    workspace.ellipse_shape_button.setChecked(True)
    assert workspace.preview.clip_kind == "ellipse"
    assert not workspace.rectangle_shape_button.isChecked()
    workspace.clip_button.setChecked(False)
    assert not workspace.ellipse_shape_button.isVisible()


def test_project_file_keeps_rectangles_and_adds_ellipses(tmp_path: Path) -> None:
    svg = (FIXTURES / "simple.svg").resolve()
    rectangle = ClipRectangle(12, 8, 40, 22)
    session = ProjectSession(
        svg_path=svg,
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform.identity(),
        plot_settings=PlotSettings(),
        fallback_work_area=FallbackWorkArea.A4,
        clip_rectangle=rectangle,
    )
    path = tmp_path / "rect.plotpilot"
    write_project_file(path, session)
    loaded = read_project_file(path)
    assert loaded.clip_rectangle == rectangle
    assert loaded.clip_ellipse is None
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1

    ellipse = ClipEllipse(40, 50, 15, 15)
    write_project_file(
        path,
        ProjectSession(
            svg_path=svg,
            checked_layer_ids=(),
            artwork_transform=ArtworkTransform.identity(),
            plot_settings=PlotSettings(),
            fallback_work_area=FallbackWorkArea.A4,
            clip_ellipse=ellipse,
        ),
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "rectangle" not in data["clipping"]
    assert read_project_file(path).clip_ellipse == ellipse

    legacy = tmp_path / "legacy.plotpilot"
    legacy.write_text(
        json.dumps({"format": FORMAT_ID, "version": 1, "svg": {"path": str(svg)}}),
        encoding="utf-8",
    )
    assert read_project_file(legacy).clip_ellipse is None
    bad = tmp_path / "bad.plotpilot"
    bad.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(svg)},
                "clipping": {"ellipse": {"cx_mm": 1, "cy_mm": 1, "rx_mm": 0, "ry_mm": 4}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectFileError, match="Clipping"):
        read_project_file(bad)


def test_preview_plot_estimate_and_multi_layer_share_the_ellipse(qapp) -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    ellipse = ClipEllipse(0, 0, 1, 1)
    margins = PrintMargins(0, 0)
    settings = PlotSettings()
    prepared = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layers[0]),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
        print_margins=margins,
        keep_inside=ellipse,
    )
    unclipped = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layers[0]),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
        print_margins=margins,
    )
    assert prepared.svg_text != unclipped.svg_text
    assert "clipPath" not in prepared.svg_text
    assert "<ellipse" not in prepared.svg_text
    preview = compute_interactive_preview(
        document,
        layers[0],
        cached_geometry=None,
        transform=ArtworkTransform.identity(),
        plot_settings=settings,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
        print_margins=margins,
        keep_inside=ellipse,
    )
    parsed = parse_prepared_polylines(prepared.svg_text)
    assert len(preview.clipped.polylines) == len(parsed)

    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    assert (
        service.start_plot_layer(
            document,
            layers[0],
            plot_settings=settings,
            print_margins=margins,
            keep_inside=ellipse,
        )
        is None
    )
    wait_for_plot_success(service)
    assert fake.plot_file_contents == [prepared.svg_text]
    assert (
        service.request_pre_plot_estimate(
            document,
            [layers[0]],
            plot_settings=settings,
            print_margins=margins,
            keep_inside=ellipse,
        )
        is None
    )
    wait_until(lambda: fake.estimate_file_contents == [prepared.svg_text])

    both_layers = ClipEllipse(0, 0, 9, 9)
    multi = MultiLayerPlotService(service)
    assert (
        multi.start_job(
            document,
            layers,
            settings=settings,
            print_margins=margins,
            keep_inside=both_layers,
        )
        is None
    )
    wait_until(
        lambda: multi.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE,
        timeout_ms=5000,
    )
    assert multi.continue_after_pen_change() is None
    wait_until(lambda: multi.job.state is MultiLayerJobState.COMPLETED, timeout_ms=5000)
    assert len(fake.plot_file_contents) == 3
    for layer, plotted in zip(layers, fake.plot_file_contents[1:], strict=True):
        layer_svg = prepare_layer_plot_svg(
            plot_svg_for_layer(document, layer),
            plot_settings=settings,
            transform=ArtworkTransform.identity(),
            print_margins=margins,
            keep_inside=both_layers,
        )
        assert plotted == layer_svg.svg_text
